import asyncio
import time

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from ml.audio_utils import load_audio_bytes
from ml.detector import detect_samples
from ml import scam_detector, wav2vec2_detector
from ml.fusion import fuse
from app import audit, metrics, policy, voiceprints

router = APIRouter()

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # ponytail: 25 MB cap; raise if real calls run longer


class AnalysisResult(BaseModel):
    risk_score: int
    alert_level: str
    layer_breakdown: dict
    quality: dict = {}
    replay: dict = {}
    novelty: float = 0.0
    model_version: str = ""
    scam: dict = {}
    action: str = "MONITOR"
    action_reason: str = ""
    call_id: str = ""
    mode: str = "enforce"
    enforced: bool = True
    campaign: dict = {}


@router.post("/analyze", response_model=AnalysisResult)
async def analyze_audio(
    audio: UploadFile = File(...),
    amount: float = Form(0),
    new_beneficiary: bool = Form(False),
    shadow: bool | None = Form(None),
):
    data = await audio.read()
    if not data:
        raise HTTPException(status_code=422, detail="Empty audio upload.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Audio file too large (max 25 MB).")
    t0 = time.monotonic()
    try:
        samples, _ = await asyncio.to_thread(load_audio_bytes, data)
        # CPU-bound torch inference + (optional) STT/LLM — keep off the event loop.
        result = await asyncio.to_thread(detect_samples, samples)
        scam = await asyncio.to_thread(scam_detector.analyze, samples)
    except Exception as exc:
        metrics.record_error("rest")
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    result["scam"] = scam
    _q = result.get("quality", {})
    _rp = result.get("replay", {})
    result.update(fuse(
        deepfake_risk=result["risk_score"],
        scam_score=scam.get("score", 0),
        novelty=result.get("novelty", 0.0),
        txn={"amount": amount, "new_beneficiary": new_beneficiary},
        quality_ok=_q.get("ok", True),
        quality_reason=_q.get("reason", ""),
        replay_suspect=_rp.get("suspect", False),
    ))
    policy.annotate(result, policy.is_shadow(shadow))
    result["call_id"] = audit.record("rest", result)
    # Campaign correlation: fingerprint the voice and link it to prior calls.
    if wav2vec2_detector.available():
        try:
            vec = await asyncio.to_thread(wav2vec2_detector.embed, samples)
            result["campaign"] = voiceprints.register(
                result["call_id"], vec, result["risk_score"], result.get("action"))
        except Exception:
            pass  # campaign intel is additive — never fail the verdict
    metrics.observe_latency(time.monotonic() - t0)
    metrics.record_verdict("rest", result["alert_level"], result.get("action"))
    return AnalysisResult(**result)
