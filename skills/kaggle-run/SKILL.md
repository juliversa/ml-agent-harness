---
name: kaggle-run
description: Place, check, push and wait on any Kaggle run (or heavy local job) without the known traps, and cache the expensive stage for sweeps. Use before any training, sweep or push, or /kaggle-run.
---
# kaggle-run
Place, check, push and wait on a run so no known trap wastes compute. RULES R17 (every launch through this skill): a run that cannot change a decision is not pushed. Read TOOLING T8–T19 (Kaggle CLI and kernel traps) before a first push.

Needs: `kit/harvest_check.sh`, `kit/harvest.sh`, `kit/preflight.py`, `kit/push_and_watch.sh`, `kit/status.sh`, `kit/ack.sh`.

## Where
1. Run locally only numpy scoring of cached outputs and cheap screens. Run k-fold fits, NN training and submission kernels on Kaggle (TOOLING T1–T4, local job traps).
2. For local background jobs use `run_in_background` only, check the log is non-empty, and never run two heavy jobs.
3. Cache for sweeps (T5, T6): split the pipeline into (a) expensive + reusable (raw per-item outputs, embeddings, OOF) and (b) cheap + varying (post-processing, late blends per RULES R3, gates). Run (a) once, dumping raw outputs incrementally to a dataset; sweep (b) on the cache.
4. Then re-profile: the new bottleneck is the stage you never timed. Explore on a subset, confirm survivors on the full set; 2–3 configs per kernel.

## Before push
1. **Harvest:** `bash kit/harvest_check.sh <comp> <name-filter>`. Every COMPLETE kernel without a `HARVEST` line is paid compute never read: `COMP_SLUG=<slug> bash kit/harvest.sh <user>/<kernel>`, then read it.
2. **Checklist:** argv printed and read; inputs present on Kaggle (T16, T17); steps × s/step fits the session cap with margin (T11); quota left; not a duplicate of running work; output lands in `/kaggle/working` (T18); CPU smoke for new code; the decision the result changes (none → do not push).
3. **GPU/TPU:** write `<comp>/plans/<kernel slug>.md` with `kind:` (lever runs also `lever:` + `elite-spec:`, PLAYBOOK §7), get a red-team GO, and dump the loader to `<comp>/plans/<slug>-batch.*` (skill `red-team-run`).
4. **Runs > 1 h:** copy `preflight()` from `kit/preflight.py` to the top of the kernel and call it, then run ONE item end to end and print its score.
5. Do pip installs before any third-party import; use `--no-deps` for repos (they shadow the image torch); `strict=True` on weight loads; never silence a fallback that changes device or algorithm. Print a CONTROL line.

## Push
1. New kernel: `kaggle kernels init -p <comp>/code/<slug>`, then set `id`, `code_file`, `competition_sources`, and `enable_internet: false` for code competitions (TOOLING T18).
2. One command lints, checks the red-team gate, pushes and registers (kernel dirs live in `code/`, tracked; TPU accelerator id: TOOLING T8, CLI 2.x):
   ```sh
   COMP_SLUG=<slug> bash kit/push_and_watch.sh <comp>/code/<kernel-slug> --accelerator NvidiaTeslaT4
   ```
3. Exit codes are in the script header. Use `NOLINT=1` only as a decision logged in `log.md`.
4. Never re-push unchanged code hoping for a faster or different GPU; fix the cause (TOOLING T8, T11).

## Wait and harvest
1. `bash kit/status.sh <slug>`; if the watcher is DEAD, restart it with the printed command.
2. Keep ONE background waiter (RULES R21, no polling loops in chat):
   ```sh
   timeout 12h grep -m1 ALERT <(tail -n0 -F <comp>/events.log)
   ```
3. After the harvest: if the row is kept or a lever and has a CV, read its failing items into `<comp>/eda/err-<id>.md` (skill `autopsy`; if it is missing, the watcher raises `noerr`); then `bash kit/ack.sh 'k-<user>_<slug>-*' <experiments.csv id>` (RULES R30, the watcher's tier-1 alerts).
4. Every 5-fold run: save its OOF and test predictions as `<comp>/oof/<id>.npy` and `<comp>/test/<id>.npy` (RULES R3, from week 1; `kit/templates/train.py --from-oof`), so models' errors can be compared and blended late.
5. To recover a kernel, `kaggle kernels pull <user>/<slug>/<N> -p dir` returns pushed version N byte-exact. Logs: T19.

## Done when
The kernel is pushed and registered with one background waiter on `events.log`, its output is harvested, read and acked, and the next step is skill `kaggle-submit`.
