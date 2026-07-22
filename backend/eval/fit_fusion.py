"""Fit the L6 decision fusion: a logistic regression over the per-layer scores,
replacing the hand-set weights in ml.ensemble.

The eval shows the hand-weighted ensemble DILUTES a strong neural detector -- the
4 acoustic heuristics carry half the vote but don't separate modern fakes. A
learned fusion fixes this by discovering the weights from labelled data; on this
corpus it drives the heuristic weights toward zero and lets the neural detectors
dominate, which is the whole point of §6/§7-L6 in the blueprint.

Reports leave-one-out CV AUC (honest on small data) + the learned weights, then
writes models/fusion.json for ml.ensemble to load. NOTE: on a 30-clip public demo
set this is a mechanism demonstration; refit on production-scale data before trust.

usage: PYTHONPATH=backend python -m eval.fit_fusion eval/corpus
"""
from __future__ import annotations

import glob
import json
import os
import sys

import numpy as np

from ml.audio_utils import load_audio
from ml.detector import detect_samples
from ml.ensemble import WEIGHTS, compute_ensemble

_LAYERS = list(WEIGHTS.keys())  # aasist, clone_v3, mfcc, breath, phase, liveness
_OUT = os.path.join(os.path.dirname(__file__), "..", "models", "fusion.json")


def _collect(folder: str, label: int):
    X, y = [], []
    exts = ("*.wav", "*.flac", "*.mp3", "*.m4a", "*.mpeg", "*.ogg")
    for f in sorted(sum((glob.glob(os.path.join(folder, e)) for e in exts), [])):
        a, _ = load_audio(f)
        lb = detect_samples(a).get("layer_breakdown", {})
        X.append([lb.get(k, 0) / 100.0 for k in _LAYERS])
        y.append(label)
    return X, y


def _auc(scores: np.ndarray, y: np.ndarray) -> float:
    fake = scores[y == 1]; real = scores[y == 0]
    if not len(fake) or not len(real):
        return float("nan")
    wins = sum((f > real).sum() + 0.5 * (f == real).sum() for f in fake)
    return float(wins / (len(fake) * len(real)))


def main():
    corpus = sys.argv[1] if len(sys.argv) > 1 else "eval/corpus"
    from sklearn.linear_model import LogisticRegression

    Xr, yr = _collect(os.path.join(corpus, "real"), 0)
    Xf, yf = _collect(os.path.join(corpus, "fake"), 1)
    X = np.array(Xr + Xf); y = np.array(yr + yf)
    print(f"collected {len(X)} clips, {X.shape[1]} layers: {_LAYERS}")

    # Honest generalization on tiny data: leave-one-out CV AUC of the learned
    # fusion vs the current hand-weighted ensemble.
    loo_learned, loo_hand = np.zeros(len(X)), np.zeros(len(X))
    for i in range(len(X)):
        mask = np.arange(len(X)) != i
        clf = LogisticRegression(C=1.0, max_iter=1000).fit(X[mask], y[mask])
        loo_learned[i] = clf.predict_proba(X[i:i + 1])[0, 1]
        loo_hand[i] = compute_ensemble(dict(zip(_LAYERS, X[i])))["risk_score"] / 100.0
    print(f"LOO-CV AUC  hand-weighted ensemble : {_auc(loo_hand, y):.3f}")
    print(f"LOO-CV AUC  learned L6 fusion       : {_auc(loo_learned, y):.3f}")

    # Fit on all data for the shipped coefficients.
    clf = LogisticRegression(C=1.0, max_iter=1000).fit(X, y)
    coef = clf.coef_[0]
    print("\nlearned weights (|coef|, higher = more trusted):")
    for name, c in sorted(zip(_LAYERS, coef), key=lambda t: -abs(t[1])):
        print(f"  {name:10s} {c:+.2f}")

    json.dump({"layers": _LAYERS, "coef": coef.tolist(), "intercept": float(clf.intercept_[0])},
              open(_OUT, "w"), indent=2)
    print(f"\nwrote {_OUT}")


if __name__ == "__main__":
    main()
