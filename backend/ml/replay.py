"""Replay-channel detector — is this audio arriving through a loudspeaker?

The over-the-air replay path (phone speaker → air → mic) is the classic way a
fraudster injects a clone into a "live" call, and it's also the channel where
SSL artifact detectors degrade hardest (the air hop smears the very micro-
artifacts they key on). Instead of fighting that physics, detect the channel
itself: small speakers cannot reproduce the low band a chest-resonant human
voice at a real mic always carries, and the speaker+air path rolls off the
top octave too.

Two cheap spectral ratios (numpy only):
  lf_ratio = energy 60-160 Hz / energy 200-1000 Hz    (fundamental + chest)
  hf_ratio = energy 5-7.5 kHz / energy 1-4 kHz        (top-octave air loss)

Thresholds were fit on this repo's own data (Dataset_orig live phone-mic reals
vs the same clips through a 250 Hz-4.2 kHz small-speaker simulation):
  live  lf min 0.135 / hf min 0.010   |   replay lf max 0.009 / hf max 0.007
so the default knobs sit in a ~14x gap on the primary (LF) signal.

DEPLOYMENT KNOB: a narrowband telephony line (G.711, 300-3400 Hz) legitimately
lacks both bands and WILL read as replay — only run this on fullband channels
(browser mic, WebRTC tap). Evidence-only: surfaced in the API/UI, carries no
ensemble weight.
"""
from __future__ import annotations

import numpy as np

# --- knobs (fit on Dataset_orig reals vs speaker-sim; see module docstring) --- #
LF_FLOOR = 0.05    # below -> low band missing (speaker can't make it)
HF_FLOOR = 0.02    # below -> top octave missing (speaker + air rolloff)
_EPS = 1e-12


def _band_ratios(x: np.ndarray, sr: int) -> tuple[float, float] | None:
    """Mean power spectrum over 32 ms Hann frames; None if clip too short."""
    win = int(0.032 * sr)
    n = len(x) // win
    if n < 4:
        return None
    frames = x[: n * win].reshape(n, win) * np.hanning(win)
    ps = (np.abs(np.fft.rfft(frames, axis=1)) ** 2).mean(axis=0)
    f = np.fft.rfftfreq(win, 1.0 / sr)

    def e(lo: float, hi: float) -> float:
        return float(ps[(f >= lo) & (f < hi)].sum()) + _EPS

    return e(60, 160) / e(200, 1000), e(5000, 7500) / e(1000, 4000)


def assess(audio: np.ndarray, sr: int = 16000) -> dict:
    """Replay-channel report for a mono float32 waveform.

    Keys: suspect (bool), score (0-100, higher = more speaker-like),
    lf_ratio / hf_ratio (raw evidence), reason (plain language)."""
    x = np.asarray(audio, dtype=np.float32).ravel()
    r = _band_ratios(x, sr)
    if r is None:
        return {"suspect": False, "score": 0, "lf_ratio": 0.0, "hf_ratio": 0.0,
                "reason": "clip too short to judge"}
    lf, hf = r
    # graded distance below each floor; LF is the strong, well-separated signal
    lf_score = float(np.clip(1.0 - lf / (2 * LF_FLOOR), 0.0, 1.0))
    hf_score = float(np.clip(1.0 - hf / HF_FLOOR, 0.0, 1.0))
    score = int(round(100 * (0.7 * lf_score + 0.3 * hf_score)))
    suspect = lf < LF_FLOOR and hf < HF_FLOOR  # both deficits = speaker signature
    reason = ("low+high bands missing — audio consistent with a loudspeaker replay"
              if suspect else "band profile consistent with a direct voice")
    return {"suspect": suspect, "score": score,
            "lf_ratio": round(lf, 4), "hf_ratio": round(hf, 5), "reason": reason}


if __name__ == "__main__":
    # Self-check: speech-like fullband signal passes; the same signal through a
    # small-speaker bandpass sim flags. Security-adjacent path -> must not invert.
    from scipy.signal import butter, sosfilt
    sr = 16000
    rng = np.random.default_rng(0)
    t = np.arange(4 * sr) / sr
    # voice-ish: 120 Hz fundamental + harmonics up to high band + noise floor
    x = sum(0.3 / k * np.sin(2 * np.pi * 120 * k * t) for k in range(1, 60))
    x = (x * (0.5 + 0.5 * np.sin(2 * np.pi * 3 * t)) + 0.01 * rng.standard_normal(len(t))).astype(np.float32)
    live = assess(x, sr)
    assert not live["suspect"], f"fullband voice must pass, got {live}"

    sos = butter(4, [250, 4200], btype="bandpass", fs=sr, output="sos")
    rep = assess(sosfilt(sos, x).astype(np.float32), sr)
    assert rep["suspect"], f"speaker-sim must flag, got {rep}"
    assert rep["score"] > live["score"]
    print(f"replay self-check ok  (live score {live['score']}, replay score {rep['score']})")
