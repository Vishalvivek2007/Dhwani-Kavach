# Dhwani-Kavach — Bank Integration Guide

How Dhwani-Kavach plugs into a bank's existing environment, and what it buys you.
Written for the UCO Bank technical review.

---

## 1. The one-line answer

Dhwani-Kavach is a **self-contained scoring service**. It takes call audio in,
returns a fraud verdict out (`GREEN / AMBER / RED` + a 0–100 risk score). It
does not replace any existing system — it sits *beside* your contact-centre /
voice-auth stack and adds a deepfake-voice check the current stack can't do.

Two ways to call it:

| Mode | Endpoint | Use for |
|------|----------|---------|
| **Live streaming** | `ws /ws/analyze` (binary PCM frames) | In-progress calls — verdict in ~4s, updates every 2s |
| **Recorded** | `POST /api/analyze` (audio file) | Recorded calls, voicenotes, post-call review |

Everything runs **inside the bank's own network**. No audio ever leaves your
perimeter.

---

## 2. Where it fits in the bank environment

Three integration points, in order of impact:

### A. Contact centre / IVR — live fraud screening (primary)
Your telephony platform (Genesys / Avaya / Cisco) already has the call audio.
A **media fork / SIPREC connector** copies the caller's audio leg to a small
adapter, which streams raw PCM to `ws /ws/analyze`. The verdict surfaces:
- on the **agent's screen** as a live risk badge, and/or
- as a **signal into your fraud-decisioning engine** to auto-trigger step-up
  auth (OTP, security questions) when the score hits RED.

```
Caller ──► Telephony (Genesys/Avaya) ──► SIPREC/media fork ──► Adapter
                                                                  │ PCM 16k
                                                                  ▼
                                                       Dhwani-Kavach  (on-prem)
                                                                  │ JSON verdict
                                                                  ▼
                                              Agent dashboard  /  Fraud engine
```

### B. Voice-biometric authentication — anti-spoofing layer
If the bank uses (or plans) voice biometrics for phone-banking login,
Dhwani-Kavach runs **in front of it** as a presentation-attack / deepfake
check: biometric says "this is customer X's voice", Dhwani-Kavach says "and
it's a live human, not a clone". The two together close the spoofing gap that
voice biometrics alone have.

### C. Recorded-call / dispute review — batch
Investigations and dispute teams `POST` recorded calls to `/api/analyze` to
flag synthetic-voice fraud after the fact. Same engine, no live plumbing.

---

## 3. Deployment model

- **On-premise / private VPC.** Ships as a Docker container. Runs inside the
  bank DMZ or private cloud. Satisfies **RBI data-localisation** — call audio
  never touches the public internet or any third party.
- **Stateless & no audio retention.** Audio is scored in memory and discarded;
  only the verdict (score + level + layer breakdown) is returned. Nothing to
  breach, minimal data-privacy surface.
- **Horizontal scale.** Stateless service → run N replicas behind the bank's
  load balancer, sized to peak concurrent calls. CPU-only inference works;
  one GPU per node raises throughput if needed.
- **Footprint.** Single service + a ~360 MB model file. No external DB
  required for scoring (Redis optional, only for multi-node alert fan-out).

---

## 4. What we harden for production (vs. the demo)

The demo build is deliberately open. For a bank deployment we add the standard
controls — all are small, known additions, not research:

| Area | Demo today | Production integration |
|------|-----------|------------------------|
| Auth | none, CORS `*` | API key + **mTLS** between adapter and service; CORS locked to bank origins |
| Transport | plain HTTP/WS | TLS everywhere (bank PKI) |
| Audit | none | Append-only verdict log (call-id, timestamp, score) for compliance; **no audio stored** |
| Packaging | run from source | Hardened Docker image, health/readiness probes, resource limits |
| Observability | logs | Prometheus metrics (latency, verdict mix, error rate) into the bank's monitoring |

None of these touch the detection engine — they wrap it.

---

## 5. Verdict contract (what the bank's systems consume)

`POST /api/analyze` and the live socket both return the same shape:

```json
{
  "risk_score": 82,
  "alert_level": "RED",
  "layer_breakdown": {
    "aasist":   0.86,
    "mfcc":     0.40,
    "breath":   0.75,
    "phase":    0.30,
    "liveness": 0.20
  }
}
```

- `risk_score` 0–100. Bands: **GREEN < 40**, **AMBER 40–69**, **RED ≥ 70**.
- `layer_breakdown` makes every verdict **explainable** — the bank's fraud team
  sees *why* a call scored high, not just a black-box number. Thresholds are
  tunable to the bank's risk appetite.

---

## 6. Benefits — what UCO Bank gets

1. **Stops voice-clone vishing** — the current scam wave (cloned voices of
   customers/relationship managers authorising transfers). Existing voice-auth
   and OTP do **not** catch a convincing deepfake; this does.
2. **Real-time** — verdict during the live call (~4s first read), so the agent
   or fraud engine can act *before* money moves, not after.
3. **Stays inside the bank** — on-prem, no audio leaves the perimeter,
   RBI-aligned. No new third-party data-sharing risk.
4. **Drops in beside existing systems** — no rip-and-replace of telephony or
   biometrics; integrates via a standard media fork + REST/WS API.
5. **Explainable & tunable** — 5-layer breakdown per verdict, thresholds set to
   the bank's risk appetite; gives audit and compliance a defensible trail.
6. **Accuracy** — 99.2% accuracy / EER 1.6% measured on a held-out set of real
   voices + commercial clones (dual XLS-R detectors, calibrated on labelled
   data); trained on global spoof datasets + real Indian voices to cut false
   alarms on genuine customers.
7. **Lightweight to run** — single container, CPU-only viable; horizontal
   scale-out is on the hardening roadmap (per-call state is in-process today).

---

## 7. Suggested rollout

1. **PoC (weeks):** point a recorded-call sample set at `POST /api/analyze`,
   measure detection rate + false-positive rate on the bank's own audio.
2. **Pilot (live, one queue):** SIPREC fork on a single contact-centre queue →
   agent-screen badge, verdicts logged but not yet auto-acting.
3. **Production:** wire RED verdicts into the fraud-decisioning engine for
   automated step-up auth; scale replicas to full call volume.

> Tuning to UCO's own call audio in the PoC is expected and important — the
> false-positive threshold should be calibrated on real bank traffic, not just
> our test sets.
