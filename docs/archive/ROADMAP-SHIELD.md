> **⛔ ARCHIVED — executed, kept for history.** These phases shipped; this
> plan no longer reflects current state (it predates the dual-detector
> architecture and the measured numbers). For where the project stands, see
> [HANDOFF.md](../../HANDOFF.md) and [FINALS-DECK-BRIEF.md](../../FINALS-DECK-BRIEF.md).

---

# Dhwani-Kavach → Real-Time Call-Fraud Shield — Build Plan

The repositioning: stop shipping a *deepfake detector* (commodity, narrow).
Ship a **real-time call-fraud shield** where the deepfake model is one sensor.
The reason: most bank vishing uses a **real human scammer**, not a deepfake — a
deepfake-only product scores those calls GREEN and misses the money-loss event.

Two deadlines:
- **Review #1 — Jul 2** (3 days out): win with what exists + positioning + one cheap signal.
- **Finals — ~early Aug** (~1 month): build the features that make you indispensable + futureproof.

Efficiency rules (apply throughout): reuse the existing streaming WS pipeline and
the already-wired Nemotron/NIM API; mock the bank side (transactions, telephony);
rule-based fusion before ML; cheapest version of each layer first.

---

## PHASE A — Lock the Jul 2 review  (now → Jul 2)
**Goal:** bulletproof live demo + sharpened narrative. Minimal build, maximum polish.

| # | Step | Effort |
|---|------|--------|
| A1 | **Back up the model** (`deepfake_w2v.pt`, 360 MB, local-only & gitignored) — USB + cloud + Kaggle Save Version. Biggest single risk. | 10 min |
| A2 | **Reframe the pitch** to "call-fraud shield / we catch the fraud others miss." Lock the live demo script: judge speaks → GREEN, play a clone → RED, no carryover. | — |
| A3 | **Audit log** (~30 lines): every verdict appended to JSONL (call-id, ts, score, level — no audio). High compliance signal, near-zero effort. | 1 hr |
| A4 | **Full dry-run rehearsal** ×3 on the laptop. Verify silence→GREEN, mp3 works, fresh socket per run. | 1 hr |

**Deliverable:** a demo that can't crash + a narrative that separates you from the pack.
**Do NOT** start ML features before Jul 2. No time, high risk.

---

## PHASE B — Scam-script layer  (Week 1, post-review)  ← the reframe feature
**Goal:** catch human-scammer vishing, not just deepfakes. Highest ROI; infra already exists.

| # | Step | Notes |
|---|------|-------|
| B1 | **Add STT to the stream.** `faster-whisper` (base/small, CPU-ok) over the rolling audio; accumulate a transcript. | new dep, small |
| B2 | **Scam-pattern LLM call** via the existing Nemotron/NIM client. Prompt returns `scam_score 0–100` + tactics detected: urgency / authority-impersonation / isolation / new-beneficiary. **Throttle** (every ~3–4 s or on transcript growth) for latency + cost. | reuse NIM |
| B3 | **New ensemble layer** `scam_script` with its own weight; tactics flow into `layer_breakdown`. | extend ensemble.py |
| B4 | **UI**: show detected tactics as chips in LiveMonitor. | frontend |
| ✓ | **Self-check**: scripted scam transcript (real voice) → high scam score; benign chat → low. | assert-based |

**Deliverable:** flags a real-human scam call with **no deepfake present** — the thing no competitor does.

---

## PHASE C — Decision fusion + context  (Week 2)
**Goal:** turn scores into an *action* a fraud engine can take. Banks pay for decisions, not scores.

| # | Step | Notes |
|---|------|-------|
| C1 | **Transaction-context input** on the API (amount, new_beneficiary, channel). Mock-able for demo. | optional field |
| C2 | **Fusion rule** → action: `MONITOR / CHALLENGE / BLOCK` from (deepfake + scam + txn-risk). Rule-based, explainable — **not** ML. | small module |
| C3 | **UI**: show recommended action + the one-line "why". | frontend |
| ✓ | **Self-check**: deepfake on "balance" → MONITOR; deepfake/scam on "₹5L to new payee" → BLOCK. | assert-based |

**Deliverable:** actionable verdicts; the line from "interesting" to "needed."

---

## PHASE D — Futureproofing: zero-day / novelty detection  (Week 2–3)
**Goal:** catch synthesis signatures never seen before. This *is* the "futureproof" answer.

| # | Step | Notes |
|---|------|-------|
| D1 | Offline: compute the distribution of wav2vec2 embeddings for known classes (centroids + cov). | one-time |
| D2 | At inference: novelty = distance to nearest centroid (Mahalanobis/cosine). **v1 fallback**: softmax entropy / low max-prob = "uncertain". | cheap v1 first |
| D3 | "Unknown synthesis signature" raises AMBER+ even when the classifier is unsure. | ensemble hook |
| ✓ | **Self-check**: feed OOD audio (a TTS not in training, or noise) → high novelty; in-dist real/clone → low. | assert-based |

**Deliverable:** catches the clone tool that doesn't exist yet. Pairs with the
self-learning Security Sentinel / threat library (confirmed frauds feed back).

---

## PHASE E — Productionize for bank integration  (Week 3–4)
**Goal:** make the on-prem claim in INTEGRATION.md demonstrable.

| # | Step |
|---|------|
| E1 | **API-key auth** + lock CORS to bank origins; TLS-ready. |
| E2 | **Dockerfile + compose** (backend + frontend), health/readiness probes, resource limits. |
| E3 | **Prometheus metrics** (latency, verdict mix, error rate). |
| E4 | Extend the A3 audit log into a simple **case view** (flagged calls list). |

**Deliverable:** a container a bank PoC could actually run inside its network.

---

## PHASE F — Stretch: internal-voice impersonation  (only if E done before finals)
**Goal:** alert when a *known bank-staff voice* (RM, official) is being cloned.
Speaker-verification model + a small enrollment set → alert on protected-voice clone.
Nobody else will pitch this. Stretch only — don't jeopardize A–E.

---

## Sequencing logic (why this order)
1. **A first, alone, before Jul 2** — the review is won by proof + story, not new code.
2. **B before everything else** — biggest reach, lowest effort (Nemotron already wired), and it *reframes the whole product*. If you build one thing, build B.
3. **C next** — makes B and the deepfake score *actionable*; cheap.
4. **D** — the explicit futureproofing claim; cheap v1 exists.
5. **E** — turns slideware integration into a runnable container.
6. **F** — stretch, only on spare time.

**If the month gets tight, ship A → B → D and skip/mock C and E.** B+D alone move
you from "another detector" to "catches fraud others miss, including attacks that
don't exist yet."
