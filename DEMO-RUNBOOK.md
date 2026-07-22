# Demo Runbook — finals stage checklist

Everything on this page is **measured, not assumed** (2026-07-21, model
`w2v2aasist-cotrain+clone_v3`, calibration refit on the 122-clip Dataset_orig +
sample_audio set: 99.2% acc, EER 1.6%, AUC 0.999, verdict p50 ~2.9 s).
If you change the model or `calibration.json`, re-verify every clip below with
`cd backend && python -m eval.run ../Dataset_orig` before trusting this list again.

## 0. Start everything

```
start-fresh.bat        # kills stale 8000/8080, starts backend+frontend, opens browser
```

## 1. The golden rule: never speaker→air→mic

Playing a clone out loud into the laptop mic destroys the synthetic artifacts —
every detector in the field fails that channel. Feed audio **digitally**:

| Channel | How | Use for |
|---|---|---|
| **File upload** | "Stream a file" button in the dashboard | headline detection demo |
| **`/call` WebRTC demo** | open `localhost:8080/call` in two tabs (Customer / Bank Agent); the agent side taps the received track digitally and streams it to the detector | "how it integrates into telephony" |
| **Virtual audio cable** | install VB-Cable (vb-audio.com/Cable, free), set "CABLE Input" as the playback device for your media player and pick "CABLE Output" as the mic in the browser → live-monitor "hears" the file digitally | live-mic theater without the air gap |

If a judge insists on the open-air test: expect the **"Loudspeaker replay
suspected"** chip (ml/replay.py — LF+HF band deficits) and the action forced to
**CHALLENGE** — a suspected replay can never clear to MONITOR on the voice score
alone, and the Voice OTP (`/verify`) rejects it outright ("correct digits,
untrusted channel"). Narrate it: *"either the model catches the synthesis, or
the channel gate catches the replay — the one thing it will never do is silently
trust a speaker playback."* (Verified: 0 false replay flags across all 122
normal clips; a speaker-simulated clone → suspect, score 95, CHALLENGE.)

## 2. Verified demo clips (from Dataset_orig, re-checked on current calibration)

**Fakes — guaranteed RED (risk ≥ 90):**
`aditya_17-clone` (97) · `aditya_6-clone` (96) · `aditya_11-clone` (95) ·
`aditya_14-clone` (95) · `aditya_3-clone` (93) · `aditya_12-clone` (91)

**Reals — guaranteed GREEN (risk 0):**
`aditya_10` `aditya_11` `aditya_16` `aditya_18` `aditya_3` `aditya_7` `aditya_8` `Glenn_2`

Also safe: `sample_audio/Script_1..5` (real) and their `_clone` counterparts (fake).

**NEVER demo these (known model misses, documented in HANDOFF.md):**
- `lily_original.mp3`, `chris_original.mp3` — real voices that read fake
- `glenn_1-clone.mp3` — the one clone that reads real
- `chirag_8/11/16`, `glenn_11` — real voices that sit near the boundary (AMBER)

## 3. Scam-script demo (two independent flags on one clip)

Use a clip whose **content** is also a scam so the LLM layer fires alongside the
voice layer — two chances to flag, and the fusion action goes CHALLENGE/BLOCK
even if one layer wobbles. Script that reliably trips the tactic tags:

> "Hello, this is the bank security team. Your account has been compromised.
> Please share the one-time password immediately so we can secure your funds.
> Do not tell anyone about this call."

Tactics that fire: authority impersonation · urgency · OTP/PIN request · isolation.

## 4. Live synthesis on stage (red-team story, not headline)

```
python tools/demo_synth.py            # Bruno voice — flags RED (risk 47) today
python tools/demo_synth.py --sweep    # scores ALL KittenTTS voices: 2 caught, 5 evade, 1 AMBER
```

KittenTTS is **out-of-domain** for the current model (trained on commercial
clones) — 5 of its 8 voices evade today. Do **not** present it as the detection
demo. Present the `--sweep` table as the **red-team pipeline**: *"we
continuously probe with new open-source generators; what evades feeds the next
retrain — that's the moat, the loop, not any single frozen model."*

For a true clone-of-a-real-voice live moment: ElevenLabs instant clone
(~1 min setup, needs an account) → download the clip → upload to the dashboard.
The ElevenLabs clips in Dataset_orig score 60/61 RED.

## 5. What the judges' rubric maps to on screen

| Expected outcome (verbatim) | Where it shows |
|---|---|
| "analyzes the spectrogram of a live call" | live spectrogram panel; RED outlines the **ARTIFACT WINDOW** region it just scored |
| "synthetic artifacts … human ears miss" | HIGH RISK banner: "synthetic artifacts detected — micro-imperfections in pitch/frequency" |
| "flag as High Risk within the first 10 seconds" | banner shows **flagged at X.Xs · 10s budget ✓** (typical: ~4–6 s on stream, ~3 s on upload) |
| real-time | first verdict ~4 s into a stream, updates every 2 s |

## 6. Pre-stage checklist

- [ ] `start-fresh.bat`, wait for both windows, dashboard loads
- [ ] Upload one verified fake → RED + HIGH RISK banner + artifact window outline
- [ ] Upload one verified real → GREEN
- [ ] `/call` in two tabs → call connects, agent side streams verdicts
- [ ] Mic test in the actual room → GREEN on your live voice (if UNCERTAIN, the
      room is too loud — say so, it's a feature)
- [ ] Backend product pages open: /cases /campaigns /governance /metrics
