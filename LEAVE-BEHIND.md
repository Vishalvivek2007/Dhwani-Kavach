# Dhwani-Kavach
### Real-time call-fraud shield for banks — stops voice clones *and* human scams, on-prem, in real time.

---

**The problem.** Fraudsters clone customer and staff voices, or run scripted
social-engineering scams, to authorise transfers. OTP and voice biometrics don't
stop a convincing clone or a coerced genuine customer.

**What it does.** Listens to a live call and, in ~4 seconds, returns one decision —
**MONITOR / CHALLENGE / BLOCK** — with a 0–100 risk score and the reasons behind it.

---

### Capabilities

| | Capability | What it means for you |
|---|---|---|
| 🎙️ | **Deepfake voice detection** | Two independent neural detectors cross-check every window — 99.2% accuracy / EER 1.6% measured on our own held-out voices + commercial clones. |
| 💬 | **Scam-script detection** | Flags human scammers (urgency, "don't tell anyone", OTP asks) — the fraud deepfake-only tools miss. |
| ⚖️ | **Decision + context** | Weighs the transaction (amount, new payee) → a proportionate action, not just a score. |
| 🆕 | **Zero-day / novelty** | Flags clone tools it has never seen — doesn't go stale. |
| 🕸️ | **Campaign detection** | "The same synthetic voice hit 14 customers" — fraud-ring intelligence that compounds with use. |
| ☎️ | **Channel-aware** | Degraded input reads UNCERTAIN (never a false all-clear); loudspeaker-replay injection is detected and challenged. Full telephony-grade retrain in progress. |
| 🇮🇳 | **Multilingual** | Hindi, Hinglish, regional languages out of the box. |
| 🔭 | **Shadow mode** | Pilot risk-free: log only for 30 days, then flip to enforce. |
| 📑 | **Audit & evidence packs** | Defensible per-call record for disputes/regulators — **no audio stored**. |
| 📊 | **Model governance** | Live detection/false-alarm rates, drift, versioning — RBI Model Risk Management built in. |

---

### Why it's worth it
- Closes the voice-fraud gap **OTP and biometrics leave open.**
- **Real-time** — acts during the call, before money moves.
- **On-prem, no audio retained** — RBI data-localisation aligned, minimal data risk.
- Catches **human scams too**, not only deepfakes.
- **Fraud-ring intelligence** that gets smarter with every call.
- **Audit-ready and governable** — a deployable product, not a prototype.

### How it fits in
On-prem **Docker** container in your DMZ. Integrates via a standard **SIPREC /
media-fork** from your existing telephony (Genesys/Avaya/Cisco) → verdict to the
agent screen or your fraud-decisioning engine. **No rip-and-replace.** API-key
gated today; mTLS and horizontal scale-out on the hardening roadmap. CPU-viable.

---

### Suggested next step
**A 30-day shadow-mode pilot on one contact-centre queue** — we score and log your
real calls, take no action, and you measure detection and false-positive rates on
your own traffic. Then decide.

> *A deployable, explainable, on-prem layer that closes the voice-fraud gap —
> built for how your calls, your customers, and your regulators actually work.*
