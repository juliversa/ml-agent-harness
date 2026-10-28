# TOOLING: Kaggle and compute traps (symptom → fix)
Grep before trial and error. Kaggle CLI 2.x (written against 2.2.x; 1.7.x is a trap, T8). Scripts in `kit/`. New trap → new T-number the same day (R39).

## A. Where jobs run
- **T1 Heavy local job dies, empty log.** On a shared machine: silent cgroup OOM / contention. Local = numpy scoring of cached outputs and cheap screens only; k-fold fits, NN training, submissions run on Kaggle.
- **T2 Backgrounded job vanishes (0-byte log).** `nohup &`, `setsid`, heredoc on stdin get reaped. Write a `.py`, use the harness's `run_in_background` (exception: `watcher.sh`, which can be reaped too: its heartbeat shows in `status.sh`, and the Stop hook blocks when it is > 15 min old); check the log is non-empty; never two heavy jobs at once.
- **T3 Missing shell tools make monitors lie.** If the container lacks `pgrep ps bc unzip jq free pkill`: Scan `/proc/*/cmdline`, `kill -9 <pid>`, `python3 -c` for math/zip/json; poll the output artefact, not the process.
- **T4 GPU time with no speed-up.** numba/CPU loops gain nothing on a GPU: keep them on CPU.

## B. Throughput
- **T5 Sweeps take hours.** The expensive stage reruns: cache it once, sweep the cheap stage, re-profile (a 4-hour particle-filter sweep → 9 min). Skill `kaggle-run`.
- **T6 A long sweep blocks every push.** Both GPU slots held. 2–3 configs per job; budget the scorer too.

## C. Credentials, CLI, push
- **T7 401.** Live credential may be `~/.kaggle/access_token` (`KGAT_`, sent as `Bearer`); a stale `kaggle.json` 401s. Set `KAGGLE_USER`.
- **T8 `--accelerator` dropped → P100 → `no kernel image`.** Needs CLI 2.x; push with `--accelerator NvidiaTeslaT4` (TPU ids change, take the current one from Kaggle's docs; bogus values are accepted silently, so `push_and_watch.sh` allows only `NvidiaTeslaT4` and `Tpu…`, for `--accelerator` and a metadata `machine_shape`; P100 is sm_60, which current torch images do not support). T4 + P100 share ONE ≈ 30 h weekly GPU quota.
- **T9 `enable_gpu: false` ignored.** Delete `machine_shape` when copying GPU metadata to a CPU kernel.
- **T10 Push exits 0 on failure.** Require `successfully pushed` in the output (`push_and_watch.sh` does); a quota rejection prints `Kernel push error`.
  - Invalid dataset/competition/kernel sources (and tags) are dropped with `... could not be added to the kernel` and the push still prints success: `push_and_watch.sh` exits 1 on that line.
- **T11 Session caps.** Batch GPU 2, CPU 5, TPU 1 (queued counts; queue waits 6 h+ cost no quota). Wall: check the current limits (Kaggle docs when written: 12 h CPU/GPU, 9 h TPU per session; a code competition's own run limit binds its submission kernel). Weekly GPU ≈ 30 h, TPU ≈ 20 h (`kaggle quota`). Scripts must tolerate refusal and re-push. Free a slot by superseding with a CPU placeholder of the same `kernel_type`.
- **T12 Phantom kernel id** ("Notebook not found" after a refused push, or dies in ~1 min, empty log). Push under a NEW slug.
- **T13 Copied kernel dir renames someone else's slug.** Strip `id_no` from the copy first.
- **T14 No cancel.** v2 does not stop v1; stop in the web UI (ask the owner) or plan margin. Run `astgate.py` (undefined names) and `depslint.py` (deps) before every push.
- **T15 Only `code_file` uploads.** Ship helpers as a dataset tarball with a path manifest; assert every path.
- **T16 Dataset upload drops subdirs / reports false failure.** Use one tarball or `--dir-mode zip`; verify with `kaggle datasets files <owner>/<slug> --page-size 200 -v`, never by exit code; `status`/`list` lag; never re-upload blindly.
- **T17 Dataset-attach race.** A push seconds after `datasets version` gets the OLD version; wait ~60 s and list files first.

## D. Inputs, outputs, image
- **T18 Nested mounts.** `/kaggle/input/competitions/<slug>`, `/kaggle/input/datasets/<user>/<slug>`: recursive glob for a marker file. `kernel_sources` attaches the CACHED output, never a re-run; use it instead of download + republish (downloads truncate silently). Outputs go to `/kaggle/working`; clone/scratch into `/tmp`. The CLI defaults `enable_internet` to true; a code-competition submission kernel needs `"enable_internet": false` and wheels shipped as a dataset (T21); `push_and_watch.sh` warns when `competition_sources` is set and `enable_internet` is not false.
- **T19 Listing commands (`files`, `list`) return 20 items.** Always `--page-size 200`; count files. `kernels output` pages itself in 2.2.x; `--page-size 200` only cuts round trips. Logs: `--file-pattern '\.log$'`, filter `stream_name=stderr`.
- **T21 Image surprises.** Missing packages (`zarr`, `ilpy`, `pyscipopt`) → bundle wheels as a dataset. pip installs before importing numpy/scipy. numpy 2: `np.ptp(a)`.
- **T23 Kernels assembled from slices** lose imports/constants and discover inputs differently: print found resources at both ends and diff; on directory formats (`.zarr`, `.geff`) `ls d/*.ext` lists their contents: use `ls -d`, check the count.

## E. Submitting
- **T24 Code-comp submit 400/403.** `kaggle competitions submit <comp> -k <user/kernel> -v <N> -f submission.csv -m "<CV>"`; CLI 400 → Python API `competition_submit_code`. Always pass the pushed `--version` to `submit_gate.py`.
- **T25 Limits.** Daily cap resets UTC midnight; the per-competition cap is in `competitions_list(...)`'s `max_daily_submissions`; today's count comes from the submissions list. Push dry-runs the kernel on an empty test dir against the runtime cap: detect it and cap iterations.
- **T26 404 on leaderboard/submit.** Use the full ref from the URL (`.kref`). Forum: `kaggle competitions topics list <slug> -s new`. Leaderboard download is a zip.
- **T27 Background shell drops `cd`.** A `run_in_background` command `cd X && curl -O …` ran in the repo root (cwd not applied), dropping a 1 GB file there. Use absolute output paths (`curl -o /abs/path`) and absolute script paths; never rely on `cd` (R37). Also: `kit/*.sh` need `~/.local/bin` on PATH for the kaggle CLI (setup-competition.sh fails otherwise).
- **T28 pkill/pgrep -f self-match.** `pkill -f "<text>"` / `until ! pgrep -f X` match the calling shell's own command line: the shell kills itself (exit 144) or the loop never ends. Kill by PID (`ps`, then `kill <pid>`). `kaggle datasets create` can 500 with nothing created (list/files then 403): retry once, then confirm the "being created" line.
- **T29 Dataset file cap.** Kaggle datasets hold ≤ 1000 files; the CLI uploads every file first and only then fails ("file count exceeds the maximum of 1000"). Count files before `datasets create`.
