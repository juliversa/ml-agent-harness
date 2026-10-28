#!/usr/bin/env python3
"""Stop hook: when the lead's live context passes CONTEXT_ALERT_TOKENS (default 150000), send it back once per
50k step to write the handoff (RULES R33): STATE.md + NOW.md current, then a fresh session reads those and the generated STATUS.md.
Context = input + cache read + cache write of the newest main-thread (not sub-agent) message in the transcript."""
import json, os, sys, tempfile
from pathlib import Path

hook = json.load(sys.stdin)
limit = int(os.environ.get("CONTEXT_ALERT_TOKENS") or 150000)
tp = Path(hook.get("transcript_path") or "/nonexistent")
if hook.get("stop_hook_active") or not tp.is_file():
    sys.exit(0)
with open(tp, "rb") as f:
    f.seek(max(0, tp.stat().st_size - 2_000_000))
    lines = f.read().decode(errors="ignore").splitlines()
ctx = 0
for line in reversed(lines):
    if '"usage"' not in line:
        continue
    try:
        d = json.loads(line)
        u = d["message"]["usage"]
    except Exception:
        continue
    if d.get("isSidechain"):
        continue
    ctx = u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
    break
step = (ctx - limit) // 50000
if ctx < limit:
    sys.exit(0)
mark = Path(tempfile.gettempdir()) / f"ctx-alert-{hook.get('session_id') or tp.stem}"
if mark.exists() and mark.read_text().strip() == str(step):
    sys.exit(0)                                 # already asked at this size
mark.write_text(str(step))
print(f"Context is {ctx // 1000}k tokens (alert at {limit // 1000}k, RULES R33). Write the handoff now: STATE.md "
      "(decisions, numbers, next step) and NOW.md current, commit, then tell the owner a fresh session can take over "
      "from STATE.md, NOW.md and the generated STATUS.md.", file=sys.stderr)
sys.exit(2)
