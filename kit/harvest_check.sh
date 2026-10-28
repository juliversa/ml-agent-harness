#!/usr/bin/env bash
HARNESS_ROOT="${HARNESS_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)}"
# Every COMPLETE kernel with no HARVEST line for its latest push (outputs never pulled and read). Run before every push.
# Kernel list comes from the Kaggle API; an empty answer REFUSES (exit 1) instead of printing an empty table.
# USAGE:  bash harvest_check.sh <competition-dir> <kernel-name-filter>     (KAGGLE_USER required)
set -u
[ $# -ge 2 ] || { echo "usage: harvest_check.sh <comp-dir> <kernel-name-filter>" >&2; exit 2; }
D="$1"; FILTER="$2"
U=${KAGGLE_USER:?set KAGGLE_USER}
cd "$D" || { echo "FATAL: no such competition dir: $D"; exit 2; }

KS=$(for p in $(seq 1 20); do   # 100 per page; a short page is the last
       pg=$(timeout 120 kaggle kernels list -m --page-size 100 --page "$p" -v 2>/dev/null | awk -F, 'NR>1 && $1 ~ /\// {print $1}')
       [ -n "$pg" ] && echo "$pg"; [ "$(echo "$pg" | grep -c /)" -lt 100 ] && break
     done | sed 's#.*/##' | grep -- "$FILTER" | sort -u)
if [ -z "$KS" ]; then
  echo "REFUSING: the Kaggle API returned no kernels matching '$FILTER'."
  echo "   That is NOT the same as 'nothing to harvest' -- it means this check did not run."
  echo "   Fix the API/auth or the filter, then re-run. Do not proceed as if the sweep was clean."
  exit 1
fi

# Harvested = a "HARVEST <ref> vN" line (written by harvest.sh) for the latest pushed version. Mentions in notes do not count.
EV="$PWD/events.log"
printf "%-34s %-10s %s\n" KERNEL STATUS HARVESTED
n_unharvested=0; n_unknown=0
for k in $KS; do
  st=$(timeout 45 kaggle kernels status "$U/$k" 2>&1 | grep -oE 'COMPLETE|ERROR|RUNNING|QUEUED|CANCEL[A-Z]*' | head -1)
  pv=$(sed -n "s#^[^ ]* PUSH $U/$k v\([0-9?]*\)\$#\1#p" "$EV" 2>/dev/null | tail -1)
  if [ -n "$pv" ]; then h=$(grep -cE "^[^ ]+ HARVEST $U/$k v${pv//\?/\\?}\$" "$EV" 2>/dev/null)
  else h=$(grep -cE "^[^ ]+ HARVEST $U/$k v[0-9?]+\$" "$EV" 2>/dev/null); fi
  flag=""
  if [ "$st" = "COMPLETE" ] && [ "${h:-0}" -eq 0 ]; then flag="  <-- UNHARVESTED: COMP_SLUG=$(basename "$PWD") bash kit/harvest.sh $U/$k"; n_unharvested=$((n_unharvested+1)); fi
  [ "$st" = "ERROR" ] && flag="  <-- crashed; check no note claims it is running"
  [ -z "$st" ] && { flag="  <-- status unreadable: this check did not run for it"; n_unknown=$((n_unknown+1)); }
  printf "%-34s %-10s %-4s%s\n" "$k" "${st:-?}" "${h:-0}" "$flag"
done
echo
echo "Checked $(echo "$KS" | wc -w) kernels; $n_unharvested UNHARVESTED, $n_unknown unreadable."
echo "Any row flagged UNHARVESTED is compute already paid for and never read."
[ $((n_unharvested + n_unknown)) -eq 0 ]
