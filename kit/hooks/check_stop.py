#!/usr/bin/env python3
"""Stop hook: sends the agent back once when it tries to end its turn while a live competition has tier-1 ALERT lines (watcher.sh) that no
<comp>/acks.txt line covers (RULES R30, R31): ack = `kit/ack.sh <key> <exp-id|reason>`, same or later UTC second, key glob.
Also when a live competition's watcher heartbeat (.tokens_today, rewritten every pass) is over 15 min old: a dead watcher writes no ALERT lines.
Tier-2 alerts go to digest.md and never block. Exit 2 sends the agent back with the alerts listed; a second stop in a row is let through."""
import fnmatch, json, os, re, sys, time
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent.parent
WATCHER = os.path.relpath(REPO / "kit" / "watcher.sh", os.environ.get("CLAUDE_PROJECT_DIR") or REPO)


def block(msg):            # exit 2 = block; stderr goes to the agent
    print(msg, file=sys.stderr)
    sys.exit(2)


def secs(stamp):   # '…T10:27Z' -> '…T10:27:00Z': events and acks carry seconds; older lines compare as second 00
    return stamp[:-1] + ":00Z" if stamp.count(":") == 1 else stamp


def open_alerts(c):
    """Unacked ALERT lines of competition folder c (whole events.log). Key-less lines (older watcher) match only '*'."""
    try:
        acks = [l.split()[:2] for l in (c / "acks.txt").read_text().splitlines() if len(l.split()) >= 3]
    except OSError:
        acks = []
    out = []
    for l in (c / "events.log").read_text(errors="replace").splitlines():
        if " ALERT " not in l:
            continue
        t, msg = l.split(" ", 1)[0], l.split(" ALERT ", 1)[1]
        key = (re.match(r"\[([^\]]+)\] ", msg) or [None, ""])[1]
        if not any(secs(at) >= secs(t) and fnmatch.fnmatchcase(key, g) for at, g in acks):
            out.append(l)
    return out


def live(root):
    """Live competitions under root: real folders with a STATE.md (also used by kit/keeper.py)."""
    return sorted(p for p in root.glob("[a-z0-9]*") if p.is_dir() and not p.is_symlink() and (p / "STATE.md").exists())


def watcher_dead(c):
    """'N min old' / 'missing' when c's watcher heartbeat (.tokens_today) is over 15 min old and the deadline is not past, else None."""
    hb, dl = c / ".tokens_today", c / ".deadline"
    age = (time.time() - hb.stat().st_mtime) / 60 if hb.exists() else None
    past = dl.exists() and dl.read_text().strip() < time.strftime("%Y-%m-%d", time.gmtime())   # the watcher exits after the deadline
    return None if past or (age is not None and age <= 15) else (f"{age:.0f} min old" if age is not None else "missing")


if __name__ == "__main__":
    if json.load(sys.stdin).get("stop_hook_active"):
        sys.exit(0)
    root = Path(os.environ.get("COMP_ROOT") or Path(__file__).resolve().parent.parent.parent / "competitions")
    todo, dead = [], []
    for c in live(root):
        new = open_alerts(c) if (c / "events.log").exists() else []
        if age := watcher_dead(c):
            dead.append(f"{c.name}: heartbeat .tokens_today {age}"
                        + f"\n    restart: COMP_ROOT='{root}' nohup bash {WATCHER} {c.name} >/dev/null 2>&1 &")   # relative to the project dir, as the allow rule
        if new:
            todo.append(f"{c.name} ({len(new)}): " + " | ".join(l.split(" ALERT ", 1)[1][:300] for l in new[-3:])
                        + f"\n    COMP_SLUG={c.name} bash kit/ack.sh <key> <exp-id|reason>")
    msg = (["Unacked tier-1 ALERT lines. Act on each, then ack it (R30):\n  " + "\n  ".join(todo)] if todo else []) \
        + (["Watcher dead (a dead watcher writes no ALERT lines). Restart it:\n  " + "\n  ".join(dead)] if dead else [])
    if msg:
        block("\n".join(msg))
