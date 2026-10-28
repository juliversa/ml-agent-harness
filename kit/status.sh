#!/bin/bash
HARNESS_ROOT="${HARNESS_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
# One-screen status of a competition (RULES.md R30); watcher.sh writes it to STATUS.md every pass. Read-only. ≤ 20 lines. Owner time zone: OWNER_TZ (default UTC, RULES R29).
#   ./status.sh <slug>
# Needs watcher.sh running (it writes events.log, .tokens_today, .tokens_week, agentmeter.csv, digest.md). Reads NOW.md, acks.txt.
case "${1:-}" in ""|-*) echo "usage: status.sh <slug>" >&2; exit 2;; esac
SLUG="$1"
C="${COMP_ROOT:-$HARNESS_ROOT/competitions}/$SLUG"
[ -d "$C" ] || { echo "no folder $C"; exit 1; }

# Lead alive = minutes since the lead's newest transcript was written: its project folder (LEAD_DIR, default the repo), top level only, as keeper.py
proj="${CLAUDE_PROJECTS:-$HOME/.claude/projects}/$(realpath -m "${LEAD_DIR:-$HARNESS_ROOT}" | sed 's/[^A-Za-z0-9]/-/g')"
newest=$(find "$proj" -maxdepth 1 -name '*.jsonl' -printf '%T@\n' 2>/dev/null | sort -n | tail -1)
if [ -n "$newest" ]; then lead="lead last wrote $(( ($(date +%s) - ${newest%.*}) / 60 )) min ago"; else lead="lead: no transcripts for this repo"; fi
tk() { local v; v=$(cat "$C/$1" 2>/dev/null); echo $(( ${v:-0} / 1000000 )); }
echo "== $SLUG  $(TZ=${OWNER_TZ:-UTC} date '+%F %H:%M %Z')  ${lead}  tokens today $(tk .tokens_today)M · 7 d $(tk .tokens_week)M"
# Heartbeat: watcher rewrites .tokens_today every pass (5 min)
hb=$(stat -c %Y "$C/.tokens_today" 2>/dev/null)
w=$(realpath -m --relative-to="${CLAUDE_PROJECT_DIR:-$HARNESS_ROOT}" "$HARNESS_ROOT/kit/watcher.sh")   # relative to the project dir (kit/watcher.sh in this repo)
restart="restart: COMP_ROOT='$(dirname "$C")' nohup bash $w $SLUG >/dev/null 2>&1 &"   # matches settings.example.json allow
if [ -z "$hb" ]; then echo "watcher: no pass yet ($restart)"
else echo "watcher last pass $(( ($(date +%s) - hb) / 60 )) min ago (>15 = DEAD, $restart)"; fi

# Running kernels = last KERNEL state per kernel in events.log is running/queued
run=$(awk '$2=="KERNEL"{s[$3]=$4} END{for(k in s) if(s[k]=="running"||s[k]=="queued") printf "%s ", k}' "$C/events.log" 2>/dev/null)
echo "running: ${run:-none}"

echo "meter today: $(awk -F, -v d="$(date -u +%F)" '$1==d{printf "%s wM · context p50 %sk p90 %sk · %s compactions · helpers %.0f%% · wM/finding %s", $2, $3, $4, $5, $6*100, ($8==""?"—":$8)}' "$C/agentmeter.csv" 2>/dev/null)"
best=$(python3 - "$C" <<'PY' 2>/dev/null
import csv, sys
C = sys.argv[1]; lo = open(f'{C}/.lower').read().strip() == '1' if __import__('os').path.exists(f'{C}/.lower') else False
def f(x):
    try: v = float(x)
    except Exception: return None
    return v if v == v and abs(v) != float('inf') else None   # NaN / inf rows never count (as kit/exps.py num)
al = [r for r in csv.DictReader(open(f'{C}/experiments.csv')) if f(r.get('oof_mean')) is not None]
rs = [r for r in al if ('folds' not in r or f(r['folds']) == 5) and (r.get('kept') or '').strip().lower() in ('y', 'yes', '1', 'true')]
b = (min if lo else max)(rs, key=lambda r: f(r['oof_mean'])) if rs else None
gc = open(f'{C}/.goldcut').read().strip() if __import__('os').path.exists(f'{C}/.goldcut') else ''
print(f"BEST: CV {b['oof_mean']} ({b['id']}) · LB {b.get('public') or '—'}" if b else f'BEST: — (no kept=Y row yet; {len(al)} scored)', f"· gold cut {gc or '—'}")
PY
)
echo "${best:-BEST: CV —}"
head -3 "$C/NOW.md" 2>/dev/null | cut -c1-150
# Open alerts = tier-1 ALERT lines not covered by an acks.txt line (same rule as hooks/check_stop.py)
open=$(awk -v A="$C/acks.txt" 'BEGIN { while ((getline l < A) > 0) { split(l, x, " "); r = x[2]; gsub(/\./, "\\.", r); gsub(/\*/, ".*", r); gsub(/\?/, ".", r); at[++n] = s(x[1]); re[n] = "^" r "$" } }
  function s(t) { return (gsub(/:/, ":", t) == 1) ? substr(t, 1, length(t) - 1) ":00Z" : t }   # no seconds: second 00 (check_stop.secs)
  $2 == "ALERT" { k = ($3 ~ /^\[[^]]+\]$/) ? substr($3, 2, length($3) - 2) : ""; ok = 0
    for (i = 1; i <= n; i++) if (at[i] >= s($1) && k ~ re[i]) ok = 1
    if (!ok) print }' "$C/events.log" 2>/dev/null)
echo "-- OPEN ALERTS: $(printf '%s' "$open" | grep -c .) (ack: kit/ack.sh <key> <exp-id|reason>)"
printf '%s\n' "$open" | grep . | tail -3 | cut -c1-150
echo "-- digest (tier 2, last 3 of $(cat "$C/digest.md" 2>/dev/null | grep -c .))"
tail -3 "$C/digest.md" 2>/dev/null | cut -c1-150
echo "-- FINDINGS (last 3)"
sed -n '3,$p' "$C/FINDINGS.md" 2>/dev/null | grep '^|' | tail -3 | cut -c1-150
