#!/usr/bin/env bash
# See the gates and the watcher work in seconds, with no Kaggle login: a fake Kaggle CLI (tests/bin)
# and a throwaway competition in a temp dir. Nothing touches Kaggle or this repo.
set -u
R="$(cd "$(dirname "$0")/.." && pwd)"; T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
export PATH="$R/tests/bin:$PATH" KAGGLE_USER=me COMP_ROOT="$T/comps" COMP_SLUG=demo CLAUDE_PROJECTS="$T/none" PYTHONDONTWRITEBYTECODE=1
mkdir -p "$T/none" "$T/k"; C="$T/comps/demo"
say() { printf '\n\033[1m▸ %s\033[0m\n' "$*"; }
expect() { out=$(cat); echo "$out"; grep -q "$1" <<<"$out" || { echo "DEMO FAILED: expected '$1'" >&2; exit 1; }; }   # a pipe runs it in a subshell: callers add `|| exit 1`

say "Scaffold a competition (kit/setup-competition.sh)"
out=$(bash "$R/kit/setup-competition.sh" demo "Demo" 2099-01-01); echo "$out" | head -1
kill "$(echo "$out" | sed -n 's/watcher PID //p')" 2>/dev/null   # we run single watcher passes below
flock -w 20 "$C/.lock" true                                      # its children may hold the lock a moment longer

say "GPU push whose 'Verdict: GO' is not bound to the plan text (kit/push_and_watch.sh)"
printf '{"id": "me/k1", "code_file": "k.py", "enable_gpu": "true"}' > "$T/k/kernel-metadata.json"; echo 'print(1)' > "$T/k/k.py"
head -c 2000 /dev/urandom > "$C/plans/k1-batch.bin"; printf 'kind: base\nidea: own-trained base on our folds\nVerdict: GO\n' > "$C/plans/k1.md"
bash "$R/kit/push_and_watch.sh" "$T/k" --accelerator NvidiaTeslaT4 | tail -1 | expect REFUSING || exit 1

say "The reviewer signs the plan as it stands (hash of its text); push again"
echo "Verdict: GO sha256=$(grep -v '^Verdict:' "$C/plans/k1.md" | sha256sum | cut -c1-16)" >> "$C/plans/k1.md"
bash "$R/kit/push_and_watch.sh" "$T/k" --accelerator NvidiaTeslaT4 | tail -1 | expect registered || exit 1

say "Finished kernels nobody read yet (kit/harvest_check.sh)"
bash "$R/kit/harvest_check.sh" "$C" '^k1$' | tail -2 | expect '1 UNHARVESTED' || exit 1   # the filter is a grep pattern: anchored, k10 does not match

say "A submission file with a missing value (kit/submit_gate.py)"
printf 'id,target\n1,0.5\n2,0.1\n' > "$C/data/sample_submission.csv"; printf 'id,target\n1,0.5\n2,nan\n' > "$T/sub.csv"
python3 "$R/kit/submit_gate.py" --file "$T/sub.csv" --competition demo --desc demo --probe demo --dry-run 2>&1 | grep ABORT | expect ABORT || exit 1

say "One watcher pass with nine 5-fold subs whose public score falls as CV rises"
echo 0.002 > "$C/.lbnoise"
P=(0.95 0.94 0.96 0.93 0.94 0.92 0.93 0.91 0.92)   # public drifts down as CV climbs (noisy, not a perfect -1)
for i in 1 2 3 4 5 6 7 8 9; do k=lever; p=e$((i-1)); [ $i = 1 ] && k=floor p=; echo "e$i,$(date -u +%F),change $i,$k,5,$p,m1,0.8$i,0.7,${P[i-1]},1,Y," >> "$C/experiments.csv"; done
bash "$R/kit/watcher.sh" demo --once >/dev/null 2>&1
grep -q '\[ruler\]' "$C/digest.md" || exit 1
echo "tier 1 (events.log; the Stop hook sends the agent back to ack them):"
grep ALERT "$C/events.log" | sed 's/^[^ ]* /  /'
echo "tier 2 (digest.md):"
sed 's/^[^ ]* /  /' "$C/digest.md"

say "Act on the tier-1 alerts, then ack them (kit/ack.sh)"
echo '{}' | python3 "$R/kit/hooks/check_stop.py" 2>&1 | head -3
bash "$R/kit/ack.sh" 'k-*' "outputs read, logged as e9" && echo '{}' | python3 "$R/kit/hooks/check_stop.py" && echo "Stop hook: turn may end"
