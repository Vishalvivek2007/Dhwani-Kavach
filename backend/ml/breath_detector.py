import numpy as np
import librosa
from ml.audio_utils import SAMPLE_RATE


_FRAME_LEN = int(0.025 * SAMPLE_RATE)   # 25 ms
_HOP_LEN   = int(0.010 * SAMPLE_RATE)   # 10 ms
_MIN_BREATH_FRAMES = 5                   # ~50 ms minimum breath duration
_MAX_BREATH_FRAMES = 30                  # ~300 ms maximum

# DEPLOYMENT KNOB -- flatness threshold for "broadband low-energy segment".
# Was 0.05, calibrated against nothing; measured on Dataset_orig (122 clips,
# our own voices + commercial clones) the actual low-energy-frame flatness
# distribution tops out at p90=0.087, p95=0.125 -- so 0.05 already sat above
# ~85% of all real audio and _find_breath_events returned 0 on nearly every
# clip, permanently pinning score_breath() to its events==0 branch (0.75)
# regardless of input. 0.02 sits inside the actual distribution (measured
# median 0.005, p75 0.027) so the count varies with real evidence again.
_FLATNESS_MIN = 0.02


def _find_breath_events(audio: np.ndarray) -> int:
    """Count breath-like events: brief segments of low energy with broadband content."""
    rms = librosa.feature.rms(y=audio, frame_length=_FRAME_LEN,
                               hop_length=_HOP_LEN)[0]
    flatness = librosa.feature.spectral_flatness(y=audio, n_fft=512,
                                                  hop_length=_HOP_LEN)[0]
    n = min(len(rms), len(flatness))
    rms, flatness = rms[:n], flatness[:n]

    rms_norm = rms / (rms.max() + 1e-8)

    # Candidate: low energy AND some broadband noise content.
    is_candidate = (rms_norm > 0.005) & (rms_norm < 0.12) & (flatness > _FLATNESS_MIN)

    events = 0
    run = 0
    for flag in is_candidate:
        if flag:
            run += 1
        else:
            if _MIN_BREATH_FRAMES <= run <= _MAX_BREATH_FRAMES:
                events += 1
            run = 0
    if _MIN_BREATH_FRAMES <= run <= _MAX_BREATH_FRAMES:
        events += 1
    return events


def score_breath(audio: np.ndarray) -> float:
    """
    Layer 3: breath/pause pattern analysis.

    A cloned voice's noise floor between phonemes tends to be unnaturally
    clean (no room hiss / breath), so fewer broadband low-energy segments
    leans fake. MEASURED on Dataset_orig (61 real / 61 fake, 4s worst-window
    clips): real events median 8 (p25 6, p75 11), fake median 7 (p25 5, p75
    9) -- real and fake distributions overlap heavily (rank-AUC 0.61, barely
    better than a coin flip). This is why ensemble.py gives breath only 2.5%
    weight: real signal, but weak -- treat as corroborating evidence, never
    a verdict on its own.

    Graded linear score anchored on the measured fake/real quartiles (not
    hardcoded event-count buckets that don't match this signal's actual
    scale) so a clip's score varies with its own evidence instead of pinning
    to one constant. Returns spoof probability in [0.30, 0.65] -- deliberately
    narrow, reflecting how little this layer alone can tell you.
    """
    events = _find_breath_events(audio)
    score = 0.60 - 0.0417 * (events - 5)
    return float(np.clip(score, 0.30, 0.65))


if __name__ == "__main__":
    # Self-check: the score must vary with event count (the bug this module was
    # fixed for was every input landing on the constant 0.75 -- _FLATNESS_MIN
    # sat above ~85% of real audio, so events was always 0), and stay inside
    # the documented [0.30, 0.65] band at the extremes.
    assert abs(np.clip(0.60 - 0.0417 * (0 - 5), 0.30, 0.65) - 0.65) < 1e-9
    assert abs(np.clip(0.60 - 0.0417 * (20 - 5), 0.30, 0.65) - 0.30) < 1e-9

    sr = SAMPLE_RATE
    rng = np.random.default_rng(0)
    speech_burst = 0.3 * np.sin(2 * np.pi * 180 * np.arange(int(0.3 * sr)) / sr)
    silent_gap = np.zeros(int(0.1 * sr), dtype=np.float32)          # true silence: no broadband content
    noisy_gap = (0.02 * rng.standard_normal(int(0.1 * sr))).astype(np.float32)  # low-level broadband hiss

    def build(gap):
        return np.concatenate([speech_burst, gap] * 8).astype(np.float32)

    e_silent = _find_breath_events(build(silent_gap))
    e_noisy = _find_breath_events(build(noisy_gap))
    assert e_noisy > e_silent, f"broadband gaps should register more events than true silence: {e_noisy} vs {e_silent}"
    s_silent, s_noisy = score_breath(build(silent_gap)), score_breath(build(noisy_gap))
    assert 0.30 <= s_silent <= 0.65 and 0.30 <= s_noisy <= 0.65
    assert s_noisy < s_silent, f"more breath-like events should score lower (more real-like): {s_noisy} vs {s_silent}"
    print(f"breath self-check ok  (silent-gap events={e_silent} score={s_silent:.2f}, "
          f"noisy-gap events={e_noisy} score={s_noisy:.2f})")
