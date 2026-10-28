#!/usr/bin/env python3
"""Batch jobs outside the lead (RULES R11, R20, R33): one `claude -p` per manifest row; the lead reads only summary.csv.
  python3 kit/fanout.py <jobdir> [--model opus] [-j 4] [--tokens-per-job 300000] [--timeout 3600] [--go] [-- <claude args>]
<jobdir>/manifest.csv: header with an `id` column, one row per job. <jobdir>/brief.md: the brief; {column} fields are filled
per row ({jobdir} = its absolute path). The brief must pass the same check as any helper brief (kit/hooks/check_brief.py, R14).
Without --go: prints the cost estimate (pending jobs × --tokens-per-job; give it in R20 price-weighted tokens) and runs nothing.
With --go: runs pending jobs in <jobdir> (a job is done when out/<id>.json says is_error false; rerun = resume),
then writes <jobdir>/summary.csv: id, status, cost_usd, turns, secs, result (first 200 chars). $CLAUDE_BIN overrides `claude`.
Workers need Read (their inputs) and Write (the brief's Output: file), plus Bash/Grep only if the brief asks for them. `claude -p` cannot ask
for permission and runs in <jobdir>, so allow those tools in settings it loads or with <claude args>."""
import argparse, csv, json, os, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "hooks"))
from check_brief import problem

ap = argparse.ArgumentParser()
ap.add_argument("jobdir")
ap.add_argument("--model", default="opus")
ap.add_argument("-j", type=int, default=4)
ap.add_argument("--tokens-per-job", type=int, default=300000, help="R20 price-weighted tokens per job")
ap.add_argument("--timeout", type=int, default=3600)
ap.add_argument("--go", action="store_true")
argv = sys.argv[1:]
cut = argv.index("--") if "--" in argv else len(argv)   # everything after `--` goes to claude as is
a, extra = ap.parse_args(argv[:cut]), argv[cut + 1:]
J = Path(a.jobdir)
brief = (J / "brief.md").read_text()
if problem(brief):
    sys.exit(f"REFUSING brief.md: {problem(brief)}")
jobs = list(csv.DictReader((J / "manifest.csv").open()))
ids = [r.get("id", "").strip() for r in jobs]
if not jobs or not all(re.fullmatch(r"[A-Za-z0-9_.-]+", i) for i in ids) or len(set(ids)) != len(ids):
    sys.exit("REFUSING: manifest.csv needs an `id` column with unique ids of [A-Za-z0-9_.-]")
(J / "out").mkdir(exist_ok=True)


def result(i):
    try:
        return json.loads((J / "out" / f"{i}.json").read_text())
    except Exception:
        return None


done = lambda i: (result(i) or {}).get("is_error") is False
todo = [r for r in jobs if not done(r["id"].strip())]
w = len(todo) * a.tokens_per_job / 1e6
print(f"{len(todo)} of {len(jobs)} jobs pending · model {a.model} · estimate {w:.1f}M weighted tokens "
      f"({len(todo)} x {a.tokens_per_job // 1000}k; daily budget ≈ 36M, RULES R20)")
if not a.go and todo:
    print("estimate only: rerun with --go to start")
    sys.exit(0)


def run(r):
    i = r["id"].strip()
    vals = {k: (v or "") for k, v in r.items()} | {"jobdir": str(J.resolve())}
    prompt = re.sub(r"\{(\w+)\}", lambda m: vals.get(m[1], m[0]), brief)    # other braces (code) stay as written
    try:
        p = subprocess.run([os.environ.get("CLAUDE_BIN", "claude"), "-p", "--output-format", "json", "--model", a.model, *extra],
                           input=prompt, capture_output=True, text=True, timeout=a.timeout, cwd=J)
        out = p.stdout if p.stdout.strip().startswith("{") else json.dumps({"is_error": True, "result": (p.stderr or p.stdout)[-500:]})
    except subprocess.TimeoutExpired:
        out = json.dumps({"is_error": True, "result": f"timeout after {a.timeout} s"})
    (J / "out" / f"{i}.json").write_text(out)


if a.go and todo:
    with ThreadPoolExecutor(max(1, a.j)) as ex:
        list(ex.map(run, todo))
rows = []
for i in ids:
    d = result(i)
    st = "missing" if d is None else "error" if d.get("is_error") is not False else "ok"
    rows.append({"id": i, "status": st, "cost_usd": (d or {}).get("total_cost_usd", ""), "turns": (d or {}).get("num_turns", ""),
                 "secs": round((d or {}).get("duration_ms", 0) / 1000), "result": " ".join(str((d or {}).get("result", "")).split())[:200]})
with open(J / "summary.csv", "w", newline="") as fh:
    wr = csv.DictWriter(fh, list(rows[0]))
    wr.writeheader()
    wr.writerows(rows)
n = sum(r["status"] == "ok" for r in rows)
cost = sum(float(r["cost_usd"] or 0) for r in rows)
print(f"{n} ok, {len(rows) - n} not ok · ${cost:.2f} · {J / 'summary.csv'}")
sys.exit(0 if n == len(rows) else 1)
