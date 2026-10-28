---
name: autopsy
description: Read real failing examples one by one to find why the model fails, and check a measured gain is real before acting on it. Use when sweeps stop improving, a result looks too good, or /autopsy.
---
# autopsy
Find the mechanism behind the errors by reading real failing items at the lowest level, then confirm any measured delta before acting on it.

Needs: `<comp>/experiments.csv`, OOF predictions, `kit/pick_items.py`, the clean-truth subset if one exists. Output per experiment: `<comp>/eda/err-<id>.md`, one per kept or lever row of `experiments.csv` (PLAYBOOK §7; a convention, not checked by code).

Switch here when sweeps sit inside noise, every sweep's best setting is the one you already ship, or lanes close faster than the score rises: the answer is not in the space you search. This is step D5 of the Depth loop (PLAYBOOK §1, the weekly checklist).

## Steps
1. Pick the items by script, not by a helper: `python3 kit/pick_items.py --oof <comp>/oof/<id>.npy --score-dir <comp> --seed 0` → `<comp>/eda/pick-<id>.csv` (20 worst, 10 clean, 10 random controls). A clean-truth subset (expert labels) exists → run it on that subset too and read its clean group. Never read the worst only: it over-samples mislabels and biases you toward "labels".
2. One one-shot reading helper (strongest model, RULES R11, R13; brief below) sorts all failing items into patterns: one page.
3. The lead hand-reads ~15 picked items itself at the lowest level (raw file, label source, pixels/rows as the loader outputs them, the inference-path input, the metric code on that item), ≥ 3 of them random controls (RULES R7). Attach every field: score, rank, confidence, the competing answer.
4. Compare each field on failures vs controls; the ratio is the signal. Where the clean truth disagrees with the training label, count it into the noise matrix (PLAYBOOK law 4, one calibrated ruler). Name the mechanism in one sentence a person could act on, with item ids.
5. Only then write a fix. Write its acceptance criterion first ("beats the model here without breaking the rest") and judge it on the failure population. Keep the characterised failures as a reusable offline test.
6. Write `<comp>/eda/err-<id>.md`; in the same turn, write the mechanism into `STATE.md` (this week's bet if it is the biggest error class) and add a FINDINGS row.

## Reading-helper brief
Copy, fill the `<…>`, spawn one fresh helper on the strongest model; the same brief serves research and EDA sweeps (swap the inputs).
```
<paste skills/coding-discipline/SKILL.md verbatim>
Goal: sort every failing item of <comp> experiment <id> into error patterns. The lead decides; you only read.
Ruled out: <mechanisms already tested, with experiments.csv ids>. No plan or hypothesis of ours is given on purpose.
Inputs (raw): <comp>/oof/<id>.npy, <comp>/data/oof_target.npy, <raw data dir>, <label source>, <comp>/eda/pick-<id>.csv.
Scope: read items, not code; no training, no edits outside <scratch dir>.
Output: <scratch dir>/read-<id>.md, ≤ 1 page: patterns with counts and their chance rate (share among
controls), 5–10 example ids each; a "didn't fit / weird" section with ≥ 3 ids.
```

## Traps
- Report no proportion without its chance rate: compute the null before reporting a split.
- Feed a metric an input that should fail; if it is perfect at every setting, it is a bug.
- Price the decision, not the proxy: a proxy can improve without moving the decision.
- Test a fix where the target case happens, not on a whole population where it is rare.

## Is the delta real?
Run these before acting on any measured delta (law 4).
- Measure the noise floor first: σ_Δ from ≥ 5 fresh seed pairs (PLAYBOOK Terms). A best with both neighbours negative is noise; check monotonicity, not the argmax.
- Report the deployment stratum, not only the pooled number. Fix strata from a reference config, never from what the change alters.
- Remember small samples mislead both ways; cheap sanity stats never veto a real validation number.
- Treat an effect far bigger than its mechanism as a bug hypothesis first (check dtype casts and truncation).
- Remember default-arg constants bind at definition, so sweeps can report the default; generate the CV kernel from the submission file.
- Check the tested thing is active (a clip above the data max is a no-op).
- Log the proxy prediction before the true result; until calibrated, a proxy only ranks.
- An oracle over your own outputs cannot see their errors: state which metric term a change moves and that term's max.
- Use mechanism arguments to choose what to measure, never to conclude. Record a clean negative as a result, with its number.

## Done when
`<comp>/eda/err-<id>.md` lists the sampled ids with label, prediction, path and cause, names the mechanism in one sentence, and the `STATE.md` line and FINDINGS row are written.
