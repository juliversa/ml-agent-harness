<!-- Rendered by kit/setup-competition.sh (placeholders $SLUG $NAME $KREF $DEADLINE $WEEKS $TODAY $DAYS $DUE5F $DEST); this line is dropped. -->

# Week 0 — $NAME

0. **Data:** `kaggle competitions download -c $KREF -p $DEST/data`, then `unzip -q $DEST/data/$KREF.zip -d $DEST/data` · **Look:** 20 train + 20 test raw items per class/site AS THE LOADER OUTPUTS THEM → eda/look-d0-*; label/data disagreements with ids, train-vs-test stat diff → eda/look-d0.md
1. **Entry (PLAYBOOK §2):** $WEEKS weeks left; field size; winners' GPU-h per model × our folds × families × 2 vs the free quota (RULES R16); quota cost of ONE commit (measured). < 8 weeks or > ~5× quota → "target = silver unless …":
2. **Split axis, in the host's words** (host spec + data page line by line, L33; `kaggle competitions pages $KREF --content --format json`) → fold design (whole groups, or forward with gap = horizon), hard-slice group unit (PLAYBOOK Terms), worst fold reported (law 3):
3. **Metric:** host metric code run locally; reproduces one scored sub to the digit; worth of one unit of each term; direction (lower is better → `echo 1 > $DEST/.lower`):
4. **Leak/shift/shortcut on raw inputs:** adversarial validation train vs test; can a model guess site, scanner, period (L12)? duplicates, ID/time order; what were provided weights trained on (L15)?
5. **Label truth:** label noise estimate; clean expert subset? → it is the truth for the noise matrix and autopsy (law 4), not the ruler:
6. **Intel by day 2 → intel/writeups.md** (≥ 3 URLs, verbatim quotes): 2–3 nearest past comps' write-ups, forum, top notebooks; none → nearest-problem papers, same-metric comps `[analog]`. Model-, data-, target- or runtime-bound (law 1)? → D2 levers with IDs:
7. **Board facts:** gold cut → `$DEST/.goldcut` (empty board → D1 prior, PLAYBOOK §1), team count, score histogram, tie-blocks (L31):
8. **Floor by day 2:** strongest public notebook (URL, score) retrained by us on our folds, no weights others trained for the comp (RULES R3) → `kind=floor` row + scored sub:
9. **Runtime limit** and whether the base fits it; code comp → hidden-test TTA / pseudo-labels on test allowed? inference budget per item:
10. **Noise:** σ_Δ from ≥ 5 fresh seed pairs on fold 0 of the week-1 base (PLAYBOOK Terms; in week 0 only if a fold trains in minutes) → ; LB noise (end of week 1; PLAYBOOK Terms: the floor vs the week-1 base) → write it to `.lbnoise` in the competition folder →
11. **Constraint table** (law 10; external-data and weights rules read yourself, L23): constraint → verbatim source → score price → keep/drop:
12. **Owner batch** (RULES R2): target, constraint prices, over-budget spend, LLM-API spend, anything public; sent (date):
13. **Team-merge deadline** (solo by design, PLAYBOOK §2; from the competition's overview/rules page):
14. **Depth loop D1–D7 written into STATE.md** (D6/D7 may read `none yet`; only `—` is hollow; PLAYBOOK §1) · first red-team before the first GPU run (skill `red-team-run`).
15. **TTA and post-processing** (knobs; main effort stays on models): costed on the week-1 base's OOF (minutes, no GPU; PLAYBOOK Terms: knob) → gain of each; revisit in the last two weeks:
