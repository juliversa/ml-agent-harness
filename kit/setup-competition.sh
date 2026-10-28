#!/usr/bin/env bash
HARNESS_ROOT="${HARNESS_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"   # repo root; override with HARNESS_ROOT=
# Scaffold a new competition (PLAYBOOK.md §3–§4). Files render from kit/templates/.
#   ./setup-competition.sh <slug> "Full Name" <deadline YYYY-MM-DD> [kaggle-ref]
#   kaggle-ref = the competition id in its kaggle.com URL, when it differs from <slug>.
# Creates STATE.md, WEEK0.md, NOW.md, STATUS.md (kit/status.sh; then the watcher every pass), FINDINGS.md, experiments.csv, log.md, kernels.txt, events.log, .entry, .deadline, .kref, .lower, .goldcut, .lbnoise,
# and dirs intel/ code/ plans/ retrospective/ eda/ data/; checks KREF on Kaggle, starts the watcher (kit/watcher.sh, run in place).
set -e
SLUG="$1"; NAME="${2:-$1}"; DEADLINE="$3"; KREF="${4:-$1}"
[ -n "$SLUG" ] && [ -n "$DEADLINE" ] || { echo "usage: $0 <slug> \"Full Name\" <YYYY-MM-DD> [kaggle-ref]"; exit 1; }
echo "$SLUG" | grep -qxE '[a-z0-9][a-z0-9-]*' || { echo "bad slug: $SLUG (lowercase letters, digits, hyphens)"; exit 1; }
DEST="${COMP_ROOT:-$HARNESS_ROOT/competitions}/$SLUG"
[ -e "$DEST" ] && { echo "refusing: $DEST already exists"; exit 1; }
TODAY=$(date -u +%F)
echo "$DEADLINE" | grep -qxE '[0-9]{4}-[0-9]{2}-[0-9]{2}' && date -u -d "$DEADLINE" +%s >/dev/null 2>&1 \
  && [ "$(date -u -d "$DEADLINE" +%s)" -ge "$(date -u -d "$TODAY" +%s)" ] || { echo "bad deadline: $DEADLINE (want YYYY-MM-DD, today or later)"; exit 1; }
DAYS=$(( ( $(date -u -d "$DEADLINE" +%s) - $(date -u -d "$TODAY" +%s) ) / 86400 ))
WEEKS=$(( DAYS / 7 ))
[ "$WEEKS" -lt 8 ] && echo "WARN: $WEEKS weeks left (< 8, PLAYBOOK §2): target = silver unless WEEK0 item 1 says why not"
DUE5F=$(date -u -d "$TODAY +14 days" +%F)
command -v kaggle >/dev/null || { echo "kaggle CLI not on PATH (README Quickstart: python3 -m pip install kaggle; check: kaggle --version)"; exit 1; }
out=$(timeout 60 kaggle competitions submissions "$KREF" -v --page-size 1 2>&1) || true
echo "$out" | grep -qE '^ref,|No submissions found' || { echo "set KREF (Kaggle ref) or accept the rules on kaggle.com — got: $(echo "$out" | head -c 200)"; exit 1; }
mkdir -p "$DEST/intel" "$DEST/code" "$DEST/plans" "$DEST/retrospective" "$DEST/eda" "$DEST/data"
echo "$TODAY" > "$DEST/.entry"; echo "$DEADLINE" > "$DEST/.deadline"; echo "$KREF" > "$DEST/.kref"
: > "$DEST/.lower"   # metric direction: empty = higher is better; "1" = lower is better (echo 1 > .lower)
: > "$DEST/.goldcut" # gold cutoff score from the LB, day 0 (WEEK0 item 7): drives the plateau alert (law 9)
: > "$DEST/.lbnoise" # LB noise (PLAYBOOK Terms, WEEK0 item 10): drives the ruler alert (law 4)

# Render kit/templates/* (the one source): sed-substitute $PLACEHOLDERS, drop the leading <!-- --> line.
REL=${DEST#"$HARNESS_ROOT"/}   # repo-relative (competitions/<slug>) when under the repo, so the files stay valid in a clone
esc() { printf '%s' "$1" | sed 's/[\\|&]/\\&/g'; }
for f in STATE NOW WEEK0; do
  sed -e '1{/^<!--/d}' -e "s|\$SLUG|$(esc "$SLUG")|g; s|\$NAME|$(esc "$NAME")|g; s|\$KREF|$(esc "$KREF")|g; s|\$DEADLINE|$DEADLINE|g" \
      -e "s|\$WEEKS|$WEEKS|g; s|\$TODAY|$TODAY|g; s|\$DAYS|$DAYS|g; s|\$DUE5F|$DUE5F|g; s|\$DEST|$(esc "$REL")|g" \
      "$(dirname "$0")/templates/$f.md" > "$DEST/$f.md"
done

echo "id,date,change,kind,folds,parent,mechanism,oof_mean,oof_hard,public,gpu_h,kept,note" > "$DEST/experiments.csv"
printf "# %s — log (append-only)\n" "$NAME" > "$DEST/log.md"
touch "$DEST/kernels.txt" "$DEST/events.log"
printf '| id | date | decision | number (folds, SD) | example ids | verdict |\n|---|---|---|---|---|---|\n' > "$DEST/FINDINGS.md"
COMP_ROOT="$(dirname "$DEST")" bash "$(dirname "$0")/status.sh" "$SLUG" > "$DEST/STATUS.md"
echo "created $DEST — next: PLAYBOOK.md §1 + §3 day 0, fill WEEK0.md + NOW.md"
COMP_ROOT="$(dirname "$DEST")" nohup bash "$(dirname "$0")/watcher.sh" "$SLUG" >/dev/null 2>&1 &
echo "watcher PID $!"
