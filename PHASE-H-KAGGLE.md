# Phase H — Channel-Robust Retrain on Kaggle (SLS fine-tune)

**Updated 2026-07-20.** The old runbook (telephony-augmenting `deepfake_w2v.pt`)
is obsolete — that model is retired. The current best engine is the **ported
public XLSR-SLS checkpoint** (`backend/models/xlsr_sls.safetensors`, made by
`tools/port_sls.py`, 7.8% In-the-Wild EER out of the box). This runbook
fine-tunes **that** checkpoint for the two things it hasn't seen:

1. **Channels** — telephony, reverb, noise, phone-in-room (the live-mic gap).
2. **Indian voices** — Hindi / Indian-accented English reals (its ASVspoof
   training is Anglo/studio; some of our phone-mic reals read fake to it).
3. **Loudspeaker replay** (added 2026-07-22) — a clone played from a phone/
   laptop speaker into a mic. New `speaker_replay` augmentation condition in
   `train_robust.py` (randomized 180-400 Hz → 3.4-6.5 kHz small-driver bandpass
   + room reverb + mic noise, 14% of training samples) and a `speaker_replay`
   column in the per-epoch anti-overfit gate. The runtime replay trust gate
   (ml/replay.py → fusion CHALLENGE) stays as defense-in-depth either way; this
   retrain is what lets the model actually SCORE the clone through that channel.

Everything runs through the existing `backend/training/train_robust.py` with
`--arch sls`: full-backbone fine-tune, telephony-weighted on-the-fly
augmentation, per-condition + per-source anti-overfit gate, saves only if the
weakest channel improves without regressing clean. Verified end-to-end via
`--smoke` on CPU.

---

## Step 0 — One-time uploads (from your machine)

The training warm-starts from the ported bundle, which is gitignored. Create a
**private Kaggle dataset** (e.g. `dhwani-sls-bundle`) containing:

- `xlsr_sls.safetensors` (1.35 GB — from `backend/models/`)

Optionally add a second private dataset `dhwani-user-audio` with your own
recordings (`user_real/`, `user_fake/` folders) — they are **validation-only**
by default (honest cross-source test), `--train-on-user` folds them in.

## Step 1 — Data (all free, attach or fetch in-notebook)

Folder layout `train_robust.py` expects (build under `/kaggle/working/data`):

```
data/real/    ← Common Voice Hindi + English (attach a Kaggle CV mirror),
               LibriSpeech dev-clean (openslr.org/12), In-the-Wild reals
data/fake/    ← ASVspoof2019 LA (datashare.ed.ac.uk), WaveFake (zenodo),
               In-the-Wild fakes, your ElevenLabs clones
data/rir/     ← real room impulse responses: OpenSLR 28 (RIRS_NOISES, 1.2 GB)
               — real RIRs beat the synthetic fallback for the replay channel
data/user_real/  data/user_fake/   ← (optional) your clips, val-only
```

Aim for **thousands of reals from many speakers/mics** and **several fake
generators** — diversity is what killed the last overfit, not volume.
The `--bootstrap` flag still works for a zero-setup sanity run
(LibriSpeech+VITS), but it will NOT fix the Indian-voice gap.

## Step 2 — The one-cell Kaggle run (T4 GPU)

```python
# NOTE: until PR #37 merges, clone the branch that has the speaker_replay
# condition: add `-b feature/demo-hardening` to the clone.
!git clone https://github.com/Chiranjib-x/Dhwani-Kavach.git
%cd Dhwani-Kavach/backend
!pip -q install -r requirements.txt
# warm-start bundle from the attached private dataset:
!cp /kaggle/input/dhwani-sls-bundle/xlsr_sls.safetensors models/
# (build /kaggle/working/data per Step 1 here)
!python -m training.train_robust --arch sls --grad-ckpt \
    --data /kaggle/working/data \
    --epochs 4 --batch 4 --lr-backbone 5e-6 --lr-head 5e-5 \
    --out /kaggle/working/xlsr_sls_finetuned.safetensors
```

Notes:
- `--grad-ckpt` fits the full 24-layer backbone fine-tune in T4 memory
  (batch 4; raise to 6-8 if it fits).
- LRs are **half** the v2 defaults — the checkpoint is already good; we are
  nudging it toward new channels, not re-teaching it. If the per-epoch gate
  never saves, the augmentation is too aggressive for the LR — halve LRs again.
- **Save Version** on Kaggle so the output survives; download
  `xlsr_sls_finetuned.safetensors` when done.

## Step 3 — A/B locally, deploy only if it wins

```bash
cd backend
DHWANI_SLS_MODEL=<path-to-downloaded>.safetensors ../.venv/Scripts/python.exe -m eval.ab_channels
```

Compare per-channel EER against the committed `eval/ab_channels.json` from the
current bundle. **Only if the weakest channel improves and clean holds**, copy
over `backend/models/xlsr_sls.safetensors`, refit calibration
(`python -m tools.fit_calibration --exclude=lily_original,chris_original`),
and restart the backend.

## Why this beats retraining v2

The v2 track (truncated XLS-R + W2VAASIST, `--arch v2`) starts from our
narrow fine-tune — measured failure: studio-voice score inversions that no
threshold fixes, telephony real/fake overlap. The SLS track starts from a
model that already generalizes across in-the-wild channels and generators
(replay-attack literature: W2V2-AASIST-family EER 4.7%→18.2% on replayed audio,
recovered to ~11% with RIR augmentation — arXiv 2505.14862). Fine-tuning from
strength with real RIRs + Indian reals attacks exactly the residual gaps.
