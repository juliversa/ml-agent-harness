#!/usr/bin/env python3
"""The harness measures itself (RULES R20, R33): one row per UTC day from the Claude transcripts → <comp>/agentmeter.csv.
  python3 kit/agentmeter.py <comp> [--days 8] [--since EPOCH]
Columns: date, wM (million price-weighted tokens: input + 1.25 cache_write + 0.1 cache_read + 5 output, all projects:
the usage limit is account-wide), ctx_p50_k / ctx_p90_k (live context of main-session messages, k tokens), compactions,
helper_share (sub-agents + `claude -p` jobs outside the lead's project folder of $LEAD_DIR, share of wM), findings (FINDINGS.md rows dated that day), wM_per_finding.
Days in the window are recomputed; older rows are kept. Transcripts: $CLAUDE_PROJECTS (default ~/.claude/projects).
Cache <comp>/.tokcache.json: path -> [bytes parsed, {msg id: [t, w, ctx, kind]}] (kind m main · s helper · c compaction);
only new bytes of grown files are parsed. --since (used by watcher.sh) also prints: <wM today> <since EPOCH> <last 7 d> in tokens."""
import argparse, csv, json, os, re, time, datetime as dt
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("comp")
ap.add_argument("--days", type=int, default=8)
ap.add_argument("--since", type=float)
a = ap.parse_args()
C = Path(a.comp)
now = time.time()
utc = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc)
day0 = utc(now).replace(hour=0, minute=0, second=0, microsecond=0)
win = (day0 - dt.timedelta(days=max(a.days, 8) - 1)).timestamp()     # rows recomputed; >= 7 d back: the watcher's rolling week
lo = win if a.since is None else min(win, a.since)                    # transcripts parsed


PROJECTS = os.environ.get("CLAUDE_PROJECTS") or os.path.expanduser("~/.claude/projects")
LEAD = os.path.join(PROJECTS, re.sub(r"[^A-Za-z0-9]", "-", str(Path(os.environ.get("LEAD_DIR") or Path(__file__).resolve().parent.parent).resolve())))


def kind(d, path):              # a `claude -p` in the lead's folder is the lead restarted by keeper.py (same LEAD_DIR), not a helper
    sdk = str(d.get("entrypoint", "")).startswith("sdk") and os.path.dirname(path) != LEAD
    if d.get("isSidechain") or "/subagents/" in path or sdk:
        return "s"
    return "m"


cf = C / ".tokcache.json"
try:
    cache = json.loads(cf.read_text())
except Exception:
    cache = {}
new = {}
for root, _, files in os.walk(PROJECTS):
    for fn in files:
        p = os.path.join(root, fn)
        if not fn.endswith(".jsonl") or os.path.getmtime(p) < lo:
            continue
        off, msgs = cache.get(p, [0, {}])
        if any(len(v) != 4 for v in msgs.values()):
            off, msgs = 0, {}                         # cache from an older watcher: rescan
        size = os.path.getsize(p)
        if size < off:
            off, msgs = 0, {}                         # file rewritten: rescan
        if size > off:
            with open(p, "rb") as f:
                f.seek(off)
                buf = f.read()
            end = buf.rfind(b"\n") + 1                # stop at the last complete line
            for line in buf[:end].decode(errors="ignore").splitlines():
                if '"usage"' not in line and "compact_boundary" not in line:
                    continue
                try:
                    d = json.loads(line)
                    t = dt.datetime.fromisoformat(d["timestamp"].replace("Z", "+00:00")).timestamp()
                    if d.get("subtype") == "compact_boundary":
                        if not d.get("isSidechain"):
                            msgs[f"c:{d.get('uuid') or t}"] = [t, 0, 0, "c"]
                        continue
                    m = d["message"]; u = m["usage"]
                except Exception:
                    continue
                ctx = u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
                w = (u.get("input_tokens", 0) + 1.25 * u.get("cache_creation_input_tokens", 0)
                     + 0.1 * u.get("cache_read_input_tokens", 0) + 5 * u.get("output_tokens", 0))
                msgs[m.get("id") or f"{p}:{t}"] = [t, w, ctx, kind(d, p)]
            off += end
        new[p] = [off, {k: v for k, v in msgs.items() if v[0] >= lo}]
tmp = cf.with_suffix(".tmp")
tmp.write_text(json.dumps(new))
os.replace(tmp, cf)
seen = {}                                             # same message id is written once per content block / resumed file
for _, msgs in new.values():
    seen.update(msgs)
recs = list(seen.values())

findings = {}
try:
    for l in (C / "FINDINGS.md").read_text().splitlines()[2:]:
        x = [c.strip() for c in l.split("|")[1:-1]]
        if l.startswith("|") and len(x) >= 2:
            findings[x[1][:10]] = findings.get(x[1][:10], 0) + 1
except OSError:
    pass


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))] if xs else 0


rows = {}
f = C / "agentmeter.csv"
if f.exists():
    rows = {r["date"]: r for r in csv.DictReader(f.open())}
first = utc(win).date()
for i in range((day0.date() - first).days + 1):
    day = first + dt.timedelta(days=i)
    rs = [r for r in recs if utc(r[0]).date() == day]
    if not rs and str(day) not in rows:
        continue
    w = sum(r[1] for r in rs) / 1e6
    ctx = [r[2] for r in rs if r[3] == "m" and r[2] > 0]
    n = findings.get(str(day), 0)
    rows[str(day)] = {"date": str(day), "wM": f"{w:.2f}", "ctx_p50_k": round(pct(ctx, .5) / 1000), "ctx_p90_k": round(pct(ctx, .9) / 1000),
                      "compactions": sum(r[3] == "c" for r in rs),
                      "helper_share": f"{sum(r[1] for r in rs if r[3] == 's') / 1e6 / w:.2f}" if w else "0.00",
                      "findings": n, "wM_per_finding": f"{w / n:.2f}" if n else ""}
cols = ["date", "wM", "ctx_p50_k", "ctx_p90_k", "compactions", "helper_share", "findings", "wM_per_finding"]
with open(f.with_suffix(".tmp"), "w", newline="") as fh:
    wr = csv.DictWriter(fh, cols, extrasaction="ignore")
    wr.writeheader()
    wr.writerows(rows[k] for k in sorted(rows))
os.replace(f.with_suffix(".tmp"), f)
if a.since is not None:
    print(int(sum(r[1] for r in recs if r[0] >= day0.timestamp())), int(sum(r[1] for r in recs if r[0] >= a.since)),
          int(sum(r[1] for r in recs if r[0] >= now - 7 * 86400)))
