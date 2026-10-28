#!/usr/bin/env bash
HARNESS_ROOT="${HARNESS_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
# SessionStart hook (kit/settings.example.json). Prints each live competition's STATUS.md, then STATE.md, then the boot order. Never blocks.
# Live = a real folder (not a symlink, not _*) under competitions/ with a STATE.md.
C=${COMP_ROOT:-$HARNESS_ROOT/competitions}; n=0
for d in "$C"/[a-z0-9]*/; do
  d=${d%/}; [ -L "$d" ] && continue; [ -f "$d/STATE.md" ] || continue
  n=$((n+1)); echo "── $(basename "$d") ──"
  head -20 "$d/STATUS.md" 2>/dev/null; echo "·· STATE ··"; sed -n '/^# /,$p' "$d/STATE.md" | head -20
  COMP_ROOT="$C" bash "$HARNESS_ROOT/kit/status.sh" "$(basename "$d")" 2>/dev/null | grep -m1 "^watcher"   # a new box has no watcher running: restart it if DEAD
done
[ "$n" -eq 0 ] && echo "No live competition. Wait for the owner to name one (RULES R4), then run the kaggle-new-competition skill."
echo "Boot ($HARNESS_ROOT/CLAUDE.md): $HARNESS_ROOT/RULES.md → $HARNESS_ROOT/PLAYBOOK.md → the live competition's STATUS.md → STATE.md. Everything else on demand."
exit 0
