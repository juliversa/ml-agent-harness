---
name: kaggle-submit
description: Submit to Kaggle through a gate that checks the CV number, the code, the kernel version, the log and the daily cap, then records the CV in the message. Use for any submission or /kaggle-submit.
---
# kaggle-submit
Submit only a candidate with a validation number, through `kit/submit_gate.py`, and log the score next to its prediction.

Needs: `kit/submit_gate.py`, `<comp>/events.log`, `<comp>/log.md`.

## Steps
1. Get the validation number AND its aggregation: the same predictions score differently pooled vs fold-averaged. The candidate is the lead's CV decision (PLAYBOOK law 4, one calibrated ruler); the gate does not choose. Cadence follows law 14 (floor by day 2, then 1–2 a day, by CV only).
2. Submitting without a CV is allowed only for a pure runtime fix or a change upstream of the cached harness; say which, and expect no delta. "Confident in the mechanism" is not a number.
3. Find `--version`: vN of the last `PUSH <ref> vN` line in `events.log` (TOOLING T24, code-competition submit errors); none → abort.
4. Run the gate (add `--dry-run` when unsure):
   ```sh
   python3 kit/submit_gate.py --kernel <user/kernel> --version <N> \
     --competition <kaggle-ref> --slug <slug> --desc "<what changed>" \
     --cv <number> --agg "<how aggregated>" --source <submitted.py> --log-md <comp>/log.md
   ```
   - File-upload competitions: `--file <submission.csv>` instead of `--kernel/--version`.
   - No `--cv` is refused unless `--probe "<what the slot measures>"` or `--no-cv-reason "<why>"`. Empty kernel log → `--no-log-reason`.
   - Checks 0–4 (one at a time, ≤ 2/day, CV, AST of `--source`, pushed version, log health) are in the `submit_gate.py` docstring.
5. Write the score next to its prediction in `log.md` and in the `public` column of `experiments.csv` the turn it lands.

## Traps
- Treat `DEGRADE` as an abort: a fired runtime guard means the scored pipeline is not the one you built.
- Use a CV-vs-board disagreement to calibrate the ruler (law 4).

## Done when
The gate printed its pass and the submission is in, and the public score sits next to its CV in `log.md` and `experiments.csv`.
