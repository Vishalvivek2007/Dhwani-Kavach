"""Live synthesize-and-detect demo — generate a synthetic voice ON STAGE and
watch the detector flag it.

The strongest possible demo of "we catch machine voices" is one where the
audience picks the words: no pre-baked file, no trick. KittenTTS (local, no
API key, ~25 MB model) speaks any text; the clip goes straight to the running
backend's /api/analyze; the verdict + risk + time-to-verdict print in the
terminal and the wav is kept for replaying in the dashboard.

NOTE: KittenTTS uses PRESET voices — it does not clone a specific person.
For a clone-of-a-real-voice moment, use the ElevenLabs clips already in
sample_audio/ / Dataset_orig, or an ElevenLabs live session (see DEMO-RUNBOOK).

MEASURED (2026-07-21, w2v2aasist-cotrain+clone_v3): only Bruno (RED 47) and
Rosie (RED 34) get flagged; Hugo AMBER; the other 5 voices slip GREEN. This
generator is OUT-OF-DOMAIN for the current model (trained on commercial
clones) — so on stage, use the ElevenLabs clips (60/61 RED) for the headline
detection demo, and use THIS script as the red-team story: --sweep shows
exactly which generators we catch and which feed the next retrain.

usage (backend must be running on :8000):
    python tools/demo_synth.py                                # default scam line, Bruno
    python tools/demo_synth.py --text "any text the judges pick"
    python tools/demo_synth.py --sweep                        # red-team all voices
"""
from __future__ import annotations

import argparse
import io
import time

DEFAULT_TEXT = ("Hello, this is the bank security team. Your account has been "
                "compromised. Please share the one time password immediately "
                "so we can secure your funds.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", default=DEFAULT_TEXT)
    ap.add_argument("--voice", default="Bruno", help="Bruno/Rosie flag RED today; others evade (see docstring)")
    ap.add_argument("--backend", default="http://127.0.0.1:8000")
    ap.add_argument("--keep", default="demo_synth.wav", help="where to save the generated wav")
    ap.add_argument("--sweep", action="store_true", help="red-team: score EVERY voice, print the catch/evade table")
    args = ap.parse_args()

    from kittentts import KittenTTS  # lazy: first run downloads the ~25 MB model

    if args.sweep:
        import io
        import requests
        import soundfile as sf
        tts = KittenTTS()
        voices = tts.available_voices() if callable(tts.available_voices) else tts.available_voices
        print(f"red-team sweep: {len(voices)} voices vs {args.backend}")
        for v in voices:
            wav = tts.generate(args.text, voice=v)
            buf = io.BytesIO(); sf.write(buf, wav, 24000, format="WAV"); buf.seek(0)
            d = requests.post(f"{args.backend}/api/analyze",
                              files={"audio": ("d.wav", buf, "audio/wav")}, timeout=120).json()
            tag = "CAUGHT" if d.get("alert_level") == "RED" else "evaded"
            print(f"  {v:12s} {d.get('alert_level'):9s} risk {str(d.get('risk_score')):>3s}  {tag}")
        return

    print(f"synthesizing ({args.voice}): {args.text[:60]}...")
    t0 = time.perf_counter()
    tts = KittenTTS()
    tts.generate_to_file(args.text, args.keep, voice=args.voice)
    t_gen = time.perf_counter() - t0
    print(f"  generated in {t_gen:.1f}s -> {args.keep}")

    import requests
    t0 = time.perf_counter()
    with open(args.keep, "rb") as f:
        r = requests.post(f"{args.backend}/api/analyze", files={"audio": ("demo.wav", f, "audio/wav")}, timeout=120)
    r.raise_for_status()
    d = r.json()
    t_det = time.perf_counter() - t0
    print(f"\n  VERDICT   : {d.get('alert_level')}  (risk {d.get('risk_score')}/100)")
    print(f"  model     : {d.get('model_version')}")
    print(f"  detected in {t_det:.1f}s")
    scam = d.get("scam") or {}
    if scam.get("tactics"):
        print(f"  scam tactics: {', '.join(scam['tactics'])} ({scam.get('score')}/100)")
    if d.get("alert_level") == "RED":
        print("\n  >> HIGH RISK — synthetic voice flagged. Replay the wav in the dashboard for the visual.")
    else:
        print("\n  !! not flagged RED — do NOT use this text/voice combo on stage; try another voice.")


if __name__ == "__main__":
    main()
