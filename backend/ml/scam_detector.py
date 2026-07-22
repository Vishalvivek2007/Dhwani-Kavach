"""Scam-script layer — catch the vishing where the voice is a *real human*.

Pipeline: audio -> transcript (faster-whisper, optional) -> LLM (NVIDIA NIM) ->
scam score + detected social-engineering tactics.

Everything degrades gracefully: no whisper, no API key, or any network error ->
returns a neutral {score:0, tactics:[]} so the rest of the pipeline is never
blocked. The deepfake detector keeps working regardless.

Default model is a plain instruct model, not a reasoning one: reasoning models
(e.g. nemotron-super-49b, -v1 AND -v1.5) put their answer in a separate
"reasoning" field first and can leave message.content == null for many
seconds/tokens -- incompatible with this layer's ~8s budget inside a real-time
call. -v1 additionally hangs indefinitely server-side (retired endpoint,
confirmed via curl/requests/urllib all timing out with zero bytes back) rather
than erroring, silently eating the timeout every call. If you override
NVIDIA_MODEL, pick a non-reasoning instruct model.

Uses stdlib urllib for the LLM call (no new HTTP dependency).
ponytail: whisper "base" + 8s LLM timeout; raise model size / timeout only if accuracy or latency demands it.
"""
from __future__ import annotations

import json
import os
import urllib.request

import numpy as np

from ml.audio_utils import SAMPLE_RATE

_BASE_URL = os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
_MODEL = os.environ.get("NVIDIA_MODEL", "meta/llama-3.1-8b-instruct")
_KEY = os.environ.get("NVIDIA_API_KEY", "")

# The system sits on the CONTACT-CENTRE call: a bank agent talking to a customer.
# The agent is legitimate, so classic scammer tactics (OTP asks, threats) rarely
# appear. What DOES appear is Authorized-Push-Payment fraud -- the REAL customer,
# in their REAL voice, authorising a transfer because a scammer is manipulating
# them in real time. Voice biometrics pass (it's them), deepfake detection passes
# (real voice) -- the conversation is the only signal, and that's what we read.
_TACTICS = [
    "coaching",            # customer being fed answers by a third party (live control)
    "duress",              # fear/reluctance/confusion -- acting under pressure
    "scam_narrative",      # "safe account", police/RBI order, crypto/investment windfall, romance
    "agent_pressure",      # caller pushing the AGENT to skip steps / hurry
    "high_risk_intent",    # large transfer, brand-new payee, "move everything", access/SIM reset
    "third_party_benefit", # money going to someone the customer just met / was told to pay
]

_SYSTEM = (
    "You are a bank fraud analyst listening to a call between a BANK AGENT and a "
    "CUSTOMER. The agent is legitimate. Your job is to detect Authorized Push "
    "Payment (APP) fraud and social engineering -- a genuine customer being "
    "manipulated or coerced (often by a third party in real time) into "
    "authorising a transfer or account change. Rate 0-100 how likely this call is "
    "APP fraud / a coached or coerced customer, and list ONLY the signals with "
    "EXPLICIT evidence in the transcript. Do not infer signals that are not there. "
    "Signal definitions:\n"
    "- coaching: the customer is being fed answers / repeating phrases / pausing to "
    "consult someone / a background voice directs them.\n"
    "- duress: the customer sounds fearful, reluctant, confused, or says they were "
    "told they must act right now or face loss.\n"
    "- scam_narrative: mentions a 'safe/secure account', a police/RBI/government/tax "
    "instruction, a crypto or investment windfall, or a new online-only acquaintance.\n"
    "- agent_pressure: the caller pushes the AGENT to bypass verification, hurry, or "
    "make an exception.\n"
    "- high_risk_intent: the customer wants a large transfer, a brand-new payee, to "
    "'move everything', or an access/card/SIM reset.\n"
    "- third_party_benefit: the money or benefit goes to someone the customer just "
    "met, was instructed to pay, or does not personally know.\n"
    "A normal balance enquiry or a routine known-payee payment is NOT fraud -- score "
    "it low. Include a signal only if its definition is clearly met by the words in "
    'the transcript. Reply with STRICT JSON only: {"score": <int 0-100>, "tactics": '
    "[<strings>]}. No prose."
)

# --- transcription (optional) ------------------------------------------------
_whisper = None
_whisper_tried = False


def _get_whisper():
    global _whisper, _whisper_tried
    if _whisper_tried:
        return _whisper
    _whisper_tried = True
    try:
        from faster_whisper import WhisperModel
        _whisper = WhisperModel("base", device="cpu", compute_type="int8", cpu_threads=2)
    except Exception:
        _whisper = None  # not installed / failed to load -> scam layer stays neutral
    return _whisper


def transcribe(audio: np.ndarray) -> tuple[str, str]:
    """Return (transcript, detected_language). Language auto-detected (Hindi/
    English/Hinglish/regional all supported by Whisper)."""
    model = _get_whisper()
    if model is None:
        return "", ""
    try:
        segments, info = model.transcribe(audio.astype("float32"), language=None, vad_filter=True)
        text = " ".join(s.text for s in segments).strip()
        return text, getattr(info, "language", "") or ""
    except Exception:
        return "", ""


# --- LLM scoring -------------------------------------------------------------
def score_transcript(text: str) -> dict:
    """Score a transcript via NIM. Neutral result on any failure."""
    text = (text or "").strip()
    if not text or not _KEY:
        return {"score": 0, "tactics": [], "transcript": text}
    try:
        payload = json.dumps({
            "model": _MODEL,
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": text[:4000]},
            ],
            "temperature": 0.0,
            "max_tokens": 200,
            "stream": False,
        }).encode()
        req = urllib.request.Request(
            f"{_BASE_URL}/chat/completions",
            data=payload,
            headers={"Authorization": f"Bearer {_KEY}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            body = json.loads(resp.read())
        content = body["choices"][0]["message"]["content"] or ""  # reasoning models can leave this null
        parsed = _extract_json(content)
        score = int(np.clip(parsed.get("score", 0), 0, 100))
        tactics = [t for t in parsed.get("tactics", []) if t in _TACTICS]
        return {"score": score, "tactics": tactics, "transcript": text}
    except Exception:
        return {"score": 0, "tactics": [], "transcript": text}


def _extract_json(s: str) -> dict:
    """Pull the first {...} block out of an LLM reply; tolerate stray prose/fences."""
    i, j = s.find("{"), s.rfind("}")
    if i == -1 or j == -1:
        return {}
    try:
        return json.loads(s[i:j + 1])
    except Exception:
        return {}


def analyze(audio: np.ndarray) -> dict:
    """audio -> transcript -> scam score. Neutral if transcription/LLM unavailable."""
    text, lang = transcribe(audio)
    result = score_transcript(text)
    result["language"] = lang
    return result


if __name__ == "__main__":
    # ponytail self-check: parser + scoring logic without needing the network.
    assert _extract_json('noise {"score": 88, "tactics": ["urgency"]} tail') == {
        "score": 88, "tactics": ["urgency"]}
    assert _extract_json("not json") == {}
    r = score_transcript("")            # empty -> neutral
    assert r["score"] == 0 and r["tactics"] == []
    print("scam_detector self-check ok")
