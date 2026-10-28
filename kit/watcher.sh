#!/bin/bash
HARNESS_ROOT="${HARNESS_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
# Watcher for one competition (RULES.md R21, R30). No Claude involved. Polls every 300 s. Runs from kit/; the competition is $COMP_ROOT/<slug>.
# Record formats: PLAYBOOK.md §7 "Records" (read by the watcher; conventions not checked).
#   COMP_ROOT=<dir> nohup bash kit/watcher.sh <slug> >/dev/null 2>&1 &      (one pass only: kit/watcher.sh <slug> --once)
# Reads  <comp>/kernels.txt (one <user>/<kernel> per line), <comp>/FINDINGS.md, <comp>/experiments.csv, <comp>/.entry, <comp>/.deadline, <comp>/.lower, <comp>/.goldcut, <comp>/.lbnoise,
#        Claude transcripts ($CLAUDE_PROJECTS, default ~/.claude/projects), `kaggle kernels status`.
# Writes <comp>/events.log (UTC lines), <comp>/.tokens_today (rewritten every pass = heartbeat), <comp>/.tokens_week (rolling 7 d),
#        <comp>/.tokcache.json, <comp>/.kstate, <comp>/.kfail/, <comp>/.alerts/ (dedup), <comp>/.lock (one watcher per comp).
# Writes also <comp>/agentmeter.csv (kit/agentmeter.py), <comp>/digest.md (tier-2 alerts), <comp>/STATUS.md (kit/status.sh, every pass).
# 11 alert kinds (no network push; RULES R30). Tier 1 = k-*, unreach-*, budget, gpu-idle, freeze, finals, csvbad, uncommitted:
#   `ALERT [<key>] <message>` in events.log; the Stop hook sends the agent back once until `kit/ack.sh <key> <exp-id|reason>`. Tier 2 = the rest: digest.md.
# Key (.alerts/<key>; * = once ever, else at most every 3 h):
#   k-<ref>-<status>  kernel complete/error/cancel          unreach-<ref>   no kernel status 3 passes running
#   budget            > ${TOKEN_ALERT_M:-45}M weighted today (RULES R20)    gpu-idle        no kernel running for 12 h
#   context           today's median main-session live context > CONTEXT_ALERT_TOKENS (150k; agentmeter.csv, RULES R33)
#   uncommitted       files under <comp> changed > 2 h ago and not committed (RULES R34; only when <comp> is in a git repo)
#  *csvbad            a row with a missing/extra field, a non-ISO date or (non-floor) no parent
#   ruler             >= 5 five-fold subs: residual SD of public around its linear fit on CV > 1.5 x .lbnoise, slope < 0.5 over a CV range >= 3 x .lbnoise, or .lbnoise empty
#   plateau           14-d gain in best kept 5-fold oof_mean / 2 < (.goldcut in CV units - best) / weeks left (law 9); else 7 d flat.
#                     .goldcut -> CV units: minus median(public - oof_mean) over scored 5-fold subs (PLAYBOOK "board-adjusted"); no scored sub: none (7 d flat)
#  *freeze/*finals    deadline -10/-5 d (deadline passed: watcher exits)
# Optional add-on checks: every kit/extras/*.sh is sourced once per pass after these (none ship with the repo).
case "${1:-}" in ""|-*) echo "usage: watcher.sh <slug> [--once]" >&2; exit 2;; esac
SLUG="$1"; ONCE="${2:-}"
command -v kaggle >/dev/null || { echo "watcher: kaggle not on PATH" >&2; exit 2; }
K="$(cd "$(dirname "$0")" && pwd)"; C="${COMP_ROOT:-$HARNESS_ROOT/competitions}/$SLUG"
[ -d "$C" ] || { echo "no folder $C"; exit 1; }
for f in .entry .deadline; do   # a typo here would silence or flood every clock alert
  [ ! -s "$C/$f" ] || { grep -qxE '[0-9]{4}-[0-9]{2}-[0-9]{2}' "$C/$f" && date -u -d "$(cat "$C/$f")" +%s >/dev/null 2>&1; } \
    || { echo "bad date in $C/$f: '$(head -c 40 "$C/$f")' (want YYYY-MM-DD)" >&2; exit 2; }
done
exec 9>>"$C/.lock"   # append: a second watcher must not truncate the holder's PID
flock -n 9 || { echo "watcher already running: PID $(head -c 20 "$C/.lock") holds $C/.lock; kill it or wait for its next pass"; exit 1; }
echo $$ > "$C/.lock"   # same inode: the lock stays held
mkdir -p "$C/.alerts" "$C/.kfail"; touch "$C/.kstate" "$C/events.log" "$C/kernels.txt"
[ -e "$C/.last_running" ] || touch "$C/.last_running"     # GPU-idle clock starts when the watcher starts
log() { echo "$(date -u +%FT%TZ) $*" >> "$C/events.log"; }

alert() {  # alert <key> <message> — at most once per 3 h per key. Tier 1 → ALERT line (Stop hook sends the agent back once until kit/ack.sh); rest → digest.md
  local f="$C/.alerts/$1"
  [ -n "$(find "$f" -mmin -180 2>/dev/null)" ] && return
  touch "$f"
  case "$1" in k-*|unreach-*|budget|gpu-idle|freeze|finals|csvbad*|uncommitted) log "ALERT [$1] $2";;
    *) echo "$(date -u +%FT%TZ) [$1] $2" >> "$C/digest.md";; esac
}
once() { [ -e "$C/.alerts/$1" ] || alert "$@"; }   # once ever per key (.alerts/<key> kept)

# Weighted tokens and the daily agentmeter.csv row (kit/agentmeter.py).
# Prints: <today UTC> <since epoch $1> <last 7 d>.
tokens() { python3 "$K/agentmeter.py" "$C" --since "$1"; }

# exps <days left> -> "<n scored 5-fold rows> <bad csv lines or 0> <ruler failure or na> <plateau message or ->" (tab-separated; kit/exps.py)
exps() { python3 "$K/exps.py" "$C" "$1"; }

while :; do
  touch "$C/.tokens_today"                           # heartbeat first (Stop hook), so a slow API pass is not a dead watcher
  # 1. kernels: log status changes, alert on complete/error
  running=0
  while read -r k _; do
    k=${k%$'\r'}; [ -z "$k" ] || [ "${k#\#}" != "$k" ] && continue
    kk=${k//\//_}                                    # alert/fail key = full ref (no basename collisions)
    case "$(awk -v k="$k" '$1==k{print $2}' "$C/.kstate")" in complete|error|cancel*) continue;; esac   # finished: no API call (a push resets it)
    s=$(timeout 60 kaggle kernels status "$k" </dev/null 2>/dev/null 9>&- | grep -o 'KernelWorkerStatus\.[A-Z_]*' | cut -d. -f2 | tr A-Z a-z)
    kf="$C/.kfail/$kk"
    if [ -z "$s" ]; then                             # API hiccup: retry; 3 empty passes in a row = alert
      n=$(( $(cat "$kf" 2>/dev/null || echo 0) + 1 )); echo $n > "$kf"
      [ $n -ge 3 ] && alert "unreach-$kk" "unreachable $k (no status $n passes)"
      continue
    fi
    rm -f "$kf"
    old=$(awk -v k="$k" '$1==k{print $2}' "$C/.kstate")
    case "$s" in running|queued) running=1; rm -f "$C/.alerts/k-$kk-"*;; esac   # re-run: its next done/fail alerts again
    [ "$s" = "$old" ] && continue
    log "KERNEL $k $s"
    { grep -v "^$k " "$C/.kstate"; echo "$k $s"; } > "$C/.kstate.tmp"; mv "$C/.kstate.tmp" "$C/.kstate"
    case "$s" in complete|error|cancel*) alert "k-$kk-$s" "kernel $k $s";; esac
  done < "$C/kernels.txt"
  [ $running = 1 ] && touch "$C/.last_running"

  # 2. tokens (agentmeter): context and budget
  fm=$(stat -c %Y "$C/FINDINGS.md" 2>/dev/null || date +%s)   # fm, since: read by kit/extras add-ons
  read -r today since week <<< "$(tokens "$fm")"
  [ -n "$today" ] || log "agentmeter failed"; today=${today:-0} since=${since:-0}   # since: read by kit/extras
  echo "$today" > "$C/.tokens_today"; echo "$week" > "$C/.tokens_week"
  p50=$(awk -F, -v d="$(date -u +%F)" '$1==d{print $3}' "$C/agentmeter.csv" 2>/dev/null)
  [ "${p50:-0}" -gt $(( ${CONTEXT_ALERT_TOKENS:-150000} / 1000 )) ] && alert context "context: median main-session context today ${p50}k (> $(( ${CONTEXT_ALERT_TOKENS:-150000} / 1000 ))k, RULES R33): hand off sooner"
  [ "$today" -gt $(( ${TOKEN_ALERT_M:-45} * 1000000 )) ] && alert budget "token budget: $((today/1000000))M weighted today (> ${TOKEN_ALERT_M:-45}M, RULES R20)"

  # 3. GPU idle: no kernel running for 12 h
  gi_h=$(( ($(date +%s) - $(stat -c %Y "$C/.last_running")) / 3600 ))
  [ "$gi_h" -ge 12 ] && alert gpu-idle "GPU idle: no kernel running for ${gi_h} h"

  # 3b. uncommitted: files under the competition changed > 2 h ago and still not in git (RULES R34); files the harness writes excluded
  if git -C "$C" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    uc=0; while IFS= read -r -d '' f; do [ -n "$(find "$C/$f" -maxdepth 0 -mmin +120 2>/dev/null)" ] && uc=$((uc + 1)); done \
      < <(git -C "$C" ls-files -m -o --exclude-standard -z -- . ':!events.log' ':!acks.txt' ':!keeper.md' ':!digest.md' ':!STATUS.md' ':!agentmeter.csv')
    [ "$uc" -gt 0 ] && alert uncommitted "uncommitted: $uc files under $SLUG changed > 2 h ago and not committed (RULES R34)"
  fi

  # 4. experiments.csv reads (PLAYBOOK laws 4/9, §7)
  now=$(date +%s); dd=999
  if [ -s "$C/.deadline" ]; then                     # Kaggle closes 23:59 UTC on the deadline date: the watcher runs to its end
    left=$(( $(date -u -d "$(cat "$C/.deadline")" +%s) + 86400 - now ))
    [ "$left" -le 0 ] && { log "deadline passed: watcher exits"; exit 0; }
    dd=$(( (left - 1) / 86400 ))                     # whole days left after today: 0 on the deadline date
  fi
  IFS=$'\t' read -r n bad ruler pl <<< "$(exps "$dd")"
  [ "$bad" != 0 ] && for b in ${bad//,/ }; do case "$b" in *:noparent) once "csvbad-${b%:*}" "csvbad: experiments.csv line ${b%:*}: parent is empty on a non-floor row (PLAYBOOK §7)";;
    *) once "csvbad-$b" "csvbad: experiments.csv line $b has a missing/extra field or a non-ISO date";; esac; done
  [ "$ruler" != na ] && alert ruler "ruler: CV vs public over $n subs: $ruler"
  [ "${pl:--}" != - ] && alert plateau "plateau: $pl (PLAYBOOK law 9: bigger lever)"
  # deadline clocks, once each: -10 d freeze, -5 d finals (PLAYBOOK §4)
  [ "$dd" -le 10 ] && once freeze "day -$dd: freeze: no new families, scale the best"
  [ "$dd" -le 5 ] && once finals "day -$dd: finals: red-team 2 candidates (law 13) + the owner ticks them (R19)"

  # 5. optional add-on checks (sourced: they see the variables above)
  for x in "$K"/extras/*.sh; do [ -f "$x" ] && . "$x"; done

  # 6. STATUS.md: generated every pass (RULES R30); the lead keeps NOW.md
  COMP_ROOT="$(dirname "$C")" bash "$K/status.sh" "$SLUG" > "$C/STATUS.md.tmp" 2>/dev/null 9>&- && mv "$C/STATUS.md.tmp" "$C/STATUS.md"

  [ "$ONCE" = "--once" ] && break
  sleep 300 9>&-   # fd 9 closed: a sleeping child must not hold the lock
done
