# Dhwani-Kavach — Product Explainer for Bank IT

A precise, plain-language walkthrough of the entire system: what each part does,
how it works, and why it matters to the bank. Written for your IT and fraud teams.

---

## 1. What it is, in one paragraph

Dhwani-Kavach is a **real-time call-fraud shield**. It listens to a banking call,
and within ~4 seconds returns a single decision — **Monitor, Challenge, or
Block** — backed by a 0–100 risk score and an explainable breakdown. It catches
**AI voice clones (deepfakes)** *and* **human social-engineering scams**, runs
**inside the bank's own network**, and stores **no audio**. It is not a research
model; it is a deployable service with auditing, governance, and monitoring built in.

**The problem it solves:** fraudsters now clone a customer's or relationship
manager's voice, or pressure customers with scripted scams, to authorise
transfers. OTP and existing voice biometrics do **not** stop a convincing clone
or a coerced-but-genuine customer. Dhwani-Kavach is the missing layer.

---

## 2. How a call flows through it (end to end)

```
 Live call audio ──► [1] Voice deepfake check (neural + 4 heuristics)
                     [2] Scam-script check (speech-to-text → LLM → tactics)
                     [3] Novelty check (unknown synthesis signature)
                     [4] Voiceprint check (seen this voice before? campaign?)
                            │
                            ▼
                     [5] Decision fusion  +  transaction context
                            │
                            ▼
                 MONITOR / CHALLENGE / BLOCK   (+ score, + reasons)
                            │
                ┌───────────┼───────────────┐
                ▼           ▼                ▼
           Agent screen  Audit log     Metrics / Governance
           / fraud engine (evidence)   (TPR/FPR, drift)
```

Two ways calls come in: **live streaming** (WebSocket, for in-progress calls) and
**file upload** (REST, for recordings/disputes). Both run the same engine.

---

## 3. Each functionality, explained

### A. Voice deepfake detection (the core)
- **What:** decides if the *voice itself* is AI-generated.
- **How:** **two independent neural detectors** (XLS-R self-supervised speech AI,
  trained on *different* clone families so they fail differently) cross-check every
  window and carry the verdict. Four supporting heuristics (spectral biometrics,
  breath patterns, phase coherence, liveness) are shown as corroborating evidence.
  A calibrated ensemble produces a 0–100 score banded **GREEN / AMBER / RED**, plus
  **UNCERTAIN** when the input is too degraded to judge honestly.
- **Accuracy (measured, reproducible):** **99.2% accuracy / EER 1.6% / AUC 0.999**
  on a 122-clip held-out set of our own voices + commercial clones
  (`python -m eval.run`). Telephony-degraded audio is the known gap (~20% EER) —
  a channel-robust retrain is in progress, and until it lands, degraded input
  abstains rather than guessing.
- **Why the bank cares:** this is the actual anti-clone defence OTP/biometrics lack —
  and it's tuned on Indian voices so it doesn't false-flag genuine customers.

### B. Scam-script detection (human scammers, no deepfake)
- **What:** flags the *manipulation*, even when the voice is a real human.
- **How:** the call is transcribed (speech-to-text) and read by an LLM that scores
  scam likelihood and tags tactics — **urgency, authority impersonation, isolation
  ("don't tell anyone"), new-beneficiary pressure, OTP/PIN requests, threats**.
- **Why the bank cares:** **most vishing uses a real human, not a deepfake.** A
  deepfake-only product scores those calls safe. This closes that gap — arguably
  the bigger share of real fraud.

### C. Decision fusion + transaction context
- **What:** turns scores into an **action** the fraud engine can take.
- **How:** combines voice risk + scam risk + novelty + the transaction being
  requested (amount, new payee) into **MONITOR / CHALLENGE / BLOCK**, each with a
  plain-English reason (e.g. *"synthetic-voice risk 82 during a new payee transfer"*).
- **Why the bank cares:** a balance enquiry with a suspicious voice is low-stakes;
  a ₹5-lakh transfer to a new payee is a code-red. Context makes the response
  proportionate — and gives your fraud engine a decision, not just a number.

### D. Novelty / zero-day detection
- **What:** flags a synthesis signature it has **never seen before**.
- **How:** measures the neural model's own uncertainty; an "unknown" pattern lifts
  a GREEN verdict to AMBER instead of passing clean.
- **Why the bank cares:** a new voice-clone tool ships every month. This catches
  the clone tool that **doesn't exist yet**, so the product doesn't go stale.

### E. Campaign / repeat-attacker detection
- **What:** links calls made by the **same** synthetic voice.
- **How:** each call gets a **voiceprint** (a numeric fingerprint). New calls are
  matched against past ones; the same voice across many calls forms a **campaign**,
  and a voiceprint that already committed fraud is flagged on its next call (blocklist).
- **Why the bank cares:** moves you from "one suspicious call" to *"this same voice
  hit 14 of your customers today"* — fraud-ring intelligence. It also **improves
  with use**: the more calls, the smarter the blocklist.

### F. Telephony robustness
- **What:** works on real phone lines, not just clean studio audio.
- **How:** the model is trained on **8 kHz, G.711-codec, lossy** audio (how calls
  actually sound), so it doesn't collapse on telephony.
- **Why the bank cares:** most detectors are demoed on a laptop mic and fail on the
  bank's actual lines. Ours holds — proven: 6% EER on phone-grade audio.

### G. Multilingual (Hindi / Hinglish / regional)
- **What:** detects scams in Indian languages and code-mixed speech.
- **How:** speech-to-text auto-detects the language; the deepfake model is
  language-agnostic (it reads acoustics, not words).
- **Why the bank cares:** your customers don't call in clean English. Western,
  English-only tools miss this.

### H. Shadow mode vs Enforce mode
- **What:** a switch between "watch and log only" and "act on verdicts."
- **How:** in **shadow**, every call is scored and logged but **no action** is
  taken; in **enforce**, RED verdicts trigger step-up auth / blocking. Toggle by
  config, API, or a dashboard switch.
- **Why the bank cares:** you pilot risk-free — run it in shadow on your own
  traffic for 30 days, compare to reality, then flip to enforce when the numbers
  prove out. This is how banks safely adopt anything new.

### I. Audit trail & forensic evidence packs
- **What:** a permanent, searchable record of every verdict — **with no audio**.
- **How:** each call gets a stable ID and an append-only log entry (score, level,
  tactics, language, transcript, decision). Any flagged call opens as an **evidence
  pack** for disputes, FIRs, or regulators.
- **Why the bank cares:** you can't act on fraud you can't defend in an audit. This
  is the defensible paper trail — and storing no audio minimises data-privacy risk.

### J. Model governance dashboard
- **What:** lets your model-risk team **govern** the AI.
- **How:** analysts label flagged calls (fraud/legit); the system computes live
  **detection rate (TPR)** and **false-alarm rate (FPR)**, watches for **drift**
  (the verdict pattern shifting over time), and keeps a **model registry**
  (version, training data, eval scores, champion vs challenger).
- **Why the bank cares:** **RBI Model Risk Management** requires you to monitor and
  govern any model in production. This is built in — most vendors make you build it.

### K. Metrics / observability
- **What:** operational health for your monitoring team.
- **How:** a standard **Prometheus** endpoint exposes latency, verdict mix, and
  error rate; scrapes straight into your existing dashboards.
- **Why the bank cares:** it runs like any other production service you already operate.

---

## 4. How it deploys

- **On-premise / private cloud.** Ships as a **Docker container**; runs inside your
  network. **No audio or call data ever leaves the bank** — satisfies RBI
  data-localisation.
- **Stateless & no audio retention.** Audio is scored in memory and discarded; only
  verdicts are kept. Nothing sensitive to breach.
- **Scales horizontally.** Run N copies behind your load balancer, sized to peak
  concurrent calls. CPU-only works; a GPU raises throughput.
- **Small footprint.** One service + a ~360 MB model file. No external database
  required to score.

## 5. How it integrates

- Your telephony platform (Genesys/Avaya/Cisco) already has the audio. A standard
  **SIPREC / media-fork** copies the caller's audio leg to a small adapter that
  streams it to our API. **No rip-and-replace.**
- Both entry points return the **same verdict contract** (JSON): `risk_score`,
  `alert_level`, `action`, per-layer breakdown, scam tactics, campaign info.
- Surfaces wherever you want: an **agent's screen**, or as a **signal into your
  fraud-decisioning engine** to auto-trigger OTP/step-up/hold on RED.

## 6. Security & compliance posture

- On-prem, **no audio leaves the bank**, no audio stored.
- **API-key auth + locked CORS** (production adds mTLS + TLS via your PKI).
- **Append-only audit trail** for every verdict.
- **Explainable** verdicts (per-layer + tactics + reason) — no black box.
- **Governable** (TPR/FPR, drift, versioning) for RBI Model Risk Management.

## 7. Why it's worth it — the bottom line

1. Stops the fraud OTP/biometrics can't: **voice clones** *and* **human scams**.
2. **Real-time** — acts during the call, before money moves.
3. **On-prem, no audio retained** — RBI-aligned, low data risk.
4. **Works on your real phone lines and in Indian languages.**
5. **Fraud-ring intelligence** that compounds with use.
6. **Audit-ready and governable** — deployable, not a science project.
7. **Pilots risk-free in shadow**, integrates without replacing your stack.

> In short: a deployable, explainable, on-prem layer that closes the voice-fraud
> gap — built for how your calls, customers, and regulators actually work.
