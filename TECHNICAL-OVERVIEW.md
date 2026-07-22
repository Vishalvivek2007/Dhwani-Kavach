# Dhwani-Kavach — Technical Overview (for academic review)

A complete, honest technical description: architecture, algorithms, models,
training, evaluation, engineering decisions, and limitations. Written for a
technical panel that needs to understand *how* and *why* each part works.

---

## 1. System architecture

A FastAPI service exposing two ingestion paths into one shared detection engine:

```
                          ┌──────────────── Detection engine ────────────────┐
 REST  POST /api/analyze ─┤  audio → [5-layer voice ensemble]                │
 (files, disputes)        │          [scam-script: STT → LLM]                │
                          │          [novelty]   [voiceprint/campaign]       │
 WS  /ws/analyze ─────────┤              │                                   │
 (live, 4s/2s windows)    │       [decision fusion + txn context]            │
                          └──────────────┬───────────────────────────────────┘
                                         ▼
                       {risk_score, alert_level, action, layer_breakdown,
                        scam, novelty, campaign, mode, call_id}
                                         │
                 audit log (JSONL) · metrics (Prometheus) · governance · campaigns
```

- **Backend:** FastAPI + Uvicorn, PyTorch, torchaudio/librosa, transformers.
- **Frontend:** Vite + React (live dashboard + file-upload UI).
- **Design principle:** every advanced layer is **additive and fail-safe** — if a
  dependency (STT, LLM, model file) is missing, that layer returns neutral and the
  rest of the pipeline still produces a verdict.

---

## 2. Voice deepfake detection — the core ensemble

**Two independent neural detectors** produce per-window spoof probabilities in
[0,1] and carry the verdict (0.90 combined weight); four handcrafted heuristics
are shown as corroborating evidence only (0.10 total — measured near-noise on
modern fakes, so they cannot dominate a confident verdict). A calibrated ensemble
gives a 0–100 risk score banded **GREEN / AMBER / RED**, with a fourth band —
**UNCERTAIN** — when the input is too degraded to score honestly (§2.3).

**Ensemble weights** (`ml/ensemble.py`):

| Layer | Weight | Method |
|---|---|---|
| `aasist` (neural) | 0.45 | XLS-R (300M) truncated to 5 layers + **W2VAASIST** graph-attention head |
| `clone_v3` (neural) | 0.45 | second independent detector, fine-tuned on modern commercial clones |
| `mfcc` | 0.025 | handcrafted spectral/MFCC features (evidence) |
| `breath` | 0.025 | breath-pattern energy heuristic (evidence) |
| `phase` | 0.025 | phase-coherence analysis (evidence) |
| `liveness` | 0.025 | liveness/articulation heuristic (evidence) |

**Why two detectors, not one bigger one:** a single SSL detector that scores well
on a dev set can collapse out-of-domain (Müller et al., Interspeech 2022 report
200–1000% cross-domain EER degradation). Two detectors **trained on different
clone families fail differently**, so their disagreement is itself a signal (§7)
and one model's blind spot doesn't silently clear a fraud. This is the central
design lesson (§3).

**Aggregation over a whole recording:** audio is split into ~4 s chunks; the
**worst (highest-risk) chunk drives the verdict** — *a deepfake anywhere in the
call is a deepfake*. A **Silero VAD** gates non-speech so we never score silence
or noise. The neural forward is **batched** across chunks (one backbone pass, not
one per chunk).

### 2.1 The neural detectors
- **`aasist` (primary):** `facebook/wav2vec2-xls-r-300m` truncated to its first 5
  encoder layers (we only consume `hidden_states[5]`; the trailing ~18 layers are
  removed with bit-identical output, ~2–3× less compute) → a vendored **W2VAASIST**
  graph-attention head → softmax, spoof = P(class 1). Preprocessing mirrors the
  Codecfake reference exactly: repeat-pad (tile) to 64 600 samples at 16 kHz,
  zero-mean/unit-variance normalise.
- **`clone_v3` (second detector):** an independent XLS-R-based detector fine-tuned
  on a different, clone-heavy corpus; run in the same pass and fused 50/50 with
  `aasist`.
- **Calibration:** raw scores → alarm scale via Platt scaling fit on a labelled
  dev set (`models/calibration.json`, `ml/scoring.py`), with L2 ridge to prevent
  the small-data logistic blow-up, and safety clamps so a bad calibration degrades
  gracefully rather than flagging everything.
- **Why SSL:** XLS-R is pretrained on 128-language unlabelled speech — good for
  Hindi/Indian voices — and fine-tuning a light head on top generalises far better
  than a from-scratch CNN.

### 2.2 Fallback chain
The precedence chain is `detector_v2 (dual) → wav2vec2_detector → spectrogram_cnn
→ aasist`: if the fine-tuned bundle is absent the engine falls back to a weaker
committed head so it still runs. A mel-spectrogram CNN baseline reached 2.75% dev
EER but 9.75% on unseen attacks and false-flagged real laptop-mic voices — the
domain-generalisation gap the SSL detectors close.

### 2.3 Input-quality abstention (`ml/quality.py`)
Every window is scored on level (RMS), clipping, and segmental SNR. A too-quiet /
clipping / noisy input is **out-of-distribution**, where the score is unreliable
in *both* directions (may pass a real caller OR wave through a replayed deepfake).
When it fails, the verdict becomes **UNCERTAIN** with an actionable reason ("move
somewhere quieter", "mic level too low") and fusion forces CHALLENGE — never a
false GREEN, never a BLOCK on a score we don't trust.

### 2.4 Replay-channel gate (`ml/replay.py`)
A clone played from a loudspeaker into a mic (the classic live-injection channel,
and the one where artifact detectors degrade hardest) leaves a spectral signature:
small drivers can't reproduce the low band and the driver+air path rolls off the
top octave. Two band-energy ratios detect it; a suspected replay forces CHALLENGE
even if the voice score reads clean. Evidence-only weight; fullband channels only
(a narrowband telephony line legitimately lacks both bands, so the gate is not run
there).

---

## 3. Training, evaluation & the generalization lesson

**Metric:** Equal Error Rate (EER) and AUC — standard for anti-spoofing, plus
accuracy at the deployed threshold. Lower EER / higher AUC is better.

**The lesson that shaped the architecture.** Our first single detector — a
fine-tuned wav2vec2 — scored **< 0.5% EER on its dev set** and then **40% EER /
AUC 0.63 on real commercial clones of our own voices.** Benchmark accuracy did not
transfer. The fix was *two independent detectors + calibration on our own labelled
data*, not a bigger model.

**Measured result** (single fixed benchmark: 122-clip held-out set, our own voices
+ commercial clones, `python -m eval.run ../Dataset_orig`):

| Config | Accuracy | EER | AUC |
|---|---|---|---|
| Neural-only | 95.9% | 6.6% | 0.989 |
| **Full ensemble (deployed)** | **99.2%** | **1.6%** | **0.999** |

**Known gaps, measured not hidden:** (a) **telephony ~20% EER** — no telephony-
specific training in the deployed bundle yet; a channel-robust retrain
(`training/train_robust.py`: telephony/reverb/noise/**speaker-replay**
augmentation, gated to not regress clean) is in progress. (b) A few out-of-domain
studio-real clips still false-positive. (c) Our own red-teaming found an
open-source generator that partially evades the current model — that finding feeds
the retrain, and is the argument that **the loop is the product, not any frozen
model.** (d) 122 clips is a small corpus — strong evidence, not proof.

---

## 4. Streaming engine (live calls)

- **Windowing:** raw 16 kHz float32 PCM frames are buffered into **4 s windows with
  a 2 s hop** (50% overlap) → a fresh verdict ~every 2 s; first verdict ~4 s in.
- **Off-thread inference:** CPU-bound torch runs via `asyncio.to_thread` so the
  event loop (and other connections) aren't blocked.
- **Backpressure:** only the **newest** window is scored; backlog is discarded.
  Without this, a slow CPU lets windows queue and then floods the client — the
  cause of an early UI freeze.
- **Stream aggregation (`ml/scoring.py` `StreamAggregator`):** a single 4 s window
  is noisy, so the live track is stabilised with **EWMA smoothing + 2-window
  confirmation + hysteresis** — it needs two confirming windows above the RED
  threshold to enter RED, and holds RED until the smoothed score falls back below
  the lower threshold. A separate `call_max` preserves "one cloned segment flags
  the call" over the smoothed track. This replaced an earlier peak-hold-with-decay
  scheme, which was jumpier and had no confirmation gate.

---

## 5. Scam-script detection (human scammers)

- **Pipeline:** rolling audio → **Whisper** (`faster-whisper`, base, int8 CPU) →
  transcript → **LLM** (NVIDIA NIM, OpenAI-compatible API) → `{scam_score, tactics}`.
- **Model choice — a real lesson:** the default is a plain instruct model
  (`meta/llama-3.1-8b-instruct`), **not** a reasoning model. A reasoning model
  (e.g. `nemotron-super-49b`) puts its answer behind a separate `reasoning` field
  and can leave `content` null for many seconds/tokens — incompatible with this
  layer's ~8 s real-time budget; one retired model id additionally *hung* server-
  side, silently eating the timeout every call. The instruct model returns clean
  JSON in ~1.4 s.
- **Tactics** (closed set, evidence-required prompt): urgency, authority
  impersonation, isolation, new-beneficiary, sensitive-info (OTP/PIN) request, threat.
- **Throttling:** STT+LLM is heavier, so it runs **in the background every ~4 s**
  over the last ~8 s of audio and is folded into the next verdict — it never blocks
  the 2 s detection cadence.
- **Multilingual:** Whisper auto-detects language; the LLM reasons in Hindi/Hinglish.
- **Fail-safe:** no key / no STT / network error → neutral score; voice detection unaffected.

---

## 6. Decision fusion

Rule-based (deliberately, for auditability — every decision is explainable):

```
threat     = voice_risk ≥ RED_threshold  OR  scam_score ≥ 70
high_value = new_beneficiary OR amount ≥ ₹50,000
action = BLOCK     if threat and high_value
         CHALLENGE if threat
         MONITOR   otherwise
# overrides (last word), each forcing at least CHALLENGE, never a silent clear:
#   quality not ok  → CHALLENGE ("verify another way")
#   replay suspected → CHALLENGE ("channel can't be trusted")
```
The voice RED threshold is read from `ml.scoring` so the action banding always
matches the alert-level banding. Novelty is **noted** in the reason but no longer
forces the threat flag on its own (it was too noisy as a hard gate). Each action
carries a plain-English reason; thresholds are tunable per the bank's risk
appetite. (Rationale: a learned policy needs labelled outcome data the system must
first accumulate; the rule layer is the honest v1 and the fallback.)

---

## 7. Novelty / zero-day detection

- **Signal (two, take the stronger):** (1) the primary model's own softmax
  uncertainty, `novelty = 1 − |2p − 1|` (peaks at p=0.5); (2) **cross-detector
  disagreement** — when `aasist` and `clone_v3` diverge sharply, that is itself an
  out-of-distribution signal, and ensemble disagreement is better-calibrated than
  any single model's confidence (Lakshminarayanan et al., "Deep Ensembles",
  NeurIPS 2017).
- **Action:** novelty ≥ 0.6 lifts a confident GREEN to AMBER (an unknown synthesis
  signature shouldn't read fully clean).
- **Honest limitation:** signal (1) is still a **softmax-uncertainty heuristic**;
  a calibrated upgrade is embedding-distance OOD (Mahalanobis to class centroids) —
  noted as the upgrade path in code. Signal (2) only exists while both detectors
  are loaded.

---

## 8. Campaign / repeat-attacker detection

- **Voiceprint:** an L2-normalised SSL embedding used for cosine correlation.
- **Correlation:** cosine similarity against stored voiceprints (sqlite). Match ≥
  **0.85** → same cluster (campaign); a voiceprint from a previously-flagged call
  hits a **blocklist** on its next call.
- **Honest limitations:** (a) the embedding is **not** a dedicated speaker-
  verification space, so 0.85 must be **calibrated on real clones** in a pilot;
  (b) it's a **linear scan** — fine for a branch/PoC, needs FAISS/pgvector beyond
  ~100k voiceprints; (c) **implementation note:** the embedding currently comes
  from `wav2vec2_detector` (the legacy `deepfake_w2v.pt`, gitignored) via a
  *separate* forward pass, not the deployed dual detectors — so on a machine
  without that file, campaign correlation is silently skipped (the verdict is
  unaffected; campaign intel is additive by design). Unifying the embedding onto
  the deployed detector is a tracked cleanup.

---

## 9. Governance, audit, observability

- **Audit log:** append-only JSONL, one line per verdict, stable `call_id`,
  **no audio** (transcript text only). Backs the forensic evidence packs.
- **Confusion matrix:** analyst fraud/legit labels are joined to audit verdicts →
  live **TPR / FPR / precision**.
- **Drift:** two-window heuristic — flagged-rate in the recent window vs the
  baseline; |Δ| ≥ 0.2 raises an alert. (Upgrade path: PSI / proper time-series.)
- **Model registry:** champion/challenger with version, training data, eval scores.
- **Metrics:** Prometheus exposition (latency, verdict mix, errors).
- **Shadow vs enforce:** a policy flag — score+log only, or act — for risk-free piloting.

---

## 10. Notable engineering decisions

- **Fail-safe composition:** advanced layers degrade to neutral; the core verdict
  always survives a missing dependency.
- **OpenMP conflict:** torch and ctranslate2 (Whisper) each ship an Intel OpenMP
  runtime; on Windows both load `libiomp5md.dll` and the duplicate-init check aborts
  the process. Resolved with `KMP_DUPLICATE_LIB_OK` set before import (same runtime,
  safe) — the clean alternative is isolating STT in a subprocess.
- **No-audio principle:** audio is scored in memory and discarded; only verdicts
  and transcripts persist — minimises the data-privacy/breach surface.
- **Minimalism (intentional):** code is kept to the simplest version that works,
  with explicit `ponytail:` comments naming each deliberate shortcut and its
  upgrade path — so reviewers can see intent, not omission.

---

## 11. Honest limitations & future work

1. **Telephony (~20% EER)** is the headline gap — deployed bundle has no
   telephony-specific training yet. Channel-robust retrain in progress; until it
   lands, degraded input abstains (UNCERTAIN) rather than guessing.
2. **Small eval corpus (122 clips)** — strong evidence, not proof. A larger,
   multi-source benchmark with confidence intervals is the next evaluation step.
3. **Out-of-domain false positives** — a few studio-real voices still read fake;
   the fix is more diverse real training data, not a threshold tweak.
4. **Threshold calibration** (voiceprint 0.85, fusion cut-offs) needs real bank
   data — current values are reasonable defaults, not tuned operating points.
5. **Novelty** signal (1) is a softmax-uncertainty heuristic → upgrade to
   embedding-OOD.
6. **Campaign store** is a linear scan → FAISS/pgvector at scale; and its
   embedding rides the legacy model (§8c) → unify onto the deployed detector.
7. **LLM is a cloud call** (NIM); on-prem deployment runs a self-hosted NIM
   container — code only changes a base URL.
8. **Speaker identity** (is it *this customer*?) is not yet built — anti-spoofing
   only; customer-voiceprint verification / Voice OTP (`/verify`) is the layer
   being built out (see `VOICE-OTP-HANDOFF.md`).
9. **Adversarial robustness** (evasion via perturbation) is untested — and our own
   red-teaming already found a generator that partially evades the current model.
10. **Security & scale:** endpoints are API-key gated only when `DHWANI_API_KEY`
    is set (open by default for the demo); per-call state (OTP challenges, RTC
    rooms, voiceprint scan) is in-process, so multi-replica scale-out needs a
    shared store. mTLS and horizontal scale-out are on the hardening roadmap, not
    shipped.

---

## 12. Tech stack

FastAPI · Uvicorn · PyTorch · torchaudio · librosa · transformers (XLS-R) ·
Silero VAD · faster-whisper (CTranslate2) · NVIDIA NIM (Llama-3.1-8B-Instruct) ·
scipy · scikit-learn · sqlite · Prometheus exposition · Vite + React + Tailwind ·
WebRTC · Docker.

> Summary: a layered, fail-safe pipeline where **two independent SSL detectors**
> carry the verdict, an LLM adds human-scam coverage, quality/replay gates protect
> against untrustworthy channels, and rule-based fusion turns scores into auditable
> decisions — engineered to run on-prem, in real time, with the honest limitations
> above as the roadmap.
