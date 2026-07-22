# PPT Build Context — everything a teammate needs to build the finals deck

Single briefing to build the finals PowerPoint. Tells you **what's true and safe
to claim**, **what's in flight (present as roadmap, never as done)**, the story,
and which existing assets to reuse. Read top to bottom once.

> **Golden rule for honesty:** anything in the **SHIPPED & MEASURED** section can
> go on a slide as fact. Anything in **IN FLIGHT** must be framed as roadmap /
> "in progress" — a panel that catches an unshipped claim presented as done will
> discount everything else. Our whole edge is that our numbers are real.

---

## 0. Reuse, don't rebuild

| Asset | Use for |
|---|---|
| **FINALS-DECK-BRIEF.md** | the master brief — story, per-feature detail, slide outline. **§4 is the CANONICAL numbers table.** |
| **PRESENTATION-SCRIPT.md** | speak-from narration, slide by slide (already corrected to current numbers) |
| **TECHNICAL-OVERVIEW.md** | deep architecture/algorithm detail for the technical slides + Q&A |
| **THREAT.md** | the "why the bank is exposed without us" threat-model slide |
| **DEMO-RUNBOOK.md** | the live-demo section (verified clips, channel rules) |
| `presentation.html`, `architecture.html`, `orchestration.html` | existing branded slides + diagrams — screenshot or mirror them |
| `Dhwani-Kavach_ERROR404.pptx` (via `tools/build_pptx.py`) | the existing 26-slide deck — regenerate, don't start from zero |

**Do NOT reintroduce old numbers.** If any doc, old slide, or memory says
"4% clean / 6% phone EER", "0.80 neural weight", "wav2vec2-base", or "AUC 0.996 on
15/15" — it's retired. Use §1 below.

---

## 1. SHIPPED & MEASURED — safe to put on a slide

**Canonical numbers** (source: FINALS-DECK-BRIEF §4; `python -m eval.run ../Dataset_orig`):

| Metric | Value |
|---|---|
| **Full ensemble (deployed)** | **99.2% accuracy · EER 1.6% · AUC 0.999** on a 122-clip held-out set (61 real / 61 fake — own voices + commercial clones) |
| Neural-only (no heuristics) | 95.9% · EER 6.6% · AUC 0.989 |
| First verdict | ~3 s upload / ~4 s live (well inside the 10 s problem-statement budget) |
| Telephony | ~20% EER — **known weakness** (see IN FLIGHT) |

**Architecture (as deployed today):**
- **Two independent neural detectors** (`aasist` = XLS-R-300M + W2VAASIST head;
  `clone_v3` = clone-specialist), 0.45 each = 0.90; 4 acoustic heuristics = 0.10
  (evidence only, measured near-noise).
- **Scam-script layer** — Whisper STT → LLM (`meta/llama-3.1-8b-instruct` on NVIDIA
  NIM) → 6 social-engineering tactics. Catches *human* scammers; multilingual.
- **Quality abstention** — degraded input → UNCERTAIN, never a false all-clear.
- **Replay-channel gate** — loudspeaker-injected clone → forced CHALLENGE.
- **Voice OTP (`/verify`)** — speak-back digits: ASR content match + deepfake check,
  now **English + Hindi** (Devanagari, numerals, romanized).
- **Live-call demo (`/call`)** — two-tab WebRTC, digital audio tap (the real
  integration channel, no over-the-air loophole).
- **Decision fusion** — rule-based MONITOR/CHALLENGE/BLOCK + transaction context.
- **Bank product surfaces** — `/cases` (evidence packs), `/campaigns` (fraud-ring),
  `/governance` (TPR/FPR, drift, registry), `/metrics` (Prometheus).
- **Novelty/zero-day** — model uncertainty + cross-detector disagreement.

**Differentiators to lead with (all shipped):**
1. **Human scam detection** — flags a real human reading a scam script; no
   deepfake-only competitor can.
2. **Two-sided** — protects the bank from fake customers *and* customers from fake
   bank-callers.
3. **The generalization story** — v1 single model: <0.5% dev EER but **40% EER /
   AUC 0.63 on real clones**; dual detectors + calibration: **99.2% / AUC 0.999**.
   "Never trust one detector's leaderboard number."

---

## 2. IN FLIGHT — present as roadmap / "in progress", NOT as done

| Item | Status | How to say it on a slide |
|---|---|---|
| **Channel-robust retrain** (telephony/reverb/noise/**speaker-replay** aug) | training on Kaggle; smoke-validated, full run pending | "channel-robust retrain **in progress** — measured the gap (telephony ~20% EER, own voices through a speaker ~0.48 AUC), training to close it." Do **not** quote a post-retrain number until it's measured and deployed. |
| **Voice OTP hardening** | demo-grade `/verify` shipped; persistence / speaker-match / real OTP delivery on `feature/voice-otp-verification` | "Voice OTP is live as a parallel verification path; productionizing enrolment + delivery." |
| **Customer voice-identity** (is it *this* customer?) | not built — anti-spoofing only | roadmap item, honest gap |
| **mTLS + horizontal scale-out** | not shipped (API-key gated; single-instance state) | roadmap; say "API-key gated today, mTLS on the hardening path" |
| **Embedding-based novelty / OOD** | heuristic today | roadmap |
| **Campaign store at scale** (FAISS/pgvector) | linear scan today | roadmap |

**The measured gap you CAN show as a strength** (it's your most credible slide):
"Public benchmark AUC 1.00 · our own voices through a real phone ~0.48 — the gap
every team hides. Here's ours, measured, and the retrain closing it."

---

## 3. Suggested deck spine (adapt to the time slot)

Follows the panel's framework (problem · uniqueness · benchmarks · moat ·
deployability + demo/TRL/roadmap + Q&A). Detailed outline: FINALS-DECK-BRIEF §10.

1. Problem — cloning broke voice biometrics + OTP; metadata is spoofable (THREAT.md)
2. Solution overview — one decision (MONITOR/CHALLENGE/BLOCK) in ~4 s, on-prem
3. Uniqueness — human scam detection + two-sided + channel gates
4. Architecture — dual detectors + scam LLM + fusion (architecture.html)
5. The generalization lesson — the 40%→99.2% story (§1.3) ← strongest slide
6. Benchmarks — canonical numbers (§1), honest telephony gap + retrain
7. Threat model — exposure without us (THREAT.md)
8. Deployability — SIPREC/on-prem/no-audio-retained/governance
9. Demo — DEMO-RUNBOOK order (upload clone → RED; scam script → CHALLENGE; Voice
   OTP reject; bank pages)
10. TRL 5→6, roadmap (§2), timeline
11. Q&A — FINALS-DECK-BRIEF §12 + the honest-limitations slide

## 4. Q&A landmines (have answers ready)
- "How do you know it works on real calls?" → the honest telephony/replay numbers +
  the retrain, not a dodge.
- "What about a clone tool you haven't seen?" → novelty + our own red-team finding
  (a generator that partially evades us) feeds the retrain — the loop is the moat.
- "Is it production-ready?" → detection + decision are real; mTLS, scale-out, SIPREC
  adapter, customer-identity are marked roadmap. TRL 5→6.
- "Adversarial evasion?" → untested, named openly — the frontier.

---

*If a number on your slide doesn't match FINALS-DECK-BRIEF §4, §4 wins — fix the
slide, and if the truth changed, fix §4 first then everything else.*
