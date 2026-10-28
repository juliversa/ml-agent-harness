---
name: hostile-review
description: Get independent critics to review finished work (code, docs, a plan, a claim), verify their findings, fix, and review again. Use before handover, when asked for a critique or to 'make it perfect', or /hostile-review. GPU/TPU runs and finals: red-team-run.
---
# hostile-review
Self-review finds what you already believe; fresh readers with no stake find the rest.

## Single review
1. **Name the target and the bar**, one line each: what is reviewed (paths), who it is for, the bar ("top 0.1 %", "a stranger can run it", "a newcomer understands it in 5 minutes"), and the owner's constraints that apply.
2. **Pick 1–3 readers, each with a different job** (never three of the same):
   - **Expert critic** (strongest model): a top practitioner of the field; finds what is wrong, inconsistent, naive, unverifiable; tests code and numbers itself.
   - **User** (strongest model): the person who reads it or works in it (a new user, a reviewer, the agent that runs it daily); first impression, what confuses, what slows them, what is missing.
   - **Benchmark** (fast model): finds 8–12 of the best comparable works or practices (URLs opened, dated) and tables the gap: convention, who does it, do we, worth it or overkill.
   Factual material (numbers, quotes) always gets the expert critic; anything public gets the user; "is this current best practice" gets the benchmark.
3. **Brief each reader** in parallel, one shot, with this template. Give paths to raw material, never your summary or verdict, never "check that X is good".
   ```
   <paste skills/coding-discipline/SKILL.md verbatim>
   Read only; scratch in <own folder>.
   Target: <paths>. Audience: <who>. Bar: <bar>. Constraints: <owner rules>.
   You are here to criticise, not to be nice.
   Output: ≤ 30 ranked items, each `BLOCKER / MAJOR / MINOR · file:line · problem · exact fix`
   (the replacement sentence or code); claims marked CONFIRMED / WEAKENED / REFUTED with the
   command or source; then one paragraph: the tier it is at today and the 5 changes that move it most.
   ```
4. **Re-check every BLOCKER/MAJOR yourself** (command, file, source). Reviewers are wrong too; drop what fails the check and say why.
5. **Resolve conflicts.** When readers disagree, apply `RULES.md`; if it is silent, keep the item and list it under Owner decisions.
6. **Fix in one pass.** Write the verdict file `REVIEW-<date>.md` next to the work: what is good, what was not, what changed, what was left and why.
7. **Round 2:** one fresh expert critic on the changed work only, asked "what is still wrong". At most 2 rounds; stop when round 2 finds no BLOCKER/MAJOR.
8. **Report to the owner** what the readers found, what you fixed, and what you did not, with the reason.

## Loop mode
For "make it perfect" or "keep improving it". "Perfect" has no end; this loop does: **two clean rounds in a row** (max 5). Clean = no new BLOCKER/MAJOR that survives your check and that you can fix.
1. Before round 1, write `polish-<date>/PLAN.md` next to the target, one line each: target (paths or the command that builds it), reader, bar, owner rules, the checks that must pass (tests, privacy check, demo).
2. Each round: brief a fresh reader (Single review steps 2–3; never pass earlier findings, fixes or scores) → verify (step 4).
3. Sort each item: *fix* (you can, no owner rule broken) or *owner* (what RULES R1 reserves for the owner, taste, publishing, deletes; not asked now).
4. Fix in one pass and run the PLAN checks; a failing check is a BLOCKER next round.
5. Add one row to `ROUNDS.md` (round · score /10 · found · kept · fixed · owner), then commit (RULES R34, every result lands in the repo the same turn).
6. MINORs never keep the loop going. If round 5 is not clean, stop and say what keeps coming back.

## Done when
Single review: `REVIEW-<date>.md` exists and round 2 found no BLOCKER/MAJOR (or 2 rounds ran). Loop mode: one `REPORT.md` ≤ 1 page in plain English: bar, score per round, what changed, what is still not ideal, then **Owner decisions**, numbered, each with your recommendation, asked once (RULES R2, batch questions once).
