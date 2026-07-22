# ⛔ SUPERSEDED — use [DEMO-RUNBOOK.md](DEMO-RUNBOOK.md)

This script described the **retired** wav2vec2 pipeline and — dangerously —
told the presenter to **play clone audio out loud into the laptop mic**
(Beats 2/4). That speaker→air→mic channel destroys the synthetic artifacts and
is measured to fail; DEMO-RUNBOOK §1 is the golden rule (upload / `/call` /
VB-Cable, never open-air). Its rollback procedure (renaming
`deepfake_w2v_v1.pt`) targets a model no longer in the serving path.

Everything current lives in:

- **[DEMO-RUNBOOK.md](DEMO-RUNBOOK.md)** — verified clips, channel rules, stage flow
- **[PRE-DEMO-CHECKLIST.md](PRE-DEMO-CHECKLIST.md)** — T-1 day / T-30 min tick list
- **[FINALS-DECK-BRIEF.md](FINALS-DECK-BRIEF.md)** — the measured numbers (single source of truth)

Kept only so old links don't 404.
