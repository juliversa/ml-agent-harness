#!/usr/bin/env python3
"""The keeper (RULES R30, R33): run from cron every 2-3 h so an idle lead does not wait for the owner. No LLM in it.
  python3 kit/keeper.py
For each live competition (same rule as hooks/check_stop.py):
  lead active (a main-session transcript of $LEAD_DIR written < 2 h ago) -> no restarts;
  else a dead watcher is restarted, and a stuck lead (unacked tier-1 alerts, or no new experiments.csv row / PUSH or HARVEST event in 24 h)
  gets a fresh headless `claude -p` in $LEAD_DIR (at most one per pass: R11 one lead; the rest wait for the next pass), unless today's tokens are over the R20 alert level ($TOKEN_ALERT_M, default 45, in M) or the last two
  restarts made no progress (no new experiments row, push/harvest event or commit): then it stops and tells the owner.
Notifications (kit/notify.sh): restarted, stopped, owner decision (NOW.md BLOCKED line naming the owner, once per text),
one daily summary (first run after 08:00 in $OWNER_TZ); at most 3 notes a day per competition besides the summary and
owner decisions (never capped).
Every action -> one line in <comp>/keeper.md; state in <comp>/.keeper (JSON); the lead's output -> <comp>/keeper.log.
Env: COMP_ROOT (default <repo>/competitions), LEAD_DIR (where the lead runs, default <repo>), CLAUDE_BIN, CLAUDE_PROJECTS,
OWNER_TZ, TOKEN_ALERT_M, NTFY_TOPIC / NTFY_URL (read by notify.sh)."""
import csv, datetime as dt, json, math, os, re, shutil, subprocess, sys, time
from statistics import median
from pathlib import Path

KIT = Path(__file__).resolve().parent
sys.path.insert(0, str(KIT / "hooks"))
from check_stop import live, open_alerts, watcher_dead

ROOT = Path(os.environ.get("COMP_ROOT") or KIT.parent / "competitions")
LEAD = Path(os.environ.get("LEAD_DIR") or KIT.parent).resolve()
PROJ = Path(os.environ.get("CLAUDE_PROJECTS") or Path.home() / ".claude" / "projects") / re.sub(r"[^A-Za-z0-9]", "-", str(LEAD))
NOW = time.time()
os.environ["TZ"] = os.environ.get("OWNER_TZ") or "UTC"
time.tzset()
DAY, HOUR = time.strftime("%Y-%m-%d"), time.localtime().tm_hour       # the owner's day and hour
BUDGET, NOTES = float(os.environ.get("TOKEN_ALERT_M") or 45) * 1e6, 3     # R20 alert level, as watcher.sh; notes a day besides the summary
RESTARTED = []                                                          # competition whose lead this pass restarted (at most one, R11)
PROMPT = ("You are the lead (CLAUDE.md). The keeper restarted you for competition {slug}: the last lead was idle ({why}). "
          "Read {c}/STATE.md, NOW.md and STATUS.md. Act on the open tier-1 alerts and ack each (kit/ack.sh). "
          "Continue NOW / NEXT; keep NOW.md current. Stop when nothing is left to do without the owner.")


def lead_idle_h():
    ts = [p.stat().st_mtime for p in PROJ.glob("*.jsonl")]               # top level only: sub-agents live in <session>/subagents/
    return (NOW - max(ts)) / 3600 if ts else float("inf")


def events(c):
    """Lead actions in events.log: PUSH (push_and_watch.sh) and HARVEST (harvest.sh) lines; the watcher's own lines
    (ALERT, KERNEL, agentmeter failed, ...) are not progress."""
    try:
        return [l for l in (c / "events.log").read_text(errors="replace").splitlines() if l.split()[1:2] in (["PUSH"], ["HARVEST"])]
    except OSError:
        return []


def mark(c):
    """Progress marker: experiments rows, lead-action events, last commit touching the folder."""
    try:
        rows = len((c / "experiments.csv").read_text().splitlines())
    except OSError:
        rows = 0
    git = subprocess.run(["git", "-C", str(c), "log", "-1", "--format=%ct", "--", "."], capture_output=True, text=True).stdout.strip()
    return [rows, len(events(c)), git]


def quiet_24h(c):
    """No new experiments.csv row and no lead-action event in 24 h."""
    e = c / "experiments.csv"
    if e.exists() and NOW - e.stat().st_mtime < 86400:
        return False
    last = events(c)[-1:]
    try:
        stamp = last[0].split()[0]                                         # 2026-10-28T10:27:05Z (older lines: no seconds)
        t = dt.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ" if stamp.count(":") == 2 else "%Y-%m-%dT%H:%MZ").replace(tzinfo=dt.timezone.utc).timestamp()
    except (IndexError, ValueError):
        return True
    return NOW - t >= 86400


def cut_in_cv(c, gc):
    """The .goldcut (a public-LB number) in CV units, by the watcher's rule (watcher.sh exps): minus median(public - oof_mean)
    over scored 5-fold subs (PLAYBOOK "board-adjusted"); None if no sub."""
    def f(x):
        try:
            v = float(x)
        except (TypeError, ValueError):
            return None
        return v if math.isfinite(v) else None                             # a NaN row never enters the median
    try:
        rows = list(csv.DictReader(open(c / "experiments.csv")))
    except OSError:
        return None
    p = [(f(r.get("oof_mean")), f(r.get("public"))) for r in rows if ("folds" not in r or f(r.get("folds")) == 5)
         and f(r.get("oof_mean")) is not None and f(r.get("public")) is not None]
    return gc - median(y - x for x, y in p) if p else None


def keep(c):
    sf = c / ".keeper"
    try:
        s = json.loads(sf.read_text())
    except (OSError, ValueError):
        s = {}
    s.setdefault("notes", {})
    s["notes"] = {k: v for k, v in s["notes"].items() if k >= DAY}        # only today's count matters

    def log(action, why, title=None, msg=None, summary=False):
        noted = ""
        if title:
            n = s["notes"].get(DAY, 0)
            if summary or n < NOTES:
                subprocess.run(["bash", str(KIT / "notify.sh"), title, msg], timeout=30)
                s["notes"][DAY] = n + (not summary)
                noted = " · noted"
            else:
                noted = " · note capped"
        with open(c / "keeper.md", "a") as fh:
            fh.write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(NOW))} · {action} · {why}{noted}\n")

    alerts = [l for l in (open_alerts(c) if (c / "events.log").exists() else [])   # stuck-* are about a working lead:
              if " ALERT [stuck-" not in l]                                         # an idle one is restarted for the rest or 24 h quiet
    idle = lead_idle_h()
    if idle >= 2:
        hb = watcher_dead(c)
        if hb:
            w = subprocess.Popen(["bash", str(KIT / "watcher.sh"), c.name], env={**os.environ, "COMP_ROOT": str(ROOT)},
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            time.sleep(2)
            if w.poll() is None:
                log("restart-watcher", f"heartbeat {hb}, new watcher PID {w.pid}")
            else:                                                          # e.g. kaggle not on cron's PATH: exit 2
                log("watcher-failed", f"heartbeat {hb}; restarted watcher exited {w.returncode}", f"{c.name}: watcher down",
                    f"watcher restart failed (exit {w.returncode}); run kit/watcher.sh by hand")
        quiet = quiet_24h(c)
        closed = (c / ".deadline").exists() and (c / ".deadline").read_text().strip() < time.strftime("%Y-%m-%d", time.gmtime(NOW))
        if (alerts or quiet) and not closed:                               # after the close nothing is stuck: no lead restarts
            why = f"idle {idle:.1f} h, " + (f"{len(alerts)} open tier-1 alerts" if alerts else "no new experiment or event in 24 h")
            m = mark(c)
            if s.get("last_mark") is not None:                             # the last pass restarted the lead: did it move anything?
                s["fails"] = s.get("fails", 0) + 1 if m == s["last_mark"] else 0
                s["last_mark"] = None                                      # a pass that does not restart is not counted again
            try:
                tok = int((c / ".tokens_today").read_text().split()[0])
            except (OSError, ValueError, IndexError):
                tok = 0
            if s.get("fails", 0) >= 2:
                if not s.get("stopped"):
                    s["stopped"] = True
                    log("stop", f"{why}; 2 restarts made no progress", f"{c.name}: keeper stopped",
                        "stuck twice, stopped: please look")
            elif tok > BUDGET:
                if s.get("budget_day") != DAY:
                    s["budget_day"] = DAY
                    log("no-restart", f"{why}; tokens today {tok / 1e6:.0f}M > {BUDGET / 1e6:g}M (R20)", f"{c.name}: budget",
                        "budget reached, lead not restarted")
            elif not shutil.which(os.environ.get("CLAUDE_BIN", "claude")):
                if s.get("nocli_day") != DAY:
                    s["nocli_day"] = DAY
                    log("no-restart", f"{why}; no claude CLI here", f"{c.name}: lead stuck",
                        f"lead stuck ({why}); restart the lead")
            elif RESTARTED:                                                # R11: one lead, so one headless restart per pass
                log("no-restart", f"{why}; another competition's restart this pass ({RESTARTED[0]})")
            else:
                RESTARTED.append(c.name)
                with open(c / "keeper.log", "a") as out:
                    # runs in LEAD, so its transcript lands in the lead's project folder: agentmeter.py counts it as the lead, not a helper
                    subprocess.Popen([os.environ.get("CLAUDE_BIN", "claude"), "-p", "--permission-mode", "acceptEdits",
                                      PROMPT.format(slug=c.name, c=c, why=why)], cwd=LEAD, stdin=subprocess.DEVNULL,
                                     stdout=out, stderr=out, start_new_session=True)
                s["last_mark"], s["stopped"] = m, False
                s["restarts"] = [t for t in s.get("restarts", []) if NOW - t < 86400] + [NOW]
                log("restart-lead", why, f"{c.name}: lead restarted", f"lead was stuck; restarted ({why})")
    try:
        blocked = next((l.strip() for l in (c / "NOW.md").read_text().splitlines() if l.startswith("BLOCKED")), "")
    except OSError:
        blocked = ""
    if "owner" in blocked.lower() and blocked not in s.get("blocked_sent", []):
        s["blocked_sent"] = s.get("blocked_sent", [])[-9:] + [blocked]
        log("owner-decision", blocked[:200], f"{c.name}: your decision", blocked[:300], summary=True)   # once per text: never capped
    if HOUR >= 8 and s.get("summary_day") != DAY:
        s["summary_day"] = DAY
        st = subprocess.run(["bash", str(KIT / "status.sh"), c.name], capture_output=True, text=True,
                            env={**os.environ, "COMP_ROOT": str(ROOT)}).stdout
        b = re.search(r"BEST: CV ([-+\d.eE]+)", st)
        g = re.search(r"gold cut ([-+\d.eE]+)", st)
        line = f"best CV {b[1] if b else '-'}"
        cut = cut_in_cv(c, float(g[1])) if b and g else None
        if cut is not None:                                                # gap in CV units; .goldcut is a public-LB number
            lower = (c / ".lower").exists() and (c / ".lower").read_text().strip() == "1"
            line += f" · gap to gold {(float(b[1]) - cut) if lower else (cut - float(b[1])):+.4f}"
        elif b and g:
            line += f" · LB cut {g[1]}"                                    # no sub with a public score: cannot convert
        today = sum(time.strftime("%Y-%m-%d", time.localtime(t)) == DAY for t in s.get("restarts", []))
        line += f" · {len(alerts)} open alerts · {today} restarts today"
        log("summary", line, f"{c.name}: daily", line, summary=True)
    sf.write_text(json.dumps(s))


if __name__ == "__main__":
    for c in live(ROOT):
        keep(c)
