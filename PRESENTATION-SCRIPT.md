# Dhwani-Kavach — 40-Minute Presentation Script (Team ERROR 404)

Speak-from guide for the IIT Kharagpur panel. Deck: `Dhwani-Kavach_ERROR404.pptx`
(26 slides) / `presentation.html`. Talking points are cues, **not** to be read
verbatim — speak naturally, look at the panel.

**Time budget (~40 min):** Slides ≈ 24 min · Live demo ≈ 8 min · Q&A ≈ 8 min.
Aim ~45–60s per content slide; slow down on the ★ deep-dive slides.

**Delivery tips:** open confident and slow; repeat three words — **live, on-prem,
decision**; when you hit a limitation, say it *proudly* (it reads as maturity);
end every technical answer by tying back to the bank's benefit.

---

## PART 1 — SLIDES (≈24 min)

### Slide 1 — Title  [0:30]
- "Good morning. We're **Team ERROR 404**, and this is **Dhwani-Kavach** — a
  real-time call-fraud shield for banks."
- "In one line: it listens to a live banking call and, in about four seconds,
  says Monitor, Challenge, or Block. It catches AI voice clones **and** human scam
  calls, and it runs entirely inside the bank's network."
- → "Let me start with why this problem is urgent."

### Slide 2 — Agenda  [0:30]
- Walk the six bullets in one breath. "Problem, our solution, a deep dive into
  every layer and the model, how we compare, deployability and honest limits, then
  a live demo and Q&A."
- → "First — the problem."

### Slide 3 — Problem statement  [1:30]
- "Voice has become a bank's weakest channel, for four reasons."
- Cloning is trivial — seconds of audio from a voice note or a recorded call, and
  you have a convincing clone that can authorise a transfer.
- **Key point:** "Most vishing doesn't even use a deepfake — it's a *real human*
  scammer pressuring a real customer. That's the larger share of losses."
- The money moves *during* the call — so detecting it afterwards is worthless.
- And it's at massive volume, across Hindi, English, code-mixed — humans can't screen it.
- Right card: "And the defenses banks have today don't close it — OTP gets read
  out under pressure, biometrics get fooled by a clone, agents can't hear a deepfake."
- → "So the threat really has two faces."

### Slide 4 — Two attack vectors  [1:15]
- "This is the crux of our design. There are two attacks, and most tools see only one."
- Left: synthetic voice — sounds like the customer, passes biometrics. Our **neural
  engine** handles this.
- Right: human social engineering — a scripted con, no deepfake, so deepfake-only
  tools score it *safe*. Our **scam-script LLM** handles this.
- "A real defense must cover **both**. Almost nobody does — that's our starting edge."
- → "Which led us to a different framing."

### Slide 5 — The insight  [1:00]
- "We stopped thinking of this as a deepfake detector. We built a **fraud shield**."
- "A detector is a commodity and it's narrow. The fraud that drains accounts is
  broader — clones and human scripts, on real phone lines, in Indian languages."
- "Our edge is everything a detector *isn't*: the decision, the deployment, and the
  intelligence around it. That's the through-line for the rest of this talk."

### Slide 6 — Solution overview  [1:00]
- "Here's the whole system in one line." Read the flow.
- "Audio comes in, runs through five detection concerns in parallel, they're fused
  with the transaction context into one action, and that goes to the agent or the
  fraud engine."
- Three numbers: **~4 seconds** to first verdict; **five layers plus an LLM**, fused
  and explainable; **zero** audio stored.
- → "Let me show you how it's put together."

### Slide 7 — Architecture / how it works  [1:15]
- "Two entry points, one engine — a live WebSocket stream for calls in progress,
  and REST upload for recordings; both hit the same detector."
- "It's **fail-safe by composition** — every advanced layer is additive. If speech-
  to-text or the LLM or even the model file is missing, that layer goes neutral and
  the core verdict still ships. Nothing is a single point of failure."
- "It stays real-time under load — inference runs off the event loop, and we only
  score the newest window so a slow CPU can't flood the client."
- "And every verdict is explainable — score, per-layer breakdown, tactics, reason."
- → "Now the deep dive — starting with the voice engine."

### Slide 8 — ★ Detection layers  [1:30]
- "The voice engine is led by **two independent neural detectors** — both built on
  XLS-R, a multilingual self-supervised speech encoder, but trained on *different*
  clone families, so they fail differently and cross-check each other. Together they
  carry 90% of the vote."
- "The four handcrafted acoustic checks — spectral biometrics, breath patterns,
  phase coherence, liveness — are shown as **evidence**, near-zero weight. We
  measured them; they don't separate modern fakes, so we don't pretend they do."
- "Ensemble → 0–100 score, banded green/amber/red — thresholds fit on labelled
  data, not hand-picked."
- "**Worst-window drives the verdict** — a deepfake anywhere in the call is a
  deepfake. A VAD gates out silence so we never score noise."
- → "Why two detectors? That's the most important lesson we learned."

### Slide 9 — ★ Model & the generalization lesson  [2:00]  (slow down — panel loves this)
- "Our first model — a fine-tuned wav2vec2 — looked excellent on its dev set,
  under half a percent error. Then we tested it on **real commercial voice clones**
  of our own voices: **40% EER, AUC 0.63.** Barely better than a coin flip."
- "That's the dirty secret of this field: **benchmark accuracy does not transfer.**
  Published detectors routinely degrade 200 to 1000 percent across datasets. Any
  team quoting one dev-set number is telling you very little."
- "The fix wasn't a bigger model — it was **two independent detectors trained on
  different data**, so their failure modes anti-correlate, plus calibration fit on
  our own labelled corpus."
- "The measured result, on a **122-clip held-out set of our own voices and
  commercial clones: 99.2% accuracy, EER 1.6%, AUC 0.999** — reproducible with
  one command in the repo, `python -m eval.run`."
- "**Honest caveat:** 122 clips is a small corpus. We treat these as strong
  evidence, not gospel — and our own red-teaming already found an open-source
  generator that partially evades us. That finding feeds the retrain pipeline;
  the loop is the product, not any frozen model."
- → "That covers the clone. Now the human scammer."

### Slide 10 — ★ Scam-script + multilingual  [1:30]
- "This is the layer competitors don't have. We transcribe the call with Whisper,
  then an LLM — NVIDIA's Nemotron — reads the transcript for **manipulation tactics**."
- Name them: urgency, authority impersonation, isolation, new-beneficiary, OTP
  requests, threats.
- "It runs in the background every few seconds so it never slows the main detector."
- "**Multilingual is nearly free** — Whisper auto-detects language, the LLM reasons
  in Hindi and Hinglish. We verified a Hindi scam scores 90 out of 100."
- "And it's fail-safe — offline or no key, it goes neutral and voice detection is unaffected."
- → "Now, how do we turn all these signals into one decision?"

### Slide 11 — ★ Decision fusion  [1:15]
- "Deliberately **rule-based**, because every decision must be defensible to an auditor."
- Read the rule. "A threat is a high voice score, or a high scam score, or high
  novelty. If there's a threat *and* it's a high-value action — a new payee or a big
  amount — we Block. Threat alone, we Challenge. Otherwise Monitor."
- "Context makes it **proportionate** — a suspicious voice on a balance enquiry is
  nothing; on a five-lakh transfer to a new payee it's a Block."
- "We chose rules over a learned policy on purpose — a learned policy needs labelled
  outcomes we have to accumulate first. Rules are the honest, auditable v1."

### Slide 12 — ★ Novelty & campaigns  [1:30]
- Left — novelty: "We use the model's own uncertainty. If it's not confidently real
  or confidently fake, the signature is unfamiliar — a possible zero-day tool — and
  we lift the verdict to amber. Honestly, it's a heuristic; embedding-distance OOD is
  the upgrade."
- Right — campaigns: "Every call gets a voiceprint from the *same* forward pass, so
  it's free. We cosine-match against past calls. The same voice across many calls is
  a **campaign**; a voice that already committed fraud is **blocklisted** on its next
  call. This is the line: 'the same synthetic voice hit fourteen of your customers.'
  It's a data advantage that compounds with use."
- → "One more deep dive — the thing that makes or breaks a real deployment."

### Slide 13 — Telephony & hostile channels  [1:15]  (honest: in progress)
- "Real calls aren't studio audio — 8 kHz, band-limited, G.711, lossy. Most
  detectors collapse there, and we'll be straight: **so does ours today** — our
  telephony EER is roughly 20%, versus near-zero clean. We measured it; we're not
  hiding it."
- "Two answers. First, a **channel-robust retrain** is literally running — training
  data degraded through telephony, room reverb, noise, and speaker-replay channels,
  gated so it can't regress clean accuracy."
- "Second — and this ships today — **the system knows when it can't judge.** A
  degraded input reads UNCERTAIN, never a confident all-clear. And a clone played
  from a loudspeaker trips a **replay-channel gate**: either the model catches the
  synthesis, or the channel gate catches the replay. It never silently trusts a
  speaker playback."
- → "So, what makes us different — summarised."

### Slide 14 — Uniqueness  [1:00]
- Sweep the six cards quickly (they've heard the detail): human-scam, phone lines,
  campaigns, on-prem, novelty, multilingual.
- "No single competitor has all six. Most have one or two."

### Slide 15 — Benchmarks  [1:30]
- "Let's be rigorous and honest about where we stand."
- "Academic models top the ASVspoof leaderboard at around 1% EER. **But** — and
  this is documented in the literature — they generalise poorly across datasets:
  on in-the-wild fakes they degrade to 20–40%. We evaluate where it matters:
  **on our own held-out voices and real commercial clones — 99.2% accuracy,
  EER 1.6%** — not on the leaderboard's easy axis."
- Walk the differentiator rows: telephony, human-scam, on-prem, governance, campaigns
  — where academic and even commercial tools are blank or limited, we're a check.
- "Our point: **accuracy on a benchmark is table-stakes. We optimise for the real
  deployment, not the leaderboard.**"

### Slide 16 — Technical moat  [1:15]
- "Why is this defensible over time? Six compounding advantages."
- Highlight two: "The **data network effect** — the blocklist gets smarter with every
  call, on the bank's own data a competitor can't touch. And **governance as a moat**
  — built-in model-risk monitoring is the thing banks are legally required to have
  and most vendors don't provide."

### Slide 17 — Engineering & robustness  [1:15]
- "This isn't a notebook demo — it's engineered." Sweep the six cards.
- Call out one war story: "We hit a real runtime crash — torch and the speech-to-text
  engine each ship an OpenMP runtime that conflicts on Windows and killed the process.
  We diagnosed and fixed it. That kind of hardening is the difference between a demo
  and a product."

### Slide 18 — Deployability  [1:15]
- "How does it actually go into a bank? It drops in beside the stack — no rip-and-replace."
- Read the flow: telephony → SIPREC media-fork → our on-prem container → agent screen
  or fraud engine.
- Three cards: on-prem and private (no audio leaves, RBI-clean); standard integration
  (SIPREC + REST/WS); runs like a service (audit trail, Prometheus metrics).
- "API-key gated, TLS, full audit trail — and again, **no audio retained**. mTLS
  and horizontal scale-out are on the hardening roadmap; we're honest that today's
  build is single-instance."

### Slide 19 — Governance & trust  [1:15]
- "Banks don't switch a fraud system to full power on day one. We designed for that."
- **Shadow mode** — score and log for 30 days, take no action, measure on your own
  traffic, then flip one switch to enforce.
- **Evidence & audit** — every verdict is a defensible record for disputes and regulators.
- **Governance** — live detection and false-alarm rates, drift, champion/challenger —
  RBI Model Risk Management, built in.
- "This is how banks safely adopt AI: prove it risk-free, then enforce."

### Slide 20 — Honest limitations  [1:15]  (say it with confidence)
- "We want to be straight with the panel about what's a v1 today — and every one has
  a clear upgrade path."
- Thresholds → calibrate on real traffic. Novelty heuristic → embedding OOD. Linear
  scan → FAISS at scale. Differing EER sets → one fixed benchmark. Cloud LLM → on-prem
  NIM container (a URL change). Customer identity → the next layer. Adversarial → tested next.
- "We'd rather show you the roadmap than pretend it's finished."
- → "Enough talking — let me show it working."

---

## PART 2 — LIVE DEMO (≈8 min)  [Slide 21]

Follow **DEMO-RUNBOOK.md** (verified clips + channel rules — never play a clone
out loud into the mic; upload it or use `/call`). Say each line, then act.

1. **Real voice → GREEN.** Speak ~5s into the mic (live mic is fine for a *real*
   voice). "That's me, live — green, no false alarm."
2. **Clone → RED.** **Upload** a verified clone from the runbook list (risk ≥ 90).
   "Cloned voice — red in seconds, flagged inside the 10-second budget — see the
   timer — before money moves."
3. **Scam script in your real voice → tactics + escalation.** Read the scam line.
   "My real voice, no deepfake — every deepfake-only tool says safe; ours catches
   the *scam*."
4. **Voice OTP (`/verify`) — the strongest 30 seconds.** Show a pass with your live
   voice, then explain the measured attack: "a synthetic voice that answers the
   digits *correctly* still gets rejected — right answer, wrong speaker type."
5. **(Optional) Hindi scam** → tactics still fire.
6. **(Optional) `/call` two-tab demo** — "this is the digital tap a real telephony
   integration gives us — no over-the-air loophole."
7. **Backend product pages** — `/cases` → evidence pack; `/campaigns` → same voice,
   many calls; `/governance` → TPR/FPR, drift, registry. "A bank product, not a toy."
8. **(Optional) Shadow toggle** — flip it: "pilot mode… and one click to enforce."

Fallbacks to know: internet down → scam layer neutral, voice detection still works.
If a judge insists on playing a clone from a speaker: the replay gate forces
CHALLENGE — narrate it as the feature it is. Don't demo KittenTTS audio as the
headline (it's the red-team story, 5/8 voices evade today).

→ "So where are we on readiness?"

---

## PART 2 (cont.) — TRL, ROADMAP, INTEGRATION (≈4 min)

### Slide 22 — TRL 5 → 6  [1:15]
- "We place ourselves at **TRL 5 to 6** — and we can justify it."
- Why: full working prototype, end-to-end, real-time; validated on realistic data
  (ASVspoof + real Indian voices + modern fakes + telephony); a deployable Docker
  artifact with governance.
- Path to 7–8: "A 30-day shadow pilot on one bank queue is operational-environment
  validation. Then calibrate on real traffic and harden the SIPREC adapter and mTLS."
- "We're honest — it's a validated prototype, not yet a live bank deployment. The
  shadow pilot is exactly the bridge."

### Slide 23 — Roadmap & timeline  [1:00]
- "Everything in the 'Done' rows is built and demoed today — the core shield, the
  edge features, and the telephony retrain that's deployed."
- "Next is customer voice-identity and stronger novelty; then the bank PoC path."

### Slide 24 — Integration  [1:00]
- "Three plug-in points, one API: the contact centre is primary — a SIPREC fork to
  the agent screen and the fraud engine. It also works as an anti-spoofing layer in
  front of voice biometrics, and for batch dispute review."
- "Every path returns the same JSON verdict — any downstream system can consume it."

### Slide 25 — Impact  [0:45]
- "To close: it catches clones **and** human scams; it's real-time, so it acts before
  money moves; and it's on-prem, so no audio leaves the bank."
- "Built for how your calls, your customers, and your regulators actually work."

### Slide 26 — Thank you / Q&A  [remaining]
- "Thank you — we're Team ERROR 404, and we're happy to take questions."

---

## Q&A PREP — the hard ones, with crisp answers

**Q: Isn't this just a wrapper over an open model? What's novel?**
The model is one sensor. The novelty is the *system*: covering human scams via an LLM
layer, telephony robustness, campaign/voiceprint intelligence, and built-in governance
— plus the fusion that turns signals into an auditable decision. No off-the-shelf model
gives you that.

**Q: How do you know it isn't overfitting?**
We saw exactly that with the CNN — 2.75% dev but 9.75% on unseen attacks. That's *why*
we moved to a self-supervised model and progressively added real Indian voices, multiple
deepfake families, and telephony. Our honest gap: EERs are on different dev sets; a single
fixed benchmark is our next step.

**Q: What's your false-positive rate on real customers?**
The metric that matters most. We specifically broadened "real" with Indian voices to cut
it, and the governance dashboard tracks FPR live from analyst labels. True calibration
needs a bank's own traffic — which is exactly what shadow mode measures before enforcement.

**Q: Why rule-based fusion, not ML?**
Auditability, and honesty. A learned policy needs labelled fraud *outcomes* we must first
accumulate. Rules are explainable to a regulator today; we swap to a learned policy once a
pilot has produced the data.

**Q: The LLM is a cloud call — that breaks on-prem/RBI.**
Correct today. The same Nemotron model runs as a self-hosted NIM container inside the bank;
it's a base-URL change, no code rewrite. We flag it as a known production item.

**Q: Deepfakes will get better — how do you keep up?**
Three ways: novelty flags unknown signatures; the scam layer adapts by prompt, not retrain;
and confirmed frauds feed the blocklist. The system is designed to age gracefully.

**Q: Latency / scale in a real call centre?**
~4s first verdict, ~every 2s after; a 60s call scores in ~6s. It's stateless and scales
horizontally behind a load balancer, CPU-viable, one GPU per node if needed.

**Q: Adversarial evasion — can an attacker beat it?**
Untested, and we say so — it's on the roadmap. The ensemble + novelty + the scam layer
raise the bar (evading all of them at once is hard), but we won't overclaim.

**Q: Whose voice data trains it — privacy?**
Public datasets + augmentation + our own consented clones. In production, no audio is
stored — only verdicts and transcripts — which minimises the privacy surface.

**Q: What's the business model / who pays?**
On-prem licence per deployment to banks; value is measured in the shadow pilot (fraud
caught, false positives avoided). The compounding campaign data creates switching cost.

**Q: Why should a bank trust a student prototype?**
We don't ask them to trust — we ask them to *measure*, risk-free, in shadow mode on their
own traffic for 30 days. The numbers decide.
