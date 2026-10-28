#!/usr/bin/env bash
HARNESS_ROOT="${HARNESS_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)}"
# Pull a COMPLETE (or ERROR: its log says why) kernel's outputs into <comp>/runs/<kernel>/v<N>/ and record "HARVEST <ref> vN" in <comp>/events.log.
# harvest_check.sh counts a kernel as read only from that line. Read the outputs in the same turn (FINDINGS row).
#   COMP_SLUG=<slug> harvest.sh <user>/<kernel>
set -u
REF="${1:?usage: COMP_SLUG=<slug> harvest.sh <user>/<kernel>}"
COMP="${COMP_ROOT:-$HARNESS_ROOT/competitions}/${COMP_SLUG:?set COMP_SLUG=<slug>}"; [ -d "$COMP" ] || { echo "no $COMP"; exit 2; }
V=$(sed -n "s#^[^ ]* PUSH $REF v\([0-9?]*\)\$#\1#p" "$COMP/events.log" 2>/dev/null | tail -1); V=${V:-?}
st=$(timeout 45 kaggle kernels status "$REF" 2>&1)
TAG=""; echo "$st" | grep -q COMPLETE || { echo "$st" | grep -q ERROR && TAG=" (error)"; } || { echo "REFUSING: $REF is not COMPLETE or ERROR: $st"; exit 1; }
OUT="$COMP/runs/${REF##*/}/v$V"; TMP=$(mktemp -d "$COMP/.pull.XXXX"); trap 'rm -rf "$TMP"' EXIT
timeout 900 kaggle kernels output "$REF" -p "$TMP" --page-size 200 >"$TMP.log" 2>&1; rc=$?   # pages itself; 200 cuts round trips (T19)
{ [ $rc -eq 0 ] && [ -n "$(ls -A "$TMP")" ]; } || { echo "REFUSING: pull failed (rc $rc) or empty; not recorded as harvested: $(head -c 300 "$TMP.log")"; rm -f "$TMP.log"; exit 1; }
rm -f "$TMP.log"; [ -e "$OUT" ] && OUT="$OUT-$(date -u +%Y%m%dT%H%M)"   # never overwrite an earlier pull (R36)
mkdir -p "$(dirname "$OUT")"; mv "$TMP" "$OUT"
echo "$(date -u +%FT%TZ) HARVEST $REF v$V$TAG" >> "$COMP/events.log"
echo "harvested $REF v$V$TAG -> $OUT ($(ls "$OUT" | wc -l) files); now read it and write the FINDINGS row"
