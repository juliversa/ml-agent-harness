# PLAYBOOK: the method

The bottleneck named on day 0, compute following it, the winners' lever built in its strongest form, an honest ruler,
and one real change shipped every week. Evidence: `LESSONS.md` (L#). Traps: `TOOLING.md` (T#).
Failure modes it guards against: compute off the bottleneck, levers closed on weak tests, slow cadence, process overhead.

Terms (plain English: `GLOSSARY.md`):
- **CV** = host metric on pooled OOF predictions, folds shaped like the private split (`oof_mean`; Δ tests use per-fold Δ).
- **board-adjusted** = LB number minus the median (public − CV) of our scored 5-fold subs.
- **hard slice** = groups defined by a data property fixed day 0 (unseen site, rare class, long horizon), else the worst decile
  by the MEAN OOF loss of the floor and 2 differently seeded runs (one model's worst groups regress to the mean); frozen when the
  base lands (end of week 1), logged as `oof_hard`. Compare on it arm vs a re-run control, never vs the runs that selected it.
- **group** = the host's split unit (patient, site, well, recording), else a metadata stratum fixed day 0 (source × class).
- **noise**: for 1-fold screens σ_Δ, the std of (twin_i − control_i) over ≥ 5 pairs, each pair two fresh seeds (= √2 × the std
  of control reruns; one shared control gives the std of runs, √2 too small). For a 5-fold read, the corrected resampled t:
  se = std(Δ_fold)·√(1/5 + 1/4) (folds share training data; Nadeau & Bengio 2003, Bouckaert & Frank 2004).
- **readable** = mean Δ ≥ 2 × noise, written "≥ 2 SE" below (t ≥ 2 on 4 df either way; read against t₄ that is
  one-sided p ≈ .06, ≈ .04 with 10 pairs (9 df); a screening bar, not a test).
- **LB noise** (`.lbnoise`) = std of Δscore between two compared subs' OOF predictions (the floor vs the week-1 base), bootstrapped by group at the public-test
  size (200×), plus in code competitions the delta of one kernel scored twice (an upper bound for near-identical subs; re-bootstrap the actual pair when a public Δ decides anything).
- **knob** = constant, threshold, weight, TTA, seed, epochs. TTA and post-processing stay knobs (main effort stays on models), but cost them on OOF in week 1 (minutes, no GPU); revisit in the last two weeks.
- **real change** = new code path, learned function or information source.
- **lane** = one route to the score: a line of ideas tried over several runs.
- **elite version** = what a winner would build: full context, full resolution, tools, best
  model, the leaders' recipe.
- **edge** = a lever no top-10 team uses.
- **LLM label machine** = an LLM reading everything an expert sees to relabel data.
- **noisy student** = self-training (Xie et al. 2020): a teacher pseudo-labels unlabelled data; a student of equal or larger size trains on labels + pseudo-labels with input/model noise. Run here k-fold, so the teacher for fold k never saw fold k.
- **tie-block** = many teams on one score (forked notebooks).
- **commit day** = the day finals are queued, with one retry.

## 1. Depth loop (day 0, then every Monday; `STATE.md` D-lines, date on `depth-check:`)
- [ ] **D1 Gap:** board-adjusted gold cut − our CV, weeks left, required rate per week (law 9). Empty board → prior: the
      gold-vs-best-public-notebook gap of the 2–3 nearest past comps, tagged `prior`; replace it by day 7 and every Monday.
- [ ] **D2 What wins:** write-ups of the 2–3 nearest past comps + forum, top-10 posts, top notebooks → `intel/writeups.md`
      (URLs, verbatim quotes, by day 2) → 2–3 candidate levers with IDs, each sized against D1. No write-ups → papers on the
      nearest problem and past comps with the same metric or data type, tagged `[analog]`. Read top-10 hints literally.
      Research → action (L24): a one-shot reading helper (RULES R11) does the reading; its brief omits our current plan. The page
      ends with "what top teams did that we are not doing": top 3 levers, each with a cheap test and its cost. The top lever
      goes into `STATE.md` as this week's bet in the same turn, or the page records why not. Runs at week 0, ~30 % and ~50 % of the timeline.
- [ ] **D3 Bottleneck:** labels / data / shift / target-metric / model / compute, one line with `mechanism: <experiments.csv mechanism>`;
      its share of the last 7 days' `gpu_h` (CPU-only comp: share of `experiments.csv` rows). Share < 50 % with no written reason = the bug (L2).
- [ ] **D4 Elite spec:** `plans/elite-<lever id>.md`: what a winner would build for the top lever (all context an expert
      gets, full resolution, tools, best model, their recipe step by step, diffed against ours) BEFORE any test of it.
- [ ] **D5 Autopsy:** 20 worst OOF + 10 clean + 10 random control items, picked by `kit/pick_items.py` (skill `autopsy`).
      Name the top error mechanism with `ids:`.
- [ ] **D6 Shipped:** the real change shipped this week (CV, ≥ 2 SE, in a scored sub), or the reason in writing.
- [ ] **D7 Closures:** each lane closed this week names its `kind=lever` experiments.csv id with `oof_mean`; none → reopen.

## 2. Entry (day 0)
The owner naming a comp = joined (R1); never re-ask. < 8 weeks left (L28), or the winners' type needs > ~5× the free
quota (L22), → "target = silver unless …" in the day-0 owner batch. One competition at a time.
Solo by design; note the team-merge deadline in WEEK0.

## 3. Day 0–3 → `WEEK0.md`, the one day-0 list (answers, not plans; skill `kaggle-new-competition`)

## 4. Week by week
| when | do | exit test |
|---|---|---|
| days 0–3 | §3; ~1 h on raw data before any helper page (R7); D2 research #1; explainer video at 24 h (WEEK0 item 16); folds fixed; hard-slice rule written; floor = best public notebook retrained by us | WEEK0 complete; `kind=floor` row scored |
| week 1 | strongest simple base trained by us (law 2); hard slice frozen; LB noise measured (Terms); save OOF + test preds for every 5-fold run | base has CV + `oof_hard` + public |
| weeks 1–2 | elite version of the top lever on 50–100 items (D4); 2–3 families small, best to 5 folds | lever has a CV read |
| day 14 | leaders' family trained by us on 5 folds | `kind=family5f` row |
| day 21 | scale read, pseudo-label read (or reason), ≥ 2 mechanisms at 5 folds | rows have CV |
| week 2 … −10 | weekly depth loop; D2 research #2 at ~30 % and #3 at ~50 % of the timeline; ≥ 1 real change a week (law 5); step-back every 72 h (law 6) | D6 each week |
| day −10 … −5 | freeze; best single model maxed: 5 folds + seeds + all-data | incumbent fixed |
| day −5 … 0 | full-data retrains; blend (built from day −14, per R3), strong decorrelated members only (non-negative weights fit nested out-of-fold; report the nested CV), valid file at t+0, commit day | finals (law 13) |

Short window (≤ 3 weeks): public-recipe base trained by us by day 2 → elite top lever by day 7 → scale → CV finals.

**Owner brief.** Weekly from day 7: run `python3 kit/graphs.py <comp>` (progress to the gold cut, experiment lineage,
CV vs leaderboard) and write `<comp>/weekly/<date>.md`: ≤ 1 screen, per skill `lean-replies`, words as in
`GLOSSARY.md`: where we are vs the gold cut, what shipped (number), what failed (number), next week's one bet, owner
decisions by ID, the three pictures. The text is the record. Videos (skill `explainer-video`, 3–6 min): one competition explainer at 24 h (WEEK0 item 16), then short explainer videos for a result or method,
when useful.

## 5. Laws
1. **Bottleneck first; spend follows it.** One line in `STATE.md`; re-check weekly against where compute went (L2, L24).
2. **Strongest simple base by end of week 1**: the field's simplest modern recipe, trained by us on our folds. Public base + knobs did not transfer (L4, L27).
3. **Honest, hard validation.** Folds follow the host split (whole groups, or forward with gap = horizon); retrain per
   fold; hold out the hardest hidden axis; log `oof_hard` and report the worst fold every run (L5, L7);
   group-derived features must survive group-disjoint and leave-one-group-out folds (L13).
4. **One calibrated ruler; never decide on noise.** Trust CV as the ruler only while the public score follows it: over ≥ 5 scored 5-fold subs, public stays near its straight-line fit on CV and rises with CV.
   Adopt a change only on a 5-fold CV gain ≥ 2 SE, no fold negative and pooled Δ ≥ 0 (`kit/compare.py` prints the read); 1-fold screens only rank and pause.
   A gain < 2 SE, or a |Δpublic| below LB noise, is "not read", never "dead" (L6).
   Budget mode (owner's call per competition, `RULES.md` R1): if 5 folds per idea does not fit the GPU quota, the owner may allow fewer folds; a change is then kept provisionally (`kept=P`) only if every fold run improves by ≥ 2σΔ, and final picks still get a 5-fold check.
   A change below the bar that does not hurt CV is a candidate (`kept=C`), not kept. Candidates are combined and the stack is read as one change: it must pass the full 5-fold bar and hold per stratum (site / group / class). Only then is it kept.
   Power: a true gain of one fold-SD passes about 1 in 3 (`kit/sim_bar.py`); that is why `kept=C` exists. Stack the candidates at least every two weeks, not only at the end.
   Bootstrap read (`kit/compare.py --bootstrap N --seed-noise σΔ`, once σΔ is measured): resample whole groups (patient, site, well) for the pooled Δ, add the training noise σΔ²·(1/k + 1/(k−1)), and adopt on pooled Δ ≥ 2 SE with no fold below −2 σΔ. In simulation (`kit/sim_bar.py` (c), folds correlated up to ρ = .5; bootstrap SE by its normal approximation; the training-noise term is a conservative heuristic) it false-passes no more than the fold bar (≤ 3.5 % vs ≤ 6.5 %) and passes more true gains while training noise is small; a bootstrap without σΔ false-passes up to 16 %, so it never decides alone.
   Details:
     - Trusted = the residual SD of public around its linear fit on CV stays ≤ 1.5 × LB noise (a Δ-scale bar, so lenient on purpose) and the slope ≥ 0.5 (read only when the subs' CV range ≥ 3 × LB noise);
       At 5–8 subs over the narrowest readable CV range (3 × LB noise) this check false-alarms about 1 in 5–9 on a trusted CV (simulated: `kit/sim_bar.py`); it is a prompt to look, not a verdict (assuming per-sub public residual SD = LB noise; about 1 in 20–40 if it is LB noise/√2).
       Spearman is not used (top-CV subs are range-restricted). If the public board scores a different slice than private (other horizon, sites), skip the board check:
       CV mirrors the private slice only. A cheap test can kill a build (bug, crash, no signal on the failure population), never a lane (law 8).
     - Unit = paired screen: arm + control, same fold and seed (σΔ from fresh-seed pairs is conservative for same-seed pairs), same convergence. Noisy labels: a small clean expert set is a weak ruler (58 exams on RSNA: about ±.02 macro AUC) but is the truth for the label-noise
       matrix and the autopsy. Measure in the deployed form (L14). Classify the lever broad vs tail, predict public first (L8). An adopted change is
       re-run on fresh seeds; `kept=Y` goes on the replicate's row, not the screen's, so its CV is the incumbent (winner's curse).
     - Labels built from model OOF (pseudo, soft, blended) inflate CV unless built per fold: the teacher for fold k never saw fold k (L2; `kit/templates/train.py` refuses `LABELS_FROM_OOF` without `--labels-oof-fold-safe`).
     - Before a decision: truth independent of prediction. The CV number is the host metric on pooled OOF, closest to how one file is scored; pooled AUC also penalises calibration drift between fold models, which a fold-averaged test file does not have, so decisions rest on per-fold Δ below. A non-decomposable metric (AUC, F1) is never averaged over folds; Δ tests use per-fold Δ; if pooled and per-fold Δ disagree in sign, it is not read; gain is not carried by a handful of items (recompute after dropping the few items with the largest per-item gain).
5. **From week 2, ≥ 1 real change a week**, aimed at an error mechanism named before the run, ≥ 2 SE, no fold
   negative, in a scored sub. Knob tuning (thresholds, weights, TTA; on CV, law 14) waits for the last 10 days, ≤ 10 % of time (L3, L4, L27); CV-read knobs that are
   part of the training recipe (LR, epochs, augmentation) are allowed when they pass law 4. TTA and post-processing are costed on OOF in week 1 (Terms: knob).
6. **Keep reading.** Daily 10 min of new posts/notebooks → FINDINGS rows. Every 72 h a fresh step-back writes
   `intel/stepback-<date>.md` with `LEVER:` (biggest untried) and `EDGE:` (one thing no top-10 uses); run both within
   48 h. Check the base does not already do an imported trick's job (L29).
7. **Own a copy of what moved the top**: leaders' type, 5 folds, by day 14. Label/data-bound → ≥ 50 % effort on training
   data from week 1 (LLM label machine, pseudo-labels, outside data if allowed; L9, L32). Target-bound →
   reformulate target/loss first. Model-bound → winning type from week 2. Runtime-bound → speed per item (L34).
   Structured output → learned components inside the solver.
8. **A lane is dead only after its elite version ran** (D4) on ≥ 50 cases with a CV-correlated ruler. A failed build
   kills that build, not the channel; a wall changes allocation (≤ 10 % of the week), never the verdict (L1, L11).
9. **Rate check weekly.** Required = gap ÷ weeks left; actual = best-CV gain over 14 days ÷ 2. Actual < required →
   next run is a bigger lever (new class, channel, labels, pseudo-labels, scale), not a knob. On CV, never public (L17).
10. **Price every constraint and the compute on day 0**, hand the number to the owner; never adopt a constraint from a
   competitor's claim (L19). Spend the whole quota weekly; analysis kernels ≤ 20 % (L21, L22).
11. **Estimate, don't select.** Average ambiguous candidates; weak signals go in as soft gated inputs (L18).
12. **Events drop the queue the same day**: a notebook passes us → rerun on our folds, port its mechanism; a leak →
   rules + owner, hedge if allowed; new data → re-score the base.
13. **Finals = best CV + strongest least-correlated candidate.** Rule and predicted public written first; never two
   public-best of one family; both re-run from scratch and scored in the last 48 h; red-team the pair; the owner picks (L20, R19).
14. **Submissions:** floor by day 2, then ≥ 1/day, ≤ 5/day (Kaggle's cap; owner 10-29), by CV only, CV + claim in the message (skill `kaggle-submit`).

## 6. Priors
On demand: `LESSONS.md` › Priors by problem type. Rows cite their evidence. Read the CV–LB gap and the D5 autopsy before picking a lever type.

## 7. Records (`<comp>` = `$COMP_ROOT/<slug>`; after the close: skill `kaggle-postmortem`)
**Read by the watcher** (`kit/watcher.sh` → tier-1 ALERT lines in `<comp>/events.log`, the rest in `digest.md`) **and the gates:**
- `experiments.csv` `id,date,change,kind,folds,parent,mechanism,oof_mean,oof_hard,public,gpu_h,kept,note` (`kept`: Y · N · P (budget mode) · C (candidate); only Y counts as kept, law 4; ISO date; counts only with numeric
  `oof_mean`; `parent` = id of the run this one changes, required on every non-floor row (else `csvbad`), so every number traces to its control; board statistics, plateau
  and incumbent use `folds=5` rows). `kind`: `floor` · `base` · `family5f` (leaders' family, 5 folds) · `scale` · `pseudo` (note `na: <reason>` allowed)
  · `lever` · `edge`. A number not in this file does not count. `oof_mean`: the CV score (host metric on pooled OOF, not a mean of fold scores; the name is historical).
- `kernels.txt`; `.entry .deadline .kref .lower .goldcut`; `.lbnoise` (the LB noise).
- Step-back (tier 1): `eda/err-<id>.md` per scored kept or lever row (D5 samples: id, label, pred, path, cause; alert `noerr`); 3 `kept=N` rows on one
  mechanism since its last kept=Y, none beating its parent's CV → a new angle at a lower level (alert `loop`); `FINDINGS.md` changed within 3 h of
  work (> 1M tokens, no kernel running) and within 5M tokens (alerts `stuck-time`, `stuck-tokens`); `intel/stepback-<date>.md` every 72 h (law 6, alert `stepback`).
  `mechanism` is a short fixed tag per idea (the loop check groups by it). Stepback and loop stop at the day −10 freeze.
- `plans/<kernel slug>.md` for GPU/TPU pushes: `kind: <kind>`; `kind: lever` also `lever: <D2 id>` + `elite-spec: plans/elite-<id>.md`
  (file exists); last Verdict line `Verdict: GO sha256=<plan hash>` written by the reviewer (else `push_and_watch.sh` exit 6).

**Conventions (not checked by code):**
- `kind=floor` row and `intel/writeups.md` (≥ 3 URLs) by day 2; `eda/look-d0.md` + `eda/look-d0-*` by day 3.
- `FINDINGS.md` `| id | date | decision | number (folds, SD) | example ids | verdict |` (example ids never empty; a closed/dead
  verdict names its `kind=lever` id, law 8).
- `STATE.md` D-lines `- D<n> <name>: <value>`: never `—`; D1 has a number, D3 `mechanism:`, D5 `ids:`; depth-check ≤ 8 d old;
  the D3 mechanism gets ≥ 50 % of 7-day `gpu_h`. One screen, overwritten in place. `log.md` append-only (submissions).
