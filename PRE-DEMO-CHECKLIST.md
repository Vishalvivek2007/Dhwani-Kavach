# Pre-Demo Checklist — Team ERROR 404

Tick these in order. Everything here has bitten this project at least once, or is
one measured failure away from doing so. Pair with DEMO-RUNBOOK.md (clip lists,
click paths). **T-1 day** = night before; **T-30 min** = just before you present.

---

## T-1 DAY — on the exact laptop you'll present from

### Model & keys (the silent killers)
- [ ] `NVIDIA_API_KEY` is set in the environment the backend runs in
      (`echo $env:NVIDIA_API_KEY` in PowerShell — must be non-empty). Without it
      the scam layer silently returns 0 and your differentiator is dead.
- [ ] `backend/models/w2v2aasist_full.safetensors` present (~306 MB, gitignored —
      does NOT come from `git clone`). Without it the detector falls back to a
      weaker head.
- [ ] `backend/models/calibration.json` present (gitignored, must match the
      bundle above). Without it verdicts mis-scale.
- [ ] One scam-script upload shows tactics fire (proves LLM + key + Whisper all
      live). Expect ~95/100 + CHALLENGE. If score is 0 → key or network problem.

### Warm the caches (needs network once, then works offline-ish)
- [ ] Whisper model downloaded (first scam run pulls it — do it now, not on stage).
- [ ] XLS-R backbone cached (first analyze pulls ~1.2 GB — do it now).
- [ ] Run one upload + one `/call` + one `/verify` end-to-end so every model is
      hot; the first live verdict then isn't a 15 s hang.

### Backup (assume the venue wifi dies)
- [ ] **Screen-record the full working demo** (upload→RED, scam→CHALLENGE,
      /verify reject, /call). This is your parachute if the network fails live.
- [ ] Phone hotspot ready as network backup (LLM + Whisper need it).
- [ ] Laptop charger packed; test on the actual projector/screen resolution —
      the deck and dashboard must not clip on 4:3.

### Content
- [ ] 40-min run timed end-to-end once against the real deck.
- [ ] Q&A answers written (2 sentences each): TRL, bank integration, moat,
      "why not use <existing tool>", "how do you know it works on real calls".
- [ ] Verified-clip folder ready; `lily_original`, `chris_original`,
      `glenn_1-clone` REMOVED from the demo folder so they can't be picked by
      accident.
- [ ] If the Kaggle retrain finished: A/B'd locally with
      `DHWANI_MODEL=<path> python -m eval.run ../Dataset_orig` and deployed ONLY
      if it beats 99.2% without dropping clean (+ refit calibration). If not
      clearly better → keep current v2, present retrain as "in flight." **Never
      swap in an unvalidated model the night before.**

---

## T-30 MIN — at the venue

- [ ] `start-fresh.bat` → wait for both windows → dashboard loads at :8080.
- [ ] Click every path once (warms models + proves reachable):
      dashboard · `/call` (two tabs) · `/verify` · `/cases` `/campaigns`
      `/governance` `/metrics`.
- [ ] One verified **fake** upload → RED + HIGH RISK banner + artifact-window
      outline + "flagged at X.Xs / 10 s".
- [ ] One verified **real** upload → GREEN.
- [ ] Mic test in the actual room → GREEN on your live voice. If it reads
      UNCERTAIN, the room is too loud — that's a *feature*, narrate it, don't panic.
- [ ] Backup video open in a background tab, ready to play.

---

## THE THREE THAT MATTER MOST
If time collapses, do only these:
1. **API key + model files present** on the demo machine (T-1 day).
2. **Backup video recorded** (T-1 day).
3. **Voice-OTP rejection rehearsed** — a synthetic voice that answers the digits
   *correctly* still gets REJECTED. Your strongest 30 seconds; make it flawless.

---

## ON-STAGE NARRATIVE REMINDERS
- **Own the gap first:** "public benchmark AUC 1.00, our own voices through a real
  phone ~0.5 — the gap every team hides. Here's ours, measured, and the retrain
  closing it." Rigor beats polish to an academic panel.
- **Two differentiators no pure-deepfake team has:** human scam detection (a real
  human reading a scam script still gets flagged) + two-sided protection (fake
  customer AND fake bank-caller — their use-case #13).
- **If a judge insists on playing a clone from a speaker:** expect the
  "Loudspeaker replay suspected" chip → CHALLENGE. Narrate: "either the model
  catches the synthesis or the channel gate catches the replay — it never
  silently trusts a speaker playback." That's a win, not a miss.
- **First verdict lands ~4 s into a stream / ~3 s on upload** — well inside the
  problem statement's 10 s budget. Point at the timer.
