#!/bin/bash
# Push a Kaggle kernel: lint, red-team gate, push, register in <comp>/kernels.txt (watcher.sh alerts on complete/error).
#   COMP_SLUG=<slug> push_and_watch.sh <kernel-dir> [--accelerator NvidiaTeslaT4] [-t|--timeout <s>]
# Exit: 1 push failed (no "successfully pushed", or "could not be added": a source or tag dropped).
#       2 usage/metadata/is_private false/GPU without --accelerator/CLI not 2.x.
#       4 depslint (NOLINT=1 bypasses).
#       5 astgate (NOLINT=1 bypasses).
#       6 GPU/TPU push without a signed plan: <comp>/plans/<kernel slug>.md, less than 24 h old, with a `kind:` line and a last Verdict: line
#         "Verdict: GO sha256=<first 16 hex chars of sha256 of the plan without its Verdict lines>" (kind lever also needs `lever: <D2 id>` and an `elite-spec:` file under <comp>; PLAYBOOK §7);
#         or without a saved sample batch from the data loader, <comp>/plans/<slug>-batch.* over 1 KB.
# On success: <comp>/kernels.txt += ref, <comp>/events.log += "PUSH <ref> vN" (submit_gate reads it).
HARNESS_ROOT="${HARNESS_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)}"
set -u
kaggle --version | grep -q ' 2\.' || { echo "Kaggle CLI 2.x required (TOOLING T8)"; exit 2; }
DIR="${1:?usage: COMP_SLUG=<slug> push_and_watch.sh <kernel-dir> [--accelerator NvidiaTeslaT4] [-t|--timeout <s>]}"; shift
M="$DIR/kernel-metadata.json"; [ -f "$M" ] || { echo "no $M"; exit 2; }
COMP="${COMP_ROOT:-$HARNESS_ROOT/competitions}/${COMP_SLUG:?set COMP_SLUG=<slug>}"; [ -d "$COMP" ] || { echo "no $COMP"; exit 2; }
META=$(python3 -c "import json,sys; m=json.load(open(sys.argv[1])); print(m['id'], m.get('code_file') or '-', *(str(m.get(k)).lower() == 'true' for k in ('enable_gpu', 'enable_tpu')), str(m.get('is_private', True)).lower() == 'false', m.get('machine_shape') or '-', bool(m.get('competition_sources')) and str(m.get('enable_internet', True)).lower() != 'false')" "$M") \
  || { echo "REFUSING: $M is not valid kernel metadata (JSON with an id)"; exit 2; }
read -r ID CODE GPU TPU PUB SHAPE NET <<< "$META"
[ "$PUB" = True ] && { echo "REFUSING: \"is_private\": false in $M (RULES R35: never publish competition material)"; exit 2; }
case " $* " in *" -p"*|*" --path"*) echo "REFUSING: kernel dir is the first argument only"; exit 2;; esac   # a second -p/--path/--path= would push another kernel
# allow-list: the CLI takes option prefixes (--acc = --accelerator, --pa = --path), so only these options and their values pass
prev=; for v in "$@"; do
  case "$prev" in --accelerator|-t|--timeout) prev=; continue;; esac; prev=$v
  case "$v" in --accelerator|--accelerator=*|-t|--timeout|--timeout=*) ;; *) echo "REFUSING: $v (only --accelerator and -t/--timeout pass; the CLI takes prefixes such as --acc, --pa)"; exit 2;; esac
done
SLUG=${ID##*/}; ACC=0; case " $* " in *--accelerator*) ACC=1;; esac
# validate the value of every --accelerator / --accelerator= arg and of a metadata machine_shape; other args pass
acc_ok() { case "$1" in NvidiaTeslaT4|Tpu*) ;; *) echo "REFUSING: $2 $1 (TOOLING T8: NvidiaTeslaT4 or a current Tpu… id)"; exit 2;; esac; }
prev=; for v in "$@"; do   # TOOLING T8: Kaggle accepts a bogus --accelerator silently
  case "$prev|$v" in "--accelerator|"*) a=$v;; *"|--accelerator="*) a=${v#*=};; *) a=NvidiaTeslaT4;; esac; prev=$v
  acc_ok "$a" --accelerator
done
[ "$SHAPE" != - ] && { acc_ok "$SHAPE" "machine_shape in $M:"; ACC=1; }   # machine_shape overrides enable_gpu: false (TOOLING T9)
[ "$NET" = True ] && echo "WARN: competition_sources set and enable_internet not false (TOOLING T18)"

# Default P100 is sm_60: torch dies on the first tensor ("no kernel image is available"), so P100 is not on the allow-list.
[ "$GPU" = True ] && [ $ACC = 0 ] && { echo "REFUSING: enable_gpu without --accelerator (add --accelerator NvidiaTeslaT4)"; exit 2; }
[ "$CODE" != - ] || { echo "no code_file in $M"; exit 2; }

lint() { local rc=$1; shift; "$@" && return; echo "REFUSING: ${2##*/} failed above. Fix it, or bypass with NOLINT=1."; [ "${NOLINT:-0}" = 1 ] || exit "$rc"; }
G=$(dirname "$0")
case "$CODE" in *.py) lint 5 python3 "$G/astgate.py" "$DIR/$CODE";; esac   # compile(), not ast.parse()
lint 4 python3 "$G/depslint.py" "$DIR"

# Red-team gate (RULES R15, skill red-team-run)
if [ "$GPU" = True ] || [ "$TPU" = True ] || [ $ACC = 1 ]; then
  P="$COMP/plans/$SLUG"
  # The GO carries the first 16 hex chars of sha256 of the plan without its Verdict lines: any edit after the review voids it.
  H=$(grep -v '^Verdict:' "$P.md" 2>/dev/null | sha256sum | cut -c1-16)
  [ -n "$(find "$P.md" -mmin -1440 2>/dev/null)" ] \
    || { echo "REFUSING: GPU/TPU push: $P.md missing or plan older than 24 h (skill red-team-run)"; exit 6; }
  [ "$(grep '^Verdict:' "$P.md" | tail -1 | tr -s '[:space:]' ' ' | sed 's/ $//')" = "Verdict: GO sha256=$H" ] \
    || { echo "REFUSING: GPU/TPU push: last Verdict in $P.md is not GO for this plan's hash (plan edited after review?); expected 'Verdict: GO sha256=$H'"; exit 6; }
  [ -n "$(find "$P"-batch.* -maxdepth 0 -size +1k 2>/dev/null)" ] \
    || { echo "REFUSING: GPU/TPU push: no $P-batch.* > 1 KB (a saved sample batch from the data loader)"; exit 6; }
  K=$(sed -n 's/^kind: *\([a-z0-9]*\).*/\1/p' "$P.md" | head -1); [ -n "$K" ] || { echo "REFUSING: $P.md has no 'kind: <kind>' line (PLAYBOOK §7)"; exit 6; }
  if [ "$K" = lever ]; then
    E=$(sed -n 's/^elite-spec: *\([^ ]*\).*/\1/p' "$P.md" | head -1 | tr -d '`')
    { grep -qE '^lever: *[A-Za-z0-9]' "$P.md" && [ -n "$E" ] && case "$E" in /*|*..*) false;; esac && [ -f "$COMP/$E" ] && [ -s "$COMP/$E" ]; } \
      || { echo "REFUSING: a lever run's plan needs a 'lever: <id from the what-wins list, D2>' line and an 'elite-spec: <file under $COMP>' line naming an existing file that describes the strongest version (PLAYBOOK §7)"; exit 6; }
  fi
fi

echo "[push] $ID"
OUT=$(timeout 300 kaggle kernels push -p "$DIR" "$@" 2>&1); RC=$?; echo "$OUT"
# The CLI exits 0 on "Kernel push error" (e.g. a quota rejection) and on empty output: require the success text.
{ [ $RC -eq 0 ] && echo "$OUT" | grep -q "successfully pushed"; } || { echo "[push] FAILED, not registered"; exit 1; }
# Invalid dataset/competition/kernel sources are dropped with "could not be added" and the push still succeeds (TOOLING T10).
echo "$OUT" | grep -q "could not be added" && { echo "[push] FAILED: a source or tag was dropped (see above); kernel pushed but not registered"; exit 1; }
REF=$(echo "$OUT" | grep -oE 'kaggle\.com/code/[^/ ]+/[^/ ]+' | tail -1 | cut -d/ -f3-); REF=${REF:-$ID}
[ "$REF" = "$ID" ] || echo "WARN: Kaggle pushed to $REF, not metadata id $ID: registering $REF"
V=$(echo "$OUT" | sed -n 's/.*Kernel version \([0-9]*\).*/\1/p' | tail -1)
[ -n "$V" ] || echo "WARN: no version in the push output: logged as v?, so submit_gate refuses this push until a later one parses"
grep -qx "$REF" "$COMP/kernels.txt" 2>/dev/null || echo "$REF" >> "$COMP/kernels.txt"
# Forget the last run's state, so the watcher alerts even if this run finishes within one poll
[ -f "$COMP/.kstate" ] && { grep -v "^$REF " "$COMP/.kstate" > "$COMP/.kstate.tmp"; mv "$COMP/.kstate.tmp" "$COMP/.kstate"; }
rm -f "$COMP/.alerts/k-${REF//\//_}-"*
echo "$(date -u +%FT%TZ) PUSH $REF v${V:-?}" >> "$COMP/events.log"
echo "[push] $REF v${V:-?} registered in $COMP/kernels.txt + events.log; watcher.sh alerts in events.log on complete/error"
