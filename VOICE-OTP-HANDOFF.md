# Voice OTP verification — build-out branch

**Branch:** `feature/voice-otp-verification` · **for:** the OTP voice-verification
build-out. Push here, PR into `main` when ready.

## The one rule: this is a PARALLEL path, not a replacement

Voice OTP verification is a **separate verification method** that runs
alongside the deepfake-detection engine — it must NOT change or gate the main
detection flow. Do not touch:

- `backend/app/routes/analyze.py`   (`POST /api/analyze`)
- `backend/app/routes/websocket.py` (`WS /ws/analyze`)
- `backend/ml/detector.py`, `ensemble.py`, `fusion.py`

Those are the live call-scoring path and stay as-is. If OTP work needs a signal
from the detector, **call it, don't modify it** (import `detect_samples`, read
its result — same as `challenge.py` already does).

## What already exists (your starting scaffold)

| Piece | File | What it does today |
|---|---|---|
| Challenge issue | `backend/app/routes/challenge.py` → `GET /api/challenge` | returns 4 random digits + a `challenge_id` (in-memory, 5-min TTL) |
| Challenge verify | `backend/app/routes/challenge.py` → `POST /api/challenge/verify` | two gates: ASR digit-match (Whisper) **and** deepfake ensemble on the voice; also fails on a suspected loudspeaker replay |
| Digit generator | `backend/ml/liveness.py` → `generate_challenge()` | prompt + digit list |
| Frontend demo | `frontend/src/routes/verify.tsx` → `/verify` | issue → 6 s record → PASS/FAIL with evidence |

This is a **demo-grade** scaffold. The build-out is turning it into a real
product path.

## Likely next work (not prescriptive — your call)

- **Persistence:** `_pending` is an in-memory dict — fine for a demo, needs a
  store (Redis / sqlite) for anything real / multi-process.
- **Enrolment + speaker match:** today it verifies "a live human said the right
  digits and isn't a deepfake." A real OTP flow also checks it's the *right*
  person — wire in a voiceprint match (embeddings already exist:
  `wav2vec2_detector.embed` / `voiceprints.py`).
- **Delivery:** the digits are shown on screen; a real OTP arrives by SMS/app.
  Decide the channel and how the spoken-back code is validated.
- **Rate limiting / lockout, audit trail** (reuse `app/audit.py`), and a proper
  single-use guarantee across processes.
- **Frontend:** `/verify` is a demo page; a product flow needs error states,
  retries, accessibility, and an embed path banks can drop into their app.

## Test what exists

```bash
# backend up on :8000, then:
curl http://127.0.0.1:8000/api/challenge          # -> {challenge_id, digits, ...}
# record the digits, POST them back:
# curl -F challenge_id=<id> -F audio=@spoken.wav http://127.0.0.1:8000/api/challenge/verify
```

Keep everything OTP-related behind its own routes/modules so a merge into `main`
never risks the detection path.
