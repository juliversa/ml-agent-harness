#!/usr/bin/env python3
"""Gated Kaggle submission (skill kaggle-submit), code competition (--kernel) or file upload (--file). Any failed check aborts BEFORE the slot is spent.

    python3 submit_gate.py --kernel <user/kernel> --version N --competition <kaggle-ref> [--slug <competition folder>] \\
        --desc "<what changed>" --cv 0.8943 --agg "<how aggregated>" [--source submitted.py] [--log-md <comp>/log.md] [--dry-run]
    file competitions: --file <submission.csv> [--sample <sample_submission.csv>] instead of --kernel/--version
    (step 3 = same header, ids and row count as the sample, no NaN; step 4 skipped)
    instead of --cv/--agg: --no-cv-reason "<why the harness cannot answer>" or --probe "<what the slot measures>"

  0. one gate at a time (flock /tmp/submit_gate.lock); refuse a 3rd submission today (UTC) or one whose
     description already starts with "<--desc> |" today
  1. CV + aggregation, or --no-cv-reason, or --probe; prints the incumbent OOF (kept rows of experiments.csv)
  2. astgate.py clean on --source
  3. --version = latest `PUSH <kernel> vN` in <comp>/events.log (the CLI ignores versions: status/output are the latest;
     an unparsed `v?` push aborts),
     and kernel status COMPLETE
  4. kernel log: no Traceback / DEGRADE / '!!' lines, and not empty (unless --no-log-reason)
"""
import argparse, csv, datetime as dt, fcntl, json, math, os, re, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(os.environ.get("COMP_ROOT", str(Path(os.environ.get("HARNESS_ROOT", Path(__file__).resolve().parent.parent)) / "competitions")))
HERE = Path(__file__).resolve().parent


def die(msg):
    sys.exit(f"\n  ABORT: {msg}\n")


def run(*cmd, timeout=120):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except subprocess.TimeoutExpired:
        die(f"{' '.join(cmd[:3])} timed out after {timeout} s")
    except FileNotFoundError:
        die(f"{cmd[0]} not on PATH")


def log_text(kernel, workdir):
    """Kernel <slug>.log (JSON records) -> concatenated `data` fields. Pulls only the log, bounded at 900 s."""
    run("kaggle", "kernels", "output", kernel, "-p", workdir, "--file-pattern", r"\.log$", timeout=900)
    own = Path(workdir) / f"{kernel.split('/')[1]}.log"
    logs = [own] if own.exists() else sorted(Path(workdir).glob("*.log"))
    if not logs:
        return ""
    raw = logs[0].read_text(errors="replace")
    try:
        return "".join(r.get("data", "") for r in json.loads(raw))
    except (ValueError, TypeError, AttributeError):
        return raw


def comp_dir(ref, slug):
    """Competition folder: --slug, else the one folder whose .kref holds exactly the Kaggle ref."""
    ds = [ROOT / slug] if slug else [d for d in ROOT.iterdir() if (d / ".kref").is_file() and (d / ".kref").read_text().strip() == ref]
    if len(ds) != 1 or not (ds[0] / "experiments.csv").exists():
        die(f"no single competition folder with experiments.csv and .kref = '{ref}' under {ROOT} (found {len(ds)}). Pass --slug <competition folder>.")
    return ds[0]


def _five(v):
    try:
        return v is None or float(v) == 5     # no folds column (old file) counts as 5-fold
    except ValueError:
        return False


def incumbent(d):
    lower = (d / ".lower").exists() and (d / ".lower").read_text().strip() == "1"
    vals = []
    for r in csv.DictReader((d / "experiments.csv").open()):
        if (r.get("kept") or "").strip().lower() in ("y", "yes", "1", "true") and _five(r.get("folds")):
            try:
                vals.append(float(r.get("oof_mean") or "nan"))
            except ValueError:
                pass
    vals = [v for v in vals if v == v]
    return (min if lower else max)(vals) if vals else None, lower


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kernel", default=None, help="<user>/<kernel> (code competition)")
    ap.add_argument("--version", type=int, default=None)
    ap.add_argument("--output-file", default="submission.csv", help="the kernel's output file to submit (code competition)")
    ap.add_argument("--file", default=None, help="submission csv to upload (file competition; no kernel checks)")
    ap.add_argument("--sample", default=None, help="sample submission to check --file against (default <comp>/data/sample_submission.csv)")
    ap.add_argument("--competition", required=True, help="Kaggle ref")
    ap.add_argument("--slug", default=None, help="competition folder (default: the folder whose .kref = --competition)")
    ap.add_argument("--desc", required=True)
    ap.add_argument("--cv", type=float, default=None)
    ap.add_argument("--agg", default=None)
    ap.add_argument("--no-cv-reason", default=None)
    ap.add_argument("--probe", default=None, help="what this slot measures (a measurement, not a score)")
    ap.add_argument("--source", default=None, help="submitted .py, checked by astgate.py")
    ap.add_argument("--no-log-reason", default=None, help="proceed on an EMPTY log; say how the run was verified")
    ap.add_argument("--log-md", default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.cv is not None and not math.isfinite(a.cv):
        ap.error("--cv must be a finite number")
    if bool(a.file) == bool(a.kernel):
        ap.error("pass exactly one of --kernel (with --version) or --file")
    if a.file:
        if not Path(a.file).is_file() or Path(a.file).stat().st_size == 0:
            die(f"--file {a.file}: missing or empty")
        kernel = None
    else:
        if a.version is None:
            ap.error("--kernel needs --version")
        parts = a.kernel.split("/")
        if len(parts) == 3 and parts[2] != str(a.version):
            die(f"--kernel {a.kernel} names a version other than --version {a.version}")
        kernel = "/".join(parts[:2])

    # 0. One gate at a time: two gates in flight both saw "no duplicate" and both submitted.
    lock = open("/tmp/submit_gate.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        die("another submit_gate holds /tmp/submit_gate.lock and will submit when its pulls finish. Wait for it.")
    # Duplicate guard + daily cap: the list shows description, never the kernel, so match today + "<desc> |".
    subs = run("kaggle", "competitions", "submissions", a.competition, "-v", "--page-size", "20")
    if "No submissions found" in subs:
        rows = []
    elif (h := subs.find("ref,")) >= 0 and "description" in subs:
        rows = list(csv.DictReader(subs[h:].splitlines()))
    else:   # API errors print with rc 0
        die(f"submissions list unreadable (no 'ref,' header, no 'No submissions found'):\n    {subs.strip()[:300]}")
    today = [r for r in rows if (r.get("date") or "").startswith(dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"))]
    for r in today:
        if (r.get("description") or "").startswith(f"{a.desc.strip()} |"):
            die(f"DUPLICATE: already submitted today with this --desc:\n    {r}")
    if len(today) >= 2:
        die(f"{len(today)} submissions today (UTC) already: the cap is 2 per day (PLAYBOOK law 14).")

    what = f"file {a.file}" if a.file else f"{kernel} v{a.version}"
    print(f"=== submit gate: {what} — {a.desc} ===")

    # 1. validation number (incumbent = best kept 5-fold row)
    if a.cv is None and not (a.no_cv_reason or a.probe):
        die("no --cv, --no-cv-reason or --probe. A mechanism argument is not a measurement.")
    if a.cv is not None and not a.agg:
        die("--cv without --agg: a CV number without its aggregation is not interpretable.")
    d = comp_dir(a.competition, a.slug)
    inc, lower = incumbent(d)
    if a.cv is not None:
        worse = inc is not None and (a.cv > inc if lower else a.cv < inc)
        print(f"[1] CV {a.cv:.4f} ({a.agg}) vs incumbent OOF {inc if inc is not None else 'none yet'} ({d.name}/experiments.csv)"
              + ("  -- WORSE than incumbent: say why in --desc" if worse else ""))
    else:
        print(f"[1] " + (f"PROBE: {a.probe}" if a.probe else f"NO CV: {a.no_cv_reason}") + f" (incumbent OOF {inc if inc is not None else 'none yet'})")

    # 2. compile-level source check
    if a.source:
        r = subprocess.run([sys.executable, str(HERE / "astgate.py"), a.source], capture_output=True, text=True)
        if r.returncode:
            die(f"astgate: {(r.stdout + r.stderr).strip()[-500:]}")
        print("[2] astgate: clean")
    else:
        print("[2] astgate: SKIPPED (no --source)")

    if a.file:
        check_file(a.file, a.sample or d / "data" / "sample_submission.csv")
    else:
        kernel_checks(a, kernel, d)

    res = f"CV {a.cv:.4f} ({a.agg})" if a.cv is not None else (f"PROBE: {a.probe}" if a.probe else f"NO CV: {a.no_cv_reason}")
    msg = f"{a.desc.strip()} | {res}"
    print(f"\n[5] message: {msg}")
    if a.dry_run:
        print("\nDRY RUN — not submitted.")
        return

    if a.file:
        out = subprocess.run(["kaggle", "competitions", "submit", a.competition, "-f", a.file, "-m", msg],
                             capture_output=True, text=True, timeout=900)
        r = (out.stdout + out.stderr).strip()
        if out.returncode or "successfully" not in r.lower():   # the CLI can exit 0 on an API error
            die(f"submit failed: {r[:500]}")
    else:
        from kaggle.api.kaggle_api_extended import KaggleApi
        api = KaggleApi()
        api.authenticate()
        try:
            resp = api.competition_submit_code(file_name=a.output_file, message=msg, competition=a.competition,
                                               kernel=kernel, kernel_version=a.version)
        except Exception as e:   # HTTP errors raise
            die(f"submit failed: {str(e)[:500]}")
        if not getattr(resp, "ref", 0):   # a response without a submission ref is not a submission
            die(f"submit failed: no submission ref in the response: {getattr(resp, 'message', resp)}")
        r = f"{resp.message} (ref {resp.ref})"
    print(f"SUBMITTED: {r}")
    if a.log_md:
        with open(a.log_md, "a") as fh:
            fh.write(f"\n- **submitted** `{what}` — {a.desc} — {res} — ref {r}\n")
        print(f"recorded in {a.log_md}")


def check_file(path, sample):
    # 3. file shape: same header, same ids in column 1, no empty cells (a wrong file spends the slot and scores 0)
    if not Path(sample).is_file():
        die(f"no sample submission at {sample}: pass --sample <path>")
    with open(sample, newline="", encoding="utf-8-sig") as fs, open(path, newline="", encoding="utf-8-sig") as fp:
        rs, rp = list(csv.reader(fs)), list(csv.reader(fp))
    if not rs:
        die(f"sample submission {sample} is empty")
    if not rp or rp[0] != rs[0]:
        die(f"header {rp[0] if rp else None} != sample header {rs[0]}")
    if len(rp) != len(rs):
        die(f"{len(rp) - 1} rows, sample has {len(rs) - 1}")
    if any(not r for r in rp[1:]):
        die("blank row in the submission file")
    if sorted(r[0] for r in rp[1:]) != sorted(r[0] for r in rs[1:]):
        die(f"ids in column '{rs[0][0]}' differ from the sample")
    bad = [i + 2 for i, r in enumerate(rp[1:]) if len(r) != len(rs[0]) or any(v.strip().lower() in ("", "nan", "inf", "-inf", "+inf", "none", "null") for v in r)]
    if bad:
        die(f"{len(bad)} rows with missing/NaN values, first at line {bad[0]}")
    print(f"[3] file matches the sample: header, {len(rp) - 1} ids, no NaN  [4] kernel checks skipped")


def kernel_checks(a, kernel, d):
    # 3. the latest push is --version (CLI 2.2.3 ignores /N: status and output are always the latest), and it finished
    ev = (d / "events.log").read_text() if (d / "events.log").exists() else ""
    pushed = re.findall(rf"^\S+ PUSH {re.escape(kernel)} v(\d+|\?)$", ev, re.M)
    if not pushed:
        die(f"no '<UTC time> PUSH {kernel} vN' line in {d.name}/events.log: push via push_and_watch.sh")
    if pushed[-1] != str(a.version):
        die(f"latest push of {kernel} in {d.name}/events.log is v{pushed[-1]}, not v{a.version}: "
            "status and log below would describe another version. Push via push_and_watch.sh.")
    st = run("kaggle", "kernels", "status", kernel).strip()
    if "COMPLETE" not in st:
        die(f"kernel not complete: {st}")
    print(f"[3] v{a.version} is the latest push; kernel status: COMPLETE")

    # 4. log health; an empty log proves nothing (notebook kernels write no .log)
    with tempfile.TemporaryDirectory() as td:
        txt = log_text(kernel, td)
    bad = (["Traceback"] if "Traceback" in txt else []) \
        + (["DEGRADE (a runtime guard fired: the scored pipeline is not the one you built)"] if "DEGRADE" in txt else []) \
        + [w.strip() for w in re.findall(r"^!!.*$", txt, re.M)[:5]]
    if bad:
        die("kernel log problems:\n    " + "\n    ".join(bad))
    if not txt.strip():
        if not a.no_log_reason:
            die("[4] kernel log is EMPTY: the health check read nothing. Verify the run, then pass --no-log-reason.")
        print(f"[4] kernel log EMPTY, skipped: {a.no_log_reason}")
    else:
        print(f"[4] kernel log: {len(txt)} chars, no Traceback / DEGRADE / '!!'")


if __name__ == "__main__":
    main()
