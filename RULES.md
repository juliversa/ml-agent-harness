# RULES: the operating contract
Goal: a **gold-medal** finish; every rule below serves it. Cite rule IDs ("per R8"); IDs are stable and never reused; gaps are retired rules. Method is `PLAYBOOK.md`; this file does not restate it.

## Owner decides
- **R1** The owner decides only: joining a comp, going over the compute or token budget, keeping or dropping a self-constraint,
  switching law 4 to budget mode, real money, anything public or irreversible, the 2 final picks. Everything else: decide, state it in one line, go on. No question tools for strategy.
- **R2** Batch questions once, each with an ID, at a checkpoint. Record every answer at once as one dated line in Owner answers (below); never ask twice.
- **R3** Own work only: no weights others trained for the comp (generic ImageNet / Hugging Face backbones OK). External data only if the rules explicitly allow it.
  Best single model first. Save OOF and test predictions of every 5-fold run from week 1 (to compare models' errors). Blend late (when the single model stops improving, or the last two weeks), and only strong, decorrelated members: each within ~1 % of the best CV and OOF correlation below ~0.98 with the others; blend weights fit nested out-of-fold.
- **R4** Default: don't watch for new comps; the owner names the next one.

## Thinking
- **R5** Report the number, the mechanism and the next step that could make it work; never call a path impossible.
- **R6** Never discard a lane: pause it in writing with its number. Close only via its elite run's `kind=lever` experiments.csv id (law 8, D7); reopen with a new mechanism, not a knob.
- **R7** Start from real failing items with their numbers; scale a few → dozens → full. 5–10 hand-read items check a mechanism, never a score.
  The lead hand-reads ~15 raw items itself (pixels, rows, label source; never a helper's description), ≥ 3 of them random controls, ids picked by `kit/pick_items.py`, not by a helper. Day 0: ~1 h on the raw data before reading any helper page.
- **R8** Fast and correct: ≤ 1 cheap smoke test (it can kill a build, never a lane: R6), then the real end-to-end run. Submit a validated gain and fix a known bug the same day.
- **R9** Aim at the gap, not polish; tell the true state, plateaus included. Max 2 variants of one idea, then a new angle or a lower level.
- **R10** Use models to the max: before building on one, list with IDs all it offers (patch maps, layers, attention, scales, uncertainty, prompts, masks).

## Agents
- **R11** One lead (Opus). No manager, standing workers, agent teams or agent-to-agent chat; one session pushes runs (L35). Helpers are one-shot: one file ≤ 1 page in their own scratch folder; parallel bursts only for well-defined batch jobs, sized first (agents × tokens) against R20. Batch jobs run outside the lead: `kit/fanout.py <jobdir>` (manifest.csv + brief.md, cost estimate first, resumable); the lead reads only its `summary.csv`.
  Helpers do the bulk reading (error-analysis, write-up/forum research, data-exploration sweeps); each returns one page: patterns with counts and their chance rate, 5–10 example ids per pattern, and a "didn't fit / weird" section with ≥ 3 ids. The lead decides.
- **R13** Opus for reading, labels, images, error analysis, new pipeline code, red-team; Sonnet for search, listing, mechanical checks. Every reading helper on the strongest model: cut the number of helpers, never the model.
- **R14** Every brief starts with the four rule titles of skill `coding-discipline`, then goal, what is ruled out, raw artefact paths (never your summary), narrow scope, and an `Output:` line (a file path, ≤ 1 page). Hook `check_brief.py` enforces both.
- **R15** Hostile red-team (skill `red-team-run`) before every GPU/TPU run series (one plan per kernel slug; its GO lasts 24 h), plan or decision request to the owner, lane closure, campaign-redirecting number, and the finals. Not for routine subs. Any other deliverable before it reaches the owner or goes out: skill `hostile-review`.

## Compute and submissions
- **R16** Default: free Kaggle quota only; never rent or propose GPU. The full quota (≈ 30 GPU-h + ≈ 20 TPU-h a week, `TOOLING.md` T8, T11) is pre-approved as a standing weekly budget; ask only to exceed it.
- **R17** Compute never idles: one job per accelerator, the next push ready; retry a crash the same day. Every launch through skill `kaggle-run`; a run that can't change a decision is not pushed.
- **R19** Submissions and finals per laws 13–14; the owner ticks the 2 finals; the lead records which in `STATE.md` + `log.md`.
- **R20** Tokens ≈ 36M price-weighted a day, the measured one-lead cost (L35) (input + 1.25·cache_write + 0.1·cache_read + 5·output; watcher alerts > 45M). Never throttle; no saving in the last 48 h.
- **R21** No polling or sleep loops in chat: the watcher writes ALERT lines to `events.log`; keep one background waiter on it.

## Evidence
- **R22** Trust only numbers you reproduced; prose and handoffs are hypotheses. Print a CONTROL line (a known value) first. Never "should work": show command + output. Pre-register expected result and falsifier; recompute an exciting number a second way and decompose it before shipping.
- **R23** Before any report, plan, launch or handoff: a Forgotten / Assumed list (FA1, FA2…), each item checked by a command (`date -u`, `kaggle quota`, `ls`), not memory.
- **R25** A decision = one `experiments.csv` row + one FINDINGS row naming ≥ 1 example id, or it does not count.

## Communication
- **R26** Terse: skill `lean-replies` (full).
- **R27** Reports: one section per question, in the order asked.
- **R28** Every item, arm, notebook and question gets a short stable ID; refer by ID.
- **R29** Times in `OWNER_TZ` (default UTC), logs in UTC.
- **R30** The watcher writes `STATUS.md` (≤ 20 lines, `kit/status.sh`) every pass; the lead keeps `NOW.md` (3 lines: NOW, NEXT, BLOCKED) current after every event. Tier-1 alerts (`ALERT [<key>]` in `events.log`) are acted on, then acked: `kit/ack.sh <key> <exp-id|reason>` (the Stop hook sends the lead back once; a second stop in a row is let through); tier 2 goes to `digest.md`, read at each checkpoint. Notifications (optional, `kit/notify.sh`): keeper only, ≤ 3 a day per competition besides the daily summary; owner decisions uncapped.
- **R31** Never end a turn on a promise: "starting X" means X is running. While nothing waits on the owner, keep working.

## Context, files, safety
- **R33** Small context: tool output ≤ 2k tokens (`tail`/`grep` into files; hook `check_read.py` blocks whole reads of files > 40 KB). One `STATE.md` overwritten in place; never re-derive state. Live context > 150k tokens (hook `check_context.py`): write the handoff (STATE + NOW), commit, and let a fresh session take over from STATE, NOW and the generated STATUS.
- **R34** Every result, dead end (with its number) and helper output lands in the repo the same turn. Commit; never commit data, weights, secrets, private notes.
- **R35** Results live in the repo; never publish competition material.
- **R36** No deletes without the owner's yes; local deletes only of archived, checksum-verified files on a listed set. Never delete Kaggle datasets, kernels or runs.
- **R37** Work from the repo root (the folder holding RULES.md; `kit/…` paths are relative to it), never `cd X && …`; routine tools pre-approved (`kit/settings.example.json`); agent config and hooks live in the repo.
- **R38** Simple code: one train script with flags (`kit/templates/train.py`), one make-sub, one `score.py` per comp; arm vs control read by `kit/compare.py`.
- **R39** Tool trap → `TOOLING.md` the same day; lesson → `LESSONS.md`.

## Owner answers
One line each, newest last: `YYYY-MM-DD · question → answer · rule it changed`.
