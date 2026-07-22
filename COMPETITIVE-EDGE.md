# Dhwani-Kavach — Competitive Edge & Feature Strategy

Deep analysis of what to add to beat teams shipping "the same product"
(deepfake-voice detection for banks). Framed around **where competitors lose a
bank deal**, not features in a vacuum.

---

## 1. The core thesis

A deepfake detector is a commodity — any team can fine-tune wav2vec2/AASIST on
ASVspoof. Competitors will all claim "high accuracy." You don't win on the
model. You win on the **four places every commodity detector quietly fails**,
because that's where a bank's procurement team kills the deal:

1. **It dies on a real phone line.** Demos run on a clean laptop mic at 16 kHz.
   Real bank calls are 8 kHz, G.711/AMR-codec, packet-loss telephony. Models
   trained on clean audio collapse on telephony. **This is the #1 production
   failure** and the first thing a serious bank will test.
2. **It only catches deepfakes.** Most vishing is a *real human* scammer. A
   deepfake-only product scores the actual fraud GREEN. *(You already closed
   this with the scam-script LLM — keep hammering it.)*
3. **It can't be governed.** Banks have Model Risk Management duties (RBI / Basel).
   No FPR/TPR-over-time, no drift monitoring, no versioning = can't go to prod.
4. **It flags real customers.** A high false-positive rate on genuine callers is
   worse than useless — it destroys customer trust and floods the fraud desk.

Build where they lose. The features below are ranked by **(deal impact) ×
(feasibility given what you already have)**.

---

## 2. Tiering — know what NOT to compete on

| Tier | Capability | Stance |
|------|-----------|--------|
| **Table stakes** | A deepfake classifier; an accuracy number | Don't lead here — everyone claims it |
| **Your current moat** | Scam-script LLM, on-prem, explainable 5-layer, fused MONITOR/CHALLENGE/BLOCK, novelty/zero-day, audit trail, /cases, /metrics | Lead with these |
| **Next moat (this doc)** | Telephony-grade, multilingual, campaign detection, governance, shadow-mode | Build these to be uncatchable |

---

## 3. The features that win — ranked

### #1 — Telephony-grade robustness  ★ highest deal impact
**What:** preprocess + train for 8 kHz, G.711/G.729/AMR codecs, packet loss,
jitter, and call-centre background noise. Add codec/8 kHz augmentation to the
training set and a resample-aware front end.
**Why it beats competitors:** their laptop-mic demo will *fail the bank's own
phone-line test*. You passing it is a knockout. This is the single most
credible thing you can say to a banker: *"it works on your actual lines, not
just a clean mic."*
**Bank need:** non-negotiable — real calls are telephony.
**Effort:** medium (you already have an augmentation pipeline; extend it with
codec degradation and add an 8 kHz eval set).
**Demo angle:** play the same clone through a phone-codec filter; show it still
catches it.

### #2 — Multilingual / Hinglish coverage  ★ near-free, India-specific
**What:** handle Hindi, English, code-mixed Hinglish, and major regional
languages on the scam-script layer.
**Why it beats competitors:** Western detectors and English-only NLP fail on
Indian banking calls. You largely **already have this** — Whisper auto-detects
language and Nemotron reasons in Hindi/English; the acoustic deepfake model is
language-agnostic. So this is mostly a *positioning + a Hinglish test set*, not
a big build.
**Bank need:** direct fit for UCO's actual customer base.
**Effort:** low (verify + a curated Hinglish/regional eval; surface detected
language in the UI).
**Demo angle:** run a Hindi/Hinglish scam call live → tactics still light up.

### #3 — Fraud-campaign & repeat-attacker detection  ★ compounding moat
**What:** fingerprint each call's voice embedding; cluster across calls to flag
"the *same* synthetic voice hit 14 customers today" and maintain a fraudster
voiceprint blocklist.
**Why it beats competitors:** this is a **data network effect** — the more the
bank uses it, the smarter it gets, and a competitor can't replicate the data.
Moves you from "per-call score" to "fraud-ring intelligence," which is what
fraud teams actually chase.
**Bank need:** campaign-level detection + blocklisting is high-value.
**Effort:** medium (the wav2vec2 embeddings already exist — add storage +
nearest-neighbour clustering).
**Demo angle:** show two different "customer" calls flagged as the *same*
underlying synthetic voice.

### #4 — Model governance & drift dashboard  ★ procurement-winner
**What:** a dashboard of FPR/TPR over time, verdict drift, model version,
champion/challenger, and a per-model data sheet. Extend `/metrics` + `/cases`.
**Why it beats competitors:** banks *cannot* deploy a model they can't govern
(RBI Model Risk Management). No hackathon team will have this. It signals
"production-grade vendor," not "student project."
**Bank need:** mandatory for go-live.
**Effort:** medium (you have /metrics + audit log as the foundation; add labels
+ time-series).
**Demo angle:** "here's how your model-risk team monitors us in production."

### #5 — Shadow-mode pilot capability  ★ how you actually land the deal
**What:** a mode that scores every live call and logs verdicts **without taking
action** — so the bank measures real detection + false-positive rates on their
own traffic before trusting it to act.
**Why it beats competitors:** it's the *sales motion* banks demand — prove value
risk-free first. Offering it shows you understand how banks buy.
**Bank need:** every bank pilots in shadow before enforcement.
**Effort:** low (a config flag; the audit log already records everything).
**Demo angle:** "run us in shadow for 30 days, then turn on enforcement."

### #6 — Customer voice-identity + liveness fusion
**What:** beyond "is it synthetic," verify "is it *this customer's* voice" via a
voiceprint enrolled at consent, fused with active liveness challenges.
**Why it beats competitors:** combines anti-spoofing + identity — closes the gap
that voice biometrics alone leave.
**Bank need:** strong for phone-banking authentication.
**Effort:** medium-high (enrollment + speaker-verification model + consent flow).

### #7 — Forensic evidence pack & regulatory reporting
**What:** per flagged call, a downloadable report (spectrogram, layers that
fired, transcript, tactics, decision) for disputes / FIRs / suspicious-activity
reports.
**Why it beats competitors:** banks need *defensible evidence*, not just a score
— for chargebacks, law enforcement, and regulators.
**Effort:** low-medium (extend `/cases` into a per-call report).

---

## 4. What actually wins a bank deal (procurement reality)

Judges/bankers score on these — make sure each has an answer:

| Buying criterion | Your answer |
|------------------|-------------|
| Accuracy **and low false positives** | 99.2% acc / EER 1.6% measured on our own held-out voices + commercial clones; two independent detectors so one model's blind spot doesn't clear a fraud |
| Works on **our** infrastructure | On-prem Docker, telephony-grade (#1), no audio leaves the bank |
| Compliance | RBI data-localisation, DPDP Act posture, audit trail, no-audio-retention, governance (#4) |
| Catches **real** fraud | Scam-script LLM catches human scammers; campaign detection (#3) |
| Integrates without rip-and-replace | SIPREC media-fork + REST/WS API (INTEGRATION.md) |
| De-risked rollout | Shadow mode (#5), then enforcement |
| Explainable / auditable | 5-layer breakdown, /cases, evidence pack (#7) |
| Total cost / footprint | Single stateless container, CPU-viable, scales horizontally |

---

## 5. Recommendation

- **For the next review / finals (build):** **#1 telephony robustness** and
  **#2 Hinglish** — they are the two most credible, India/bank-specific knockouts
  and #2 is nearly free. Add **#5 shadow mode** (a one-flag change, huge sales
  signal).
- **Roadmap (post-finals, the durable moat):** **#3 campaign detection** (data
  network effect) and **#4 governance dashboard** (procurement unlock).
- **Opportunistic:** **#7 evidence pack** (cheap, extends /cases).
- **Heavier / later:** **#6 customer identity** (real, but needs enrollment +
  consent design).

## 6. Pitch lines to steal

- *"Every other detector works on a clean mic and dies on a phone line. Run us on your actual call audio."*
- *"They detect deepfakes. We detect fraud — including the human scammer with no deepfake at all."*
- *"We don't just score a call. We see the campaign: the same synthetic voice hitting fourteen of your customers."*
- *"Run us in shadow for 30 days. Look at the numbers on your own traffic. Then decide."*
- *"Your model-risk team can govern us from day one — drift, false-positive rate, versioning, all on a dashboard."*
