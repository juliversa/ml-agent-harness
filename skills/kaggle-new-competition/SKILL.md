---
name: kaggle-new-competition
description: Start a new Kaggle competition: scaffold the folder, work through WEEK0.md, build the first base and honest folds. Use when the owner names a new competition or /kaggle-new-competition.
---
# kaggle-new-competition
Take a competition from day 0 to the end of week 1: scaffold, answer the day-0 list, train an honest base.

Needs: `kit/setup-competition.sh`, `kit/templates/`. Method: `PLAYBOOK.md` §1–§4.

## Steps
1. Treat the owner naming the competition as joined (PLAYBOOK §2, entry); do not re-ask. Put the compute estimate (winners' GPU-h vs the free quota) into WEEK0 item 1 and the day-0 owner batch.
2. Scaffold:
   ```sh
   bash kit/setup-competition.sh <slug> "Name" <YYYY-MM-DD> [kaggle-ref]
   ```
   It renders `STATE.md`, `NOW.md`, `WEEK0.md` from `kit/templates/`, writes the first `STATUS.md` (`kit/status.sh`), creates the records of PLAYBOOK §7 and starts the watcher.
3. Days 0–3: answer every line of `<comp>/WEEK0.md`, top to bottom; it is the only day-0 list.
   Day 0: spend ~1 h on the raw data yourself (WEEK0 item 0) before reading any helper page (RULES R7).
   Research (WEEK0 item 6, PLAYBOOK §1 D2): one reading helper (brief: skill `autopsy`, inputs swapped), brief without our plan; its page ends with
   "what top teams did that we are not doing": top 3 levers, each with a cheap test and its cost. Put the top lever into `STATE.md` as this week's bet in the same turn, or record on the page why not.
4. Days 0–3: write `<comp>/data/folds.npy`, one fold id per train row on the host split (PLAYBOOK law 3, honest validation); commit it and never re-split.
5. Write `<comp>/score.py` with `score(y, p)` (host metric, higher is better unless `.lower`), then `cp kit/templates/train.py <comp>/code/`.
6. Train the strongest simple base ourselves (law 2, strongest simple base by end of week 1) and calibrate the ruler (law 4, one calibrated ruler).
7. Week 1: `np.save` `<comp>/data/hard_ids.npy` (the frozen hard slice, PLAYBOOK Terms); `kit/compare.py --hard` and `oof_hard` read it.
8. Set `kept=Y` on the incumbent's `experiments.csv` row (the base's replicate); `kit/status.sh` BEST and the watcher read it.
9. Read the first errors: `eda/err-<id>.md` (skill `autopsy`).

## Done when
Every `WEEK0.md` line is answered, `folds.npy` and `score.py` are committed, and the base has a CV read and its first `eda/err-<id>.md`.
