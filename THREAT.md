# Threat Model — Voice-Spoofing Attacks on a Bank

The bank's exposure to voice-spoofing fraud **with no audio-forensics layer in
place**, and where each of Dhwani-Kavach's layers intervenes. Written as a
defensive threat taxonomy (attack → current-control gap → our layer), at the
abstraction level of a fraud-risk review — not an operational playbook.

## The three trust assumptions attackers defeat
- **A1 — "the voiceprint proves identity"** (voice-biometric auth)
- **A2 — "an agent can tell a real caller from a fake"** (call-centre verification)
- **A3 — "OTP / knowledge factors confirm intent"** (2FA, security questions)

Cheap generative cloning has quietly invalidated A1 and A2; A3 was always
socially engineerable. That inversion is why this product exists.

---

## Tier 1 — highest danger (cheap, scalable, defeats a primary control)

| # | Vector | Mechanism (taxonomy) | Defeats | Feasibility | Caught today | Our layer |
|---|---|---|---|---|---|---|
| 1 | **Synthetic-voice biometric defeat** | seconds of harvested target audio → cloned sample that matches the enrolled template | A1 | **High** — ~zero cost, repeatable | nothing | dual neural detectors (core case) |
| 2 | **Agent-assisted transfer via clone** | call the contact centre as the "customer," clone speaking, to authorise a transfer / add payee | A2 | **High**, scales across agents | nothing reliable | real-time RED on the agent screen, mid-call |
| 3 | **Human scam-script, NO deepfake** | a real human coerces a genuine customer, or impersonates the bank — voice 100% real | A2 + A3 | **Very high** — no tech needed | nothing automated | scam-script LLM (the differentiator no deepfake-only tool has) |

**#3 is the single most dangerous vector**: free, high-volume, largest share of
real vishing loss, and *invisible to every pure-deepfake detector on the market.*
Lead the threat narrative with it, not with the flashy clone.

---

## Tier 2 — serious, higher cost or narrower window

| # | Vector | Mechanism | Defeats | Feasibility | Our layer |
|---|---|---|---|---|---|
| 4 | **Real-time voice conversion** | attacker speaks; a streaming model re-timbres to the target voice live, so it can answer challenges | A1/A2 + naive liveness | **Medium** (setup/latency) | detector sees conversion artifacts; Voice-OTP timing/latency analysis. *Honest: the hardest case — retrain frontier.* |
| 5 | **Loudspeaker / over-the-air replay** | a pre-made clone is played into a live call toward the IVR/agent | A1/A2; also beats most artifact detectors (air hop smears artifacts) | **Medium-high** | **replay-channel gate** forces CHALLENGE even on a clean-reading score |
| 6 | **SIM-swap / caller-ID spoof + clone** | take over / spoof the number so metadata "confirms" the customer, then clone the voice — two factors fall at once | metadata-trust model + A1 | **Medium** setup, **very high** impact | we ignore metadata and judge the *audio* — a spoofed number with a clone still gets scored |

---

## Tier 3 — situational or higher-skill

| # | Vector | Mechanism | Feasibility | Note |
|---|---|---|---|---|
| 7 | **Enrolment poisoning** | enrol attacker/synthetic voice against the victim's account at onboarding → later "matches" are legitimately theirs | Low-med, but **permanent** | detection at *transaction* time still flags anomalies; real fix is hardening enrolment (defence-in-depth beyond us) |
| 8 | **Recorded-snippet splicing** | stitch genuine captured fragments ("yes", account no.) to satisfy a scripted IVR | Low-med, brittle | phase-coherence + neural flag splice seams; dynamic-digit Voice-OTP defeats it by construction |
| 9 | **Adversarial-perturbation evasion** | imperceptible perturbations tuned to push a *known detector* toward "real" — an attack on **us** | Low today, rising | intellectual honesty: our documented untested limitation; naming it first in Q&A reads as rigour |
| 10 | **Insider / vishing-the-agent** | social-engineer the helpdesk, or a bribed insider bypasses the check entirely | Variable | no audio product fully solves the human layer; we contribute the audit trail that makes abuse *detectable after the fact* |

---

## Synthesis — what this tells the panel

1. **Exposure is worst where controls feel strongest.** Voice biometrics (A1) and
   "the call is from the right number" (metadata) are the two most-trusted controls
   and the two most cleanly defeated (#1, #6). A review that only hardens OTP is
   fighting the last war.
2. **The vectors cluster into three defences, and we have a layer for each:**
   *is the voice synthetic* (detectors) · *is the script a scam* (LLM) · *is the
   channel trustworthy* (replay + quality gates). A point solution — just a deepfake
   classifier, or just voice biometrics — leaves two-thirds of the surface open.
3. **Be honest about #4 and #9** (live conversion, adversarial evasion): they're the
   real frontier, and the retrain-loop + red-team pipeline is the answer to "what
   about attacks you haven't seen." That honesty convinces more than claimed
   total coverage.

> Scope note: this document is a defensive threat model for a fraud-detection
> product. It deliberately stays at the taxonomy level — attack classes, enabling
> factors, and control gaps — not step-by-step attack instructions.
