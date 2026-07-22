# Dhwani-Kavach

Real-time call-fraud shield for banks — detects AI voice clones **and** human
scam scripts on live calls, on-prem, with a decision (MONITOR / CHALLENGE /
BLOCK) in ~4 seconds.

## Architecture

Two **independent neural deepfake detectors** lead the verdict; heuristics are
corroborating evidence; parallel layers read the *content* and the *channel*:

| Layer | What it does |
|---|---|
| `detector_v2` — XLS-R + W2VAASIST head | primary neural detector (channel-robust fine-tune) |
| `detector_v3` — clone specialist | independent second detector, different training data — failure modes anti-correlate |
| 4 acoustic heuristics (MFCC / breath / phase / liveness) | evidence display, near-zero weight (measured) |
| Input-quality gate | too quiet/noisy/clipped → **UNCERTAIN**, never a false all-clear |
| Replay-channel gate | loudspeaker→air→mic injection detected → forced CHALLENGE |
| Scam-script layer | Whisper STT → LLM tactic analysis (urgency, OTP asks, threats…) — catches *human* scammers, multilingual |
| Decision fusion | rule-based MONITOR/CHALLENGE/BLOCK with transaction context |
| Voice OTP (`/verify`) | speak-back challenge: ASR content match + deepfake check, parallel verification path |

**Measured** (122-clip held-out set, own voices + commercial clones, reproducible
via `cd backend && python -m eval.run ../Dataset_orig`): **99.2% accuracy · EER
1.6% · AUC 0.999** clean; telephony is the known gap (~20% EER, channel-robust
retrain in progress).

> **A fresh clone has no working model.** `backend/models/w2v2aasist_full.safetensors`
> (~306 MB) and its paired `calibration.json` are gitignored — get them from the
> team or retrain (see [PHASE-H-KAGGLE.md](PHASE-H-KAGGLE.md)). Without them the
> detector falls back to a weaker committed head. The scam layer needs
> `NVIDIA_API_KEY` set, else it returns neutral.

## Quick start

**One-click (Windows):** `start-fresh.bat` — kills stale processes, starts
backend + frontend, opens the dashboard.

Manual:

```bash
# Backend  -> http://localhost:8000
pip install -r backend/requirements.txt
python -m uvicorn app.main:app --app-dir backend --port 8000

# Frontend -> http://localhost:8080
cd frontend && npm install && npm run dev
```

**Demo surfaces:** live monitor + file upload (`/`), WebRTC live-call demo
(`/call`), Voice OTP (`/verify`), and the bank product pages —
`:8000/cases` (evidence packs) · `/campaigns` (fraud-ring view) ·
`/governance` (TPR/FPR, drift, registry) · `/metrics` (Prometheus).

## Key documents

| Doc | Purpose |
|---|---|
| [HANDOFF.md](HANDOFF.md) | current technical state — start here to develop |
| [DEMO-RUNBOOK.md](DEMO-RUNBOOK.md) | stage rules: verified clips, channel discipline |
| [PRE-DEMO-CHECKLIST.md](PRE-DEMO-CHECKLIST.md) | T-1 day / T-30 min tick list |
| [FINALS-DECK-BRIEF.md](FINALS-DECK-BRIEF.md) | the measured numbers (single source of truth) |
| [INTEGRATION.md](INTEGRATION.md) | how it drops into a bank (SIPREC, on-prem) |
| [PHASE-H-KAGGLE.md](PHASE-H-KAGGLE.md) | channel-robust retrain pipeline |
