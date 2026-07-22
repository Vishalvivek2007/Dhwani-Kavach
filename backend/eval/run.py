"""Evaluation harness -- make the detector's real behaviour visible and comparable.

Runs the full pipeline over a labelled corpus and reports, side by side:
  - NEURAL-ONLY   : the primary SSL detector's probability alone.
  - FULL ENSEMBLE  : the fused multi-layer risk (neural + heuristics + novelty).
so you can SEE what the multi-layer design buys over a single classifier -- the
whole point of the platform vs "another AI classifier".

Metrics per config: EER, AUC, accuracy, and FAR/FRR at the deployed thresholds.
With --telephony it re-runs every clip through ml.telephony (8 kHz G.711) and
reports the EER shift -- i.e. how much a phone line costs you.

Layout (same convention as tools/fit_calibration.py):
    <corpus>/real/*.wav   (bonafide)
    <corpus>/fake/*.wav   (spoof)

usage:
    PYTHONPATH=backend python -m eval.run <corpus_dir> [--telephony] [--html out.html]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import time

import numpy as np

from ml.audio_utils import load_audio, SAMPLE_RATE
from ml.detector import detect_samples
from ml.scoring import thresholds as _thresholds
from ml import telephony


def _eer(fake: np.ndarray, real: np.ndarray) -> tuple[float, float]:
    """Equal-error rate and its threshold. fake should score high, real low.
    miss = spoof scored below t; false_alarm = bonafide scored at/above t."""
    ts = np.linspace(0.0, 1.0, 1001)
    miss = np.array([(fake < t).mean() if len(fake) else 0.0 for t in ts])
    fa = np.array([(real >= t).mean() if len(real) else 0.0 for t in ts])
    i = int(np.argmin(np.abs(miss - fa)))
    return float((miss[i] + fa[i]) / 2.0), float(ts[i])


def _auc(fake: np.ndarray, real: np.ndarray) -> float:
    """P(random fake scores above random real) -- rank-based, ties count half."""
    if not len(fake) or not len(real):
        return float("nan")
    wins = sum((f > real).sum() + 0.5 * (f == real).sum() for f in fake)
    return float(wins / (len(fake) * len(real)))


def _metrics(fake: np.ndarray, real: np.ndarray, t_op: float) -> dict:
    eer, t_eer = _eer(fake, real)
    far = float((fake < t_op).mean()) if len(fake) else float("nan")  # spoof accepted
    frr = float((real >= t_op).mean()) if len(real) else float("nan")  # bonafide rejected
    acc = float((np.concatenate([fake >= t_op, real < t_op])).mean())
    return {"eer": eer, "t_eer": t_eer, "auc": _auc(fake, real),
            "far": far, "frr": frr, "acc": acc, "n_fake": len(fake), "n_real": len(real)}


def _score_dir(folder: str, degrade: bool) -> list[dict]:
    rows = []
    exts = ("*.wav", "*.flac", "*.mp3", "*.m4a", "*.mpeg", "*.ogg")
    for f in sorted(sum((glob.glob(os.path.join(folder, e)) for e in exts), [])):
        audio, _ = load_audio(f)
        if degrade:
            audio = telephony.to_telephony(audio, sr=SAMPLE_RATE)
        t0 = time.perf_counter()
        out = detect_samples(audio)
        dt = (time.perf_counter() - t0) * 1000.0
        rows.append({
            "file": os.path.basename(f),
            "neural": float(out.get("raw_score", 0.0)),      # primary SSL prob alone
            "ensemble": float(out.get("risk_score", 0)) / 100.0,  # fused multi-layer
            "novelty": float(out.get("novelty", 0.0)),
            "verdict": out.get("alert_level", "GREEN"),
            "model_version": out.get("model_version", ""),
            "latency_ms": dt,
        })
    return rows


def _evaluate(corpus: str, degrade: bool) -> dict:
    real_rows = _score_dir(os.path.join(corpus, "real"), degrade)
    fake_rows = _score_dir(os.path.join(corpus, "fake"), degrade)
    t_low, t_high = _thresholds()
    t_op = t_high / 100.0
    res = {"n_real": len(real_rows), "n_fake": len(fake_rows), "t_op": t_op, "configs": {}}
    for key in ("neural", "ensemble"):
        fake = np.array([r[key] for r in fake_rows])
        real = np.array([r[key] for r in real_rows])
        res["configs"][key] = _metrics(fake, real, t_op)
    lat = [r["latency_ms"] for r in real_rows + fake_rows]
    res["latency_ms_p50"] = float(np.median(lat)) if lat else float("nan")
    res["rows"] = real_rows + fake_rows
    return res


def _fmt(res: dict, title: str) -> str:
    n = res["configs"]["neural"]; e = res["configs"]["ensemble"]

    def line(name, m):
        return (f"  {name:14s} EER {m['eer']:6.1%}  AUC {m['auc']:5.3f}  "
                f"acc {m['acc']:6.1%}  FAR {m['far']:6.1%}  FRR {m['frr']:6.1%}")
    d_eer = n["eer"] - e["eer"]
    return (f"\n{title}  (real={res['n_real']}, fake={res['n_fake']}, "
            f"op-threshold={res['t_op']:.2f}, p50 latency={res['latency_ms_p50']:.0f} ms)\n"
            f"{line('NEURAL-only', n)}\n{line('FULL ENSEMBLE', e)}\n"
            f"  >> ensemble changes EER by {d_eer:+.1%} "
            f"({'better' if d_eer > 0 else 'worse' if d_eer < 0 else 'same'})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus", help="dir with real/ and fake/ subfolders of .wav/.flac")
    ap.add_argument("--telephony", action="store_true", help="also eval through an 8kHz phone line")
    ap.add_argument("--html", help="write a visual HTML report to this path")
    ap.add_argument("--json", help="write raw results JSON to this path")
    args = ap.parse_args()

    clean = _evaluate(args.corpus, degrade=False)
    print(_fmt(clean, "CLEAN"))
    phone = None
    if args.telephony:
        phone = _evaluate(args.corpus, degrade=True)
        print(_fmt(phone, "TELEPHONY (8kHz G.711)"))
        d = phone["configs"]["ensemble"]["eer"] - clean["configs"]["ensemble"]["eer"]
        print(f"\n  >> phone line costs the ensemble {d:+.1%} EER")

    if args.json:
        json.dump({"clean": clean, "telephony": phone}, open(args.json, "w"), indent=2)
        print(f"\nwrote {args.json}")
    if args.html:
        _write_html(args.html, clean, phone)
        print(f"wrote {args.html}")


def _write_html(path: str, clean: dict, phone: dict | None):
    from eval.report import render
    open(path, "w", encoding="utf-8").write(render(clean, phone))


if __name__ == "__main__":
    main()
