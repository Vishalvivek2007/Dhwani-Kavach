import os
import numpy as np

from ml.audio_utils import load_audio_bytes, chunk_audio
from ml.aasist_model import load_aasist, infer as _aasist_infer
from ml import detector_v2
from ml import detector_v3
from ml import spectrogram_cnn
from ml import wav2vec2_detector
from ml import vad
from ml import quality
from ml import replay
from ml.handcrafted import score_handcrafted
from ml.breath_detector import score_breath
from ml.phase_coherence import score_phase
from ml.liveness import score_liveness
from ml.ensemble import WEIGHTS, compute_ensemble
from ml.scoring import calibrate, thresholds as _score_thresholds

_MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "AASIST.pth")
_model = None

# ponytail: cap chunks so a long call can't blow up latency (~0.5s/chunk on CPU).
# Beyond this we stride across the whole file rather than only its first minute.
_MAX_CHUNKS = 16

# ponytail: RMS below this is effectively silence; scoring it just feeds the
# heuristics noise and yields false alarms. Raise if genuinely quiet calls drop.
_SILENCE_RMS = 1e-3

# A chunk must be at least this fraction speech (Silero VAD) to be worth a full
# SSL forward pass. RMS only catches silence; this also drops loud non-speech
# (hold music, hum, line noise). No-op when VAD is unavailable (fail-open).
_MIN_SPEECH = 0.3

_EVIDENCE_KEYS = [k for k in WEIGHTS if k != "aasist"]


def _get_model():
    # Only needed as a fallback when the trained CNN weights aren't present.
    global _model
    if _model is None:
        _model = load_aasist(_MODEL_PATH)
    return _model


def active_model_version() -> str:
    """Which primary neural tier will actually score, given what's loadable now.
    Reported in every verdict so a silent fallback (champion weights absent ->
    CNN) is visible downstream instead of masquerading as the champion. Mirrors
    the _neural_infer() precedence exactly; append '+clone_v3' when the second
    independent detector is also voting."""
    if detector_v2.available():
        primary = "w2v2aasist-cotrain"
    elif wav2vec2_detector.available():
        primary = "wav2vec2-xlsr"
    elif spectrogram_cnn.available():
        primary = "spectrogram-cnn"
    else:
        primary = "aasist-raw"
    return f"{primary}+clone_v3" if detector_v3.available() else primary


def _neural_infer(model, chunk: np.ndarray) -> float:
    """Best available PRIMARY neural model: detector_v2 (W2VAASIST-cotrain) >
    wav2vec2 (SSL) > spectrogram CNN > AASIST. detector_v3 is scored
    separately in _score_chunk as a second, independent ensemble vote (not a
    fallback in this chain) -- see ml/ensemble.py's WEIGHTS comment for why
    two independent neural signals matter more than picking "the best one"."""
    if detector_v2.available():
        return detector_v2.infer(chunk)
    if wav2vec2_detector.available():
        return wav2vec2_detector.infer(chunk)
    if spectrogram_cnn.available():
        return spectrogram_cnn.infer(chunk)
    return _aasist_infer(model, chunk)


def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x, dtype=np.float64)))) if len(x) else 0.0


def _score_chunk(chunk: np.ndarray, neural_score: float) -> dict:
    # neural_score is the primary detector's spoof prob, computed once for the whole
    # batch of chunks upstream (detector_v2.infer_batch) instead of per chunk here.
    raw = {
        "aasist":   neural_score,
        "mfcc":     score_handcrafted(chunk),
        "breath":   score_breath(chunk),
        "phase":    score_phase(chunk),
        "liveness": score_liveness(chunk),
    }
    if detector_v3.available():
        raw["clone_v3"] = detector_v3.infer(chunk)
    # Never let a NaN/out-of-range value from a degenerate chunk reach downstream scoring.
    return {k: float(np.clip(np.nan_to_num(v), 0.0, 1.0)) for k, v in raw.items()}


def detect_samples(audio: np.ndarray) -> dict:
    """
    Run all 5 layers across a decoded waveform, not just its first 4s.
    Audio is split into ~4s chunks; the highest-risk chunk drives the verdict
    (a deepfake anywhere in the call is a deepfake).

    risk_score/alert_level come from compute_ensemble() -- a weighted fusion
    of up to two INDEPENDENT neural detectors (detector_v2, detector_v3 --
    different architectures/training data, different failure modes) and 4
    acoustic heuristics. No single signal can flag alone -- see
    ml/ensemble.py's WEIGHTS comment for why. evidence/layer_breakdown keep
    the per-layer view for the UI. raw_score is the primary neural model's
    uncalibrated probability; fused_score is the final 0-1 ensemble
    probability, for callers (the websocket loop) doing their own temporal
    aggregation on top of the fused signal rather than one neural score.
    """
    have_trained = detector_v2.available() or wav2vec2_detector.available() or spectrogram_cnn.available()
    model = None if have_trained else _get_model()

    chunks = chunk_audio(audio)
    if len(chunks) > _MAX_CHUNKS:
        chunks = chunks[:: -(-len(chunks) // _MAX_CHUNKS)]  # stride to span whole file

    # Score only chunks with real audio energy; silence has no honest verdict.
    voiced = [c for c in chunks if _rms(c) >= _SILENCE_RMS]
    # Then use VAD to spend SSL forward passes only where there's speech:
    #  - essentially no speech anywhere (max ratio tiny) -> skip entirely (GREEN),
    #    which is how a silence/music/hold-tone window avoids a wasted forward pass;
    #  - otherwise keep the speech-heavy chunks, but never blank a clip VAD can't
    #    segment well (degraded telephony): fall back to its most-speech chunk.
    # Fail-open when VAD is unavailable (speech_ratio()==1.0 -> nothing dropped).
    if voiced and vad.available():
        ratios = [vad.speech_ratio(c) for c in voiced]
        if max(ratios) < 0.1:
            voiced = []
        else:
            voiced = [c for c, r in zip(voiced, ratios) if r >= _MIN_SPEECH] \
                or [voiced[int(np.argmax(ratios))]]
    if not voiced:
        # No speech to judge -> benign GREEN (not a threat), but flag that we had
        # nothing to score so the UI never reads it as a confident all-clear.
        return {
            "risk_score": 0, "alert_level": "GREEN",
            "layer_breakdown": {k: 0 for k in WEIGHTS},
            "evidence": {k: 0 for k in _EVIDENCE_KEYS},
            "raw_score": 0.0, "fused_score": 0.0,
            "quality": {"ok": True, "score": 0, "reason": "no speech detected",
                        "snr_db": 0.0, "rms": 0.0, "clip_frac": 0.0},
            "model_version": active_model_version(),
        }

    # Input-quality gate: is this window even worth a confident verdict? A too
    # quiet / clipping / noisy input pushes the audio out-of-distribution, where
    # the score is unreliable in BOTH directions (may pass a real caller OR wave
    # through a replayed deepfake). Measured on the voiced region so silence pauses
    # don't drag the SNR. When it fails, we abstain (UNCERTAIN) instead of guessing.
    q = quality.assess(np.concatenate(voiced))

    # Batch the primary neural forward across all voiced chunks (one backbone pass
    # instead of one per chunk). Falls back to the per-chunk chain when the batched
    # detector_v2 isn't the active primary.
    if detector_v2.available():
        neural_scores = detector_v2.infer_batch(voiced)
    else:
        neural_scores = [_neural_infer(model, c) for c in voiced]
    per_chunk = [_score_chunk(c, n) for c, n in zip(voiced, neural_scores)]
    # Worst chunk = highest FUSED ensemble risk, not just the primary neural
    # slot -- either independent detector flagging a chunk should be able to
    # drive chunk selection, not only detector_v2.
    worst = max(per_chunk, key=lambda s: compute_ensemble(s)["risk_score"])

    p = worst["aasist"]
    fused = compute_ensemble({**worst, "aasist": calibrate(p)})
    risk_score = fused["risk_score"]
    t_low, t_high = _score_thresholds()
    alert_level = "RED" if risk_score >= t_high else "AMBER" if risk_score >= t_low else "GREEN"
    result = {
        "risk_score": risk_score, "alert_level": alert_level,
        "raw_score": p, "fused_score": risk_score / 100.0,
        "model_version": active_model_version(),
    }
    result["layer_breakdown"] = {k: int(round(v * 100)) for k, v in worst.items()}
    result["evidence"] = {k: result["layer_breakdown"][k] for k in _EVIDENCE_KEYS if k in result["layer_breakdown"]}
    # Novelty / zero-day flag: how unfamiliar this synthesis signature looks.
    # Two signals, taking the stronger:
    #  1. Primary neural model's own softmax uncertainty (p near 0.5 = neither
    #     confidently real nor fake).
    #  2. Cross-model disagreement, when detector_v3 is available: two
    #     detectors trained on different data/objectives disagreeing sharply
    #     is itself evidence of an unfamiliar case -- ensemble disagreement is
    #     a better-calibrated OOD signal than any single model's confidence
    #     (Lakshminarayanan et al., "Deep Ensembles", NeurIPS 2017).
    novelty = round(1.0 - abs(2.0 * p - 1.0), 3)
    if "clone_v3" in worst:
        disagreement = round(abs(worst["aasist"] - worst["clone_v3"]), 3)
        novelty = max(novelty, disagreement)
    result["novelty"] = novelty
    # D3: an unknown synthesis signature can't read fully clean — a confident
    # GREEN with high model uncertainty is exactly the zero-day case. Lift to AMBER.
    if novelty >= 0.6 and result["alert_level"] == "GREEN":
        result["alert_level"] = "AMBER"
    # Abstention (last word): if the input was too degraded to trust, don't emit a
    # confident GREEN/AMBER/RED at all -- surface UNCERTAIN + the actionable reason
    # ("move to a quieter place" / "mic level too low"). risk_score is kept for
    # transparency but the band tells the agent the number can't be trusted.
    result["quality"] = q
    if not q["ok"]:
        result["alert_level"] = "UNCERTAIN"
    # Replay-channel evidence (no ensemble weight): flags the loudspeaker->air->mic
    # signature — the classic clone-injection path AND the channel where artifact
    # detectors degrade hardest. Either the model catches the synthesis or this
    # catches the replay. Fullband channels only (see ml/replay.py telephony note).
    result["replay"] = replay.assess(np.concatenate(voiced))
    return result


def detect_audio(audio_bytes: bytes) -> dict:
    """Decode encoded audio bytes (wav/mp3/…) then score the whole recording."""
    audio, _ = load_audio_bytes(audio_bytes)
    return detect_samples(audio)
