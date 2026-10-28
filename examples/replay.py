#!/usr/bin/env python3
"""Replay a past competition's records through today's watcher, one day at a time.

  python3 examples/replay.py examples/<comp>        prints, per day, the alerts one `kit/watcher.sh <comp> --once` raises

For each day D from the first row to the deadline: a scratch competition holds the rows dated <= D, every date
(rows, .entry, .deadline) shifted by (today - D) so the watcher's clock reads D.
Point in time: experiments.csv holds each value as logged that day; <comp>/known.csv (date,id,column,value,source) adds
what became known later (a rescored CV, the first gold cut, the first LB-noise measure), each only from its own date.
A dotfile named in known.csv (.goldcut, .lbnoise) is absent before its first date; other dotfiles (.lower) are copied.
A stub `kaggle` (no kernels listed, never called) and an empty transcript folder stand in for the live services;
optional kit/extras add-ons are left out (the shipped checks only). Left out too: noerr and stepback (no eda/ or intel/ files in the records,
so they would fire every day) and stuck-time, stuck-tokens (no transcripts, so they cannot fire).
Also lists kept=Y rows on fewer than 5 folds: law 4 (kit/compare.py) reads those as screens, never as kept."""
import csv, datetime as dt, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent / "kit"
sys.path.insert(0, str(KIT))
from exps import num  # noqa: E402  (the watcher's number parser)
DAYKEY = re.compile(r"-\d{4}-(?:\d{2}-\d{2}|W\d{2})(?=\])")   # the watcher keys by today's day or week, not the replayed one
KEY = lambda a: DAYKEY.sub("", a)[1:DAYKEY.sub("", a).index("]")]   # ruler-<day> -> ruler
UNRECORDED = ("noerr", "stepback", "stuck-time", "stuck-tokens")
UNRECORDED_KEY = lambda k: k.startswith(UNRECORDED)


def known_by(known, d, day):
    """{(id, column): value} for the known.csv entries dated <= d; a later entry replaces an earlier one."""
    out = {}
    for k in sorted(known, key=lambda k: day(k["date"])):
        if day(k["date"]) <= d: out[(k["id"], k["column"])] = k["value"]
    return out


def replay(src):
    src = Path(src)
    with open(src / "experiments.csv") as fh:
        rows = list(csv.DictReader(fh))
    hdr = list(rows[0].keys())
    known = []
    if (src / "known.csv").exists():
        with open(src / "known.csv") as fh:
            known = list(csv.DictReader(fh))
    dated = {k["id"] for k in known if k["id"].startswith(".")}
    day = lambda s: dt.date.fromisoformat(s.strip()[:10])
    first, end, today = min(day(r["date"]) for r in rows), day((src / ".deadline").read_text()), dt.datetime.now(dt.timezone.utc).date()
    out = []                                             # (replayed date, alert line)
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        shutil.copytree(KIT, t / "kit", ignore=shutil.ignore_patterns("extras", "__pycache__"))
        (t / "bin").mkdir(); (t / "proj").mkdir()
        (t / "bin" / "kaggle").write_text("#!/bin/sh\nexit 0\n"); (t / "bin" / "kaggle").chmod(0o755)
        env = dict(os.environ, PATH=f"{t / 'bin'}:{os.environ['PATH']}", COMP_ROOT=str(t / "c"),
                   CLAUDE_PROJECTS=str(t / "proj"), PYTHONDONTWRITEBYTECODE="1")
        d = first
        while d <= end:
            shift = today - d
            c = t / "c" / src.name
            shutil.rmtree(t / "c", ignore_errors=True); c.mkdir(parents=True)
            now = known_by(known, d, day)
            for f in (".goldcut", ".lbnoise", ".lower"):
                if f in dated:
                    if (f, "") in now: (c / f).write_text(now[(f, "")] + "\n")
                elif (src / f).exists(): shutil.copy(src / f, c / f)
            for f in (".entry", ".deadline"):
                (c / f).write_text((day((src / f).read_text()) + shift).isoformat() + "\n")
            with open(c / "experiments.csv", "w", newline="") as fh:
                w = csv.DictWriter(fh, hdr); w.writeheader()
                for r in rows:
                    if day(r["date"]) <= d:
                        later = {col: v for (i, col), v in now.items() if i == r["id"]}
                        w.writerow({**r, **later, "date": (day(r["date"]) + shift).isoformat()})
            r = subprocess.run(["bash", str(t / "kit" / "watcher.sh"), src.name, "--once"], env=env, capture_output=True, text=True, timeout=120)
            if r.returncode: sys.exit(f"watcher failed on {d}: {r.stdout}{r.stderr}")
            for f in ("events.log", "digest.md"):
                p = c / f
                for line in (p.read_text().splitlines() if p.exists() else []):
                    if "[" in line and not UNRECORDED_KEY(KEY(line[line.index("["):])): out.append((d.isoformat(), line[line.index("["):]))
            d += dt.timedelta(1)
    screens = [r["id"] for r in rows if (r.get("kept") or "").strip().lower() in ("y", "yes", "1", "true") and (num(r.get("folds")) or 5) < 5]
    return out, screens


if __name__ == "__main__":
    alerts, screens = replay(sys.argv[1])
    days = {}
    for d, a in alerts: days.setdefault(KEY(a), []).append((d, a))
    for k, v in days.items():       # first day each alert fired, its message then, and how many replayed days it was up
        print(f"{v[0][0]}  {DAYKEY.sub('', v[0][1])}  (up {len(v)} d, last {v[-1][0]})")
    print(f"kept=Y on < 5 folds ({len(screens)}): {' '.join(screens) or '-'}; law 4 reads these as screens (kit/compare.py), not kept")
