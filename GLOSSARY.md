# GLOSSARY: terms used across the docs
One line each: what it is, and why it matters. Docs and reports use these words as defined here.

- **CV (cross-validation score)**: the host metric on all out-of-fold predictions pooled (training rows each model did not see). It is our own scoreboard, and we pick by it, not by the leaderboard.
- **Fold**: one slice of the training data held out for checking. Five folds = five models, each checked on a different slice.
- **OOF (out-of-fold) predictions**: each training row predicted by the model that did not train on it. They give the CV and feed blends.
- **Hard slice (`oof_hard`)**: rows fixed on day 0 by a data property (unseen site, rare class, long horizon), else the worst tenth by error. Most of the loss lives there, so it is reported every run.
- **Noise (σΔ, "SD")**: how much a score moves when only the random seed changes. A gain smaller than about two times the noise is not proven ("not read"), which is not the same as no gain.
- **LB noise (`.lbnoise`)**: the same idea for the public leaderboard: how much it moves by chance.
- **Public / private leaderboard**: public = the part of the test set shown during the competition; private = the hidden part that decides the medals.
- **Ruler**: the check that CV and the public leaderboard move together. If they do not, the CV is not trusted to rank.
- **Floor**: the best public notebook, retrained by us. Day-2 baseline.
- **Base**: the first control we train; each later change is measured against its parent.
- **Lever**: a change aimed at the bottleneck (labels, data, the model family), not a setting.
- **Knob**: a setting (learning rate, threshold). Knobs rarely win medals.
- **Elite version**: the strongest form of an idea, as the top teams would build it. An idea is closed only after its elite version ran.
- **Mechanism**: why a change should help, in one sentence. Each experiment names one.
- **Pseudo-labels**: the model's own confident predictions on unlabelled data, used as extra training labels.
- **Blend / ensemble**: an average of several models. It helps only when the models make different mistakes.
- **Red-team**: a fresh reviewer that tries to find what is wrong with a plan before GPU time is spent.
- **Depth loop (D1–D7)**: the weekly checklist: name the bottleneck, read real errors, build the elite version, measure.
- **Context**: everything the agent holds in mind at once. Too much makes it slow, costly and forgetful.
- **wM**: weighted million tokens, the token cost measure (input + 1.25 × cache write + 0.1 × cache read + 5 × output).
- **Law**: one of the 14 rules of thumb in PLAYBOOK §5, cited as "law N".
- **Lane**: one route to the score, a line of ideas tried over several runs; closed only after its elite version ran.
- **Verdict / GO**: the reviewer's last line on a run plan; the push script accepts only a GO matching the plan's hash.
- **Harvest**: downloading and reading a finished kernel's outputs.
- **FINDINGS**: the per-competition record of ideas and results (PLAYBOOK §7).
- **Tier-1 alert**: an urgent watcher alert that must be acked (`kit/ack.sh`).
