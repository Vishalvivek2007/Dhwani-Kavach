> **⛔ ARCHIVED — executed, kept for history.** These phases shipped; this
> plan no longer reflects current state (it predates the dual-detector
> architecture and the measured numbers). For where the project stands, see
> [HANDOFF.md](../../HANDOFF.md) and [FINALS-DECK-BRIEF.md](../../FINALS-DECK-BRIEF.md).

---

# Dhwani-Kavach — Competitive-Edge Build Plan (Phases G–K)

Build plan for the 7 features in [COMPETITIVE-EDGE.md](COMPETITIVE-EDGE.md).
Phases A–F (the shield) are done; this continues the lettering.

**Key idea — two parallel tracks.** Telephony retraining (#1) is the long pole
(data + Kaggle GPU + eval). Kick it off **first and let it run in the
background** while the engineering features (G, I, J) are built in the repo.
Don't serialize behind it.

Anchor: finals ~early Aug (~5 weeks). Efficiency rules from the shield apply —
reuse the streaming pipeline, the Nemotron/Whisper stack, `/metrics` + `/cases`
+ the audit log; mock the bank side; cheapest version first.

```
Week:        1        2        3        4        5
ENG track:  [G quick wins][ I campaign ][ J governance ][ K identity? ]
ML  track:  [========== H telephony retrain (background) ==========]
```

---

## PHASE G — Quick wins  (week 1)  ← start here
Three low-effort, high-signal features, no ML retraining. Ship fast.

### G1 — Shadow mode (#5)
**Goal:** score every live call and log verdicts **without acting** — banks pilot
in shadow before enforcement.
- Add `DHWANI_SHADOW` env flag (+ optional per-request override).
- When on: compute the full verdict, mark `enforced=false`, still audit + metric it.
- Surface a "SHADOW" badge in the UI and a `mode` field in the response.
- ✓ check: with shadow on, response has `enforced=false` and the action is logged.
**Effort:** low (a flag; audit already records everything).

### G2 — Hinglish / multilingual (#2)
**Goal:** prove the scam + deepfake layers work on Hindi / code-mixed calls.
- Confirm Whisper auto-detect (`language=None`) + Nemotron handle Hindi/Hinglish.
- Surface the detected language in the verdict + UI.
- Build a small Hinglish/regional scam-vs-benign eval set; record results.
- ✓ check: a Hindi scam transcript → tactics detected; benign Hindi → clean.
**Effort:** low (mostly verification + a test set + one UI field).

### G3 — Forensic evidence pack (#7)
**Goal:** a defensible per-call report for disputes / FIRs / regulators.
- `GET /api/cases/{id}` + `GET /cases/{id}` → report: timestamp, risk, layers
  that fired, transcript, tactics, fused decision (no audio).
- "Download report" link from the `/cases` list.
- ✓ check: endpoint returns a complete report for a known call id.
**Effort:** low-medium (extends `/cases`; needs a stable call-id in the audit log).

**Phase G deliverable:** shadow-mode pilot story + multilingual proof + audit
evidence packs — three procurement signals, ~1 week.

---

## PHASE H — Telephony-grade robustness  (#1) — START IN PARALLEL, week 1–3 (ML track)
**Goal:** works on real 8 kHz, codec-degraded, lossy phone lines — the knockout
that fails every laptop-mic competitor.
- H1 Extend the augmentation pipeline: 8 kHz resample, G.711/G.729/AMR codec
  passes, packet-loss/jitter, call-centre noise.
- H2 Build/curate an **8 kHz telephony eval set** (clean + degraded, real + fake).
- H3 Retrain wav2vec2 with telephony augmentation (Kaggle T4). Save versioned weights.
- H4 Resample-aware front end so 8 kHz input is handled at inference.
- H5 Validate: EER on the telephony eval set; compare vs the current model.
- ✓ check: same clone through a phone-codec filter is still caught;
  telephony-eval EER beats the un-augmented baseline.
**Effort:** medium-high; **long calendar time** (data + GPU) → why it starts first.
**Demo angle:** play a clone through an 8 kHz codec → still RED.

---

## PHASE I — Fraud-campaign / repeat-attacker detection  (#3)  (week 2–3)
**Goal:** "the *same* synthetic voice hit 14 customers today" — a data network
effect competitors can't replicate.
- I1 Expose the wav2vec2 utterance embedding from the detector (already computed).
- I2 Store per-call embeddings (sqlite/parquet — stdlib/lightweight).
- I3 Nearest-neighbour clustering: link calls whose voiceprints match; maintain a
  fraudster-voiceprint blocklist; instant-flag a known-bad voiceprint.
- I4 Campaign view: `/campaigns` — clusters with hit counts + linked calls.
- ✓ check: two clips of the same voice cluster together; a different voice doesn't;
  a blocklisted voiceprint is flagged on the next call.
**Effort:** medium (embeddings exist; add storage + k-NN). Depends on I1 only.
**Demo angle:** two different "customer" calls flagged as the same underlying voice.

---

## PHASE J — Model governance & drift dashboard  (#4)  (week 3–4)
**Goal:** the procurement unlock — banks can't deploy what they can't govern (RBI MRM).
**Depends on:** G1 (shadow data) + G3 (labeled/reviewed cases) for ground truth.
- J1 Analyst review/label on a case (fraud / not-fraud) → feedback store.
- J2 Time-series metrics: FPR/TPR, verdict mix, scam-vs-voice contribution over time.
- J3 Drift signal: alert when the verdict distribution shifts vs a baseline window.
- J4 Model registry: version, training data sheet, eval scores, champion/challenger.
- J5 Dashboard page over `/metrics` + the feedback store.
- ✓ check: labeling cases updates FPR/TPR; a synthetic distribution shift raises the drift alert.
**Effort:** medium (foundation = `/metrics` + audit log + G3).

---

## PHASE K — Customer voice-identity + liveness  (#6)  (stretch / post-finals)
**Goal:** not just "is it synthetic" but "is it *this customer*" — closes the
voice-biometric spoofing gap.
- K1 Consent + voiceprint enrollment flow.
- K2 Speaker-verification model (ECAPA/pyannote) → match score vs enrolled print.
- K3 Fuse identity + anti-spoof + active liveness challenge into the decision.
- ✓ check: enrolled speaker matches self, rejects a different speaker and a clone.
**Effort:** medium-high (enrollment + consent design + a new model). Stretch only.

---

## Sequencing & fallback
1. **Day 1:** kick off **H** (telephony data/training) so it bakes in the background.
2. **Week 1:** ship **G** (shadow + Hinglish + evidence) — fast procurement signals.
3. **Week 2–3:** **I** (campaign) — the compounding moat.
4. **Week 3–4:** **J** (governance) — once shadow + labels exist.
5. **K** only if H/I/J land early.

**If time gets tight:** G + H alone are the two biggest competitor knockouts
(shadow/multilingual story + works-on-real-phone-lines). Ship those; treat I/J/K
as the post-finals moat.
