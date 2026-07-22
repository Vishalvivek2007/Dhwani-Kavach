import asyncio
import os
import time

import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ml.detector import detect_samples
from ml.audio_utils import SAMPLE_RATE
from ml.scoring import StreamAggregator
from ml import scam_detector
from ml.fusion import fuse
from app import audit, metrics, policy

router = APIRouter()

_WINDOW = SAMPLE_RATE * 4    # 4s window — matches the model's training clip length
_HOP = SAMPLE_RATE * 2       # slide 2s forward (50% overlap)
_CONTEXT = SAMPLE_RATE * 8   # transcribe the last ~8s for a fuller transcript
_SCAM_PERIOD = 4.0           # seconds between scam (STT+LLM) runs


def _drain_windows(buf: np.ndarray):
    windows = []
    while len(buf) >= _WINDOW:
        windows.append(buf[:_WINDOW])
        buf = buf[_HOP:]
    return windows, buf


@router.websocket("/ws/analyze")
async def ws_analyze(websocket: WebSocket):
    """
    Real-time streaming fraud shield for a live call.

    Send raw 16 kHz mono float32 PCM as binary frames. Emits
    {risk_score, alert_level, layer_breakdown, novelty, call_max, scam,
    action, action_reason} per scored window.

    Stays real-time under load: only the newest window is scored (backlog is
    discarded), and the scam layer (STT+LLM, heavier) runs in the background so
    it never blocks the verdict loop.
    """
    # Same key gate as REST /api/* (app.main.require_key), read from the same env.
    # Browsers can't set custom headers on the WS handshake, so the token rides a
    # query param (?key=... or ?token=...). When DHWANI_API_KEY is unset the demo
    # stays open, exactly like the REST guard. Reject before accept() -> HTTP 403.
    api_key = os.environ.get("DHWANI_API_KEY", "")
    if api_key:
        supplied = websocket.query_params.get("key") or websocket.query_params.get("token") or ""
        if supplied != api_key:
            await websocket.close(code=1008)  # policy violation
            return

    await websocket.accept()
    # Shadow mode: env default, optional ?shadow=true|false override per connection.
    q = websocket.query_params.get("shadow")
    shadow = policy.is_shadow({"true": True, "false": False}.get((q or "").lower()))
    buf = np.empty(0, dtype=np.float32)
    recent = np.empty(0, dtype=np.float32)
    scam = {"score": 0, "tactics": [], "transcript": ""}
    scam_task: asyncio.Task | None = None
    last_scam = 0.0
    agg = StreamAggregator()
    try:
        while True:
            data = await websocket.receive_bytes()
            n = len(data) - (len(data) % 4)  # ponytail: drop a partial float, realign next frame
            frame = np.frombuffer(data[:n], dtype=np.float32)
            buf = np.concatenate([buf, frame])
            recent = np.concatenate([recent, frame])[-_CONTEXT:]

            windows, buf = _drain_windows(buf)
            if not windows:
                continue
            # Only score the newest window; discarding backlog keeps us real-time
            # and stops a slow CPU from flooding the client with stale verdicts.
            w = windows[-1]

            # Harvest a finished background scam result, if any.
            if scam_task is not None and scam_task.done():
                try:
                    scam = scam_task.result() or scam
                    print(f"[scam] score={scam.get('score')} "
                          f"transcript={scam.get('transcript','')!r}", flush=True)
                except Exception as exc:
                    print(f"[scam] error: {exc}", flush=True)
                scam_task = None

            try:
                result = await asyncio.to_thread(detect_samples, w.copy())
            except Exception as exc:
                metrics.record_error("ws")
                await websocket.send_json({"error": str(exc)})
                continue

            # EWMA smoothing + confirmation + hysteresis (ml.scoring.StreamAggregator)
            # over the FUSED ensemble score (not the raw neural score alone -- a
            # single SSL detector is brittle out-of-domain; see ml/ensemble.py).
            # Damps one-off spikes, needs 2 confirming windows above t_high to enter
            # RED, and holds RED until the score drops back below t_low. call_max
            # preserves "one cloned segment flags the call" over the smoothed track.
            state = agg.update(result["fused_score"])
            result["risk_score"] = state["risk_score"]
            result["alert_level"] = state["alert_level"]
            result["call_max"] = state["call_max"]
            # Abstention wins over the smoothed band: a degraded window can't earn a
            # confident GREEN/RED. detect_samples set quality; re-assert UNCERTAIN
            # here because StreamAggregator just overwrote alert_level above.
            _q = result.get("quality", {})
            if not _q.get("ok", True):
                result["alert_level"] = "UNCERTAIN"

            # Kick off the next scam pass in the background (non-blocking, throttled).
            now = time.monotonic()
            if scam_task is None and now - last_scam >= _SCAM_PERIOD and len(recent) >= _WINDOW:
                last_scam = now
                snap = recent.copy()
                scam_task = asyncio.create_task(asyncio.to_thread(scam_detector.analyze, snap))

            result["scam"] = scam
            _rp = result.get("replay", {})
            result.update(fuse(
                deepfake_risk=result["risk_score"],
                scam_score=scam.get("score", 0),
                novelty=result.get("novelty", 0.0),
                quality_ok=_q.get("ok", True),
                quality_reason=_q.get("reason", ""),
                replay_suspect=_rp.get("suspect", False),
            ))
            policy.annotate(result, shadow)
            result["call_id"] = audit.record("ws", result)
            metrics.record_verdict("ws", result["alert_level"], result.get("action"))
            await websocket.send_json(result)
    except WebSocketDisconnect:
        pass
    finally:
        if scam_task is not None:
            scam_task.cancel()
