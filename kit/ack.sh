#!/bin/bash
HARNESS_ROOT="${HARNESS_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
# Acknowledge tier-1 alerts (RULES R30): the Stop hook (hooks/check_stop.py) then lets the turn end.
#   kit/ack.sh <key> <exp-id|reason>      key as in `ALERT [<key>]`; a glob acks several ('k-*'; '*' = all, incl. key-less lines)
# Appends `<UTC time, seconds> <key> <reason>` to <comp>/acks.txt; acks every alert with that key logged up to now (a later repeat needs a new ack).
# <comp> = $COMP_ROOT/$COMP_SLUG, else the one live competition (a folder with STATE.md).
[ $# -ge 2 ] && [[ "$2" =~ [^[:space:]] ]] || { echo "usage: ack.sh <key> <exp-id|reason>" >&2; exit 2; }
K="$1"; shift
R="${COMP_ROOT:-$HARNESS_ROOT/competitions}"
if [ -n "${COMP_SLUG:-}" ]; then C="$R/$COMP_SLUG"
else
  live=(); for d in "$R"/[a-z0-9]*/; do d=${d%/}; [ -L "$d" ] || [ ! -f "$d/STATE.md" ] || live+=("$d"); done
  [ ${#live[@]} -eq 1 ] || { echo "set COMP_SLUG (${#live[@]} live competitions under $R)" >&2; exit 2; }
  C=${live[0]}
fi
n=0
while read -r k; do [[ "$k" == $K ]] && n=$((n + 1)); done \
  < <(awk '$2 == "ALERT" { print ($3 ~ /^\[[^]]+\]$/) ? substr($3, 2, length($3) - 2) : "" }' "$C/events.log" 2>/dev/null)
[ "$n" -gt 0 ] || { echo "no ALERT [$K] line in $C/events.log: nothing to ack" >&2; exit 1; }
echo "$(date -u +%FT%TZ) $K $*" >> "$C/acks.txt"
echo "acked $n ALERT line(s) [$K] in $(basename "$C"): $*"
