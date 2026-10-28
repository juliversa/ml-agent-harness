---
name: red-team-run
description: One fresh hostile reviewer checks a GPU/TPU run plan (or a plan to the owner, a lane closure, the finals) and writes the Verdict line the push gate needs. Use before any GPU/TPU push or /red-team-run.
---
# red-team-run
Stop wasted GPU time and wrong decisions before they happen: RULES R15 (red-team before every GPU/TPU run series, owner plan, lane closure and the finals).

Needs: `<comp>/plans/<kernel slug>.md`, the loader dump `<comp>/plans/<slug>-batch.*` (> 1 KB), `STATUS.md`, `STATE.md`, FINDINGS.

## Brief
Spawn ONE fresh sub-agent on the strongest model. Give it this brief and nothing else; never your summary.
```
<paste skills/coding-discipline/SKILL.md verbatim>
Plan: <comp>/plans/<kernel slug>.md (≤ 1 page: the kind: / lever: / elite-spec: lines of
PLAYBOOK §7, idea, the runs of the screen series (defined below), argv, data, folds, GPU-h, expected gain, the decision it changes).
Loader dump: <comp>/plans/<slug>-batch.*. Context: STATUS.md, STATE.md, the last 20 FINDINGS rows.
You are here to criticise, not to be nice. Assume gold is reachable. Run checks 1–8 of skills/red-team-run/SKILL.md.
Output: ≤ 10 lines, each with evidence (number or file:line), each named claim CONFIRMED / WEAKENED / REFUTED,
each item BLOCKER / MAJOR / MINOR; then append the Verdict line to the plan.
```
`elite-spec:` points to `plans/elite-<id>.md`, what a winner would build for the lever (PLAYBOOK §1 D4). A **screen series** is the runs one plan lists, on one kernel slug, within 24 h.

## Checks
1. **Waste:** bug, wrong files on Kaggle, time vs session cap, quota, duplicate of running work.
2. **Best version:** is this the elite version (PLAYBOOK §1 D4) or a cheap one? Gain ≥ smallest readable change? A `kind: lever` plan with no `elite-spec:` file, or a build that deviates from that spec without a written reason → NO-GO.
3. **Decision:** which decision changes with the result? None → NO-GO.
4. **Gap:** does this aim at the bottleneck and the top lever of the latest Depth loop? A bigger lever, the winners' family, a known bug, a cheaper CPU test? Any unpriced self-constraint → FIX.
5. **Ruler** (PLAYBOOK law 4, one calibrated ruler): anything killed or adopted on a proxy or < 2 SE? An open watcher `ruler` alert (spread > 1.5 × LB noise, slope < 0.5 over a CV range ≥ 3 × LB noise, or `.lbnoise` empty) → no decision on public.
6. **Depth:** loader dump + one item's inference input present; from run 2, the last `eda/err-<id>.md` read. Missing → FIX.
7. **Stuck:** same idea failed ≥ 2 times → a new angle at a lower level (data, labels, metric, loss, loader), not a third try.
8. **What the lead forgot.**

## Verdict
The reviewer appends `Verdict: FIX`, `Verdict: NO-GO`, or for a GO the line bound to the plan as reviewed:
```sh
sed -i -e '$a\' <plan>      # make sure the plan ends with a newline
echo "Verdict: GO sha256=$(grep -v '^Verdict:' <plan> | sha256sum | cut -c1-16)" >> <plan>
```
- The last Verdict line counts. `push_and_watch.sh` refuses GPU/TPU unless it matches the plan as it stands and is < 24 h old, so any edit after the review needs a new one.
- The lead re-checks key claims by command, fixes, writes one FINDINGS row, then pushes. At most 2 rounds per decision.
- One GO covers one screen series; a run not listed needs a new review.

## Non-run reviews
For a plan to the owner, a lane closure, a redirecting number or the finals: brief file `<comp>/plans/<topic>.md` (finals: CV-ranked candidates with CV, public, pairwise correlation, the law 13 rule, best CV + strongest least-correlated candidate); apply the checks as they fit; nothing goes out before `Verdict: GO`.

## Done when
The plan ends with a Verdict line; for a GO, its sha256 matches the plan as it stands.
