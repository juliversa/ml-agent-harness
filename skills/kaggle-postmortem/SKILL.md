---
name: kaggle-postmortem
description: After a competition closes, pull every private score, write the post-mortem, correct refuted beliefs and merge the lessons. Use when a competition closes or /kaggle-postmortem.
---
# kaggle-postmortem
Audit the picks and the process against the private board, and carry what was learned into `LESSONS.md`.

Output: `<comp>/retrospective/postmortem.md` (one file, ≤ 2 pages) with these six parts:
1. **Provenance:** board snapshot, write-ups read, dates. A post-mortem built on the public board repeats the error.
2. **Result:** private score, gap to the gold cut, the pick error (best private vs picked).
3. **What won:** from published write-ups, quoted verbatim; tag second-hand sources.
4. **Gap to the gold cut, ranked by cost** (not by count): each `COST: <what> — fix: process / tooling / strategy`. Cheap crashes are not root causes.
5. **Depth-loop audit** (PLAYBOOK §1): was the winners' lever in our D2 list (what wins), and when? Did spend follow D3 (bottleneck)? Did any lane close without its elite run? D7 flags a closed or dead FINDINGS row that has no `kind=lever` id with `oof_mean`.
6. **Refuted ledger:** every pre-deadline belief the board or write-ups killed, one row each.

## Steps
1. **Pull, within 1 hour of the close:** the private score of every submission we made (one CSV), and the private board + cuts (snapshot). The best private sub is not always a picked one; this table audits the picks.
2. **Write**, within 1 week, `postmortem.md` with parts 1–6 above.
3. **Red-team** the headline (skill `red-team-run`) before it is final.
4. **Merge upward:** add one row to the competitions table in `LESSONS.md` (comp · what the top team compared did · the winners' edge · lesson) and update the competition count and team-size range there and in README (the Kaggle results line under the title, and the LESSONS row of the repo map: competition and lesson counts). Add new lessons and load-bearing refuted beliefs as new L-IDs. A lesson changes `PLAYBOOK.md` only by replacing a law, at most one per competition. Keep competition-specific detail in the post-mortem.
5. **Archive:** `git mv` the folder to `competitions/_finished/<slug>/`, so the hooks, `ack.sh` and the session start stop treating it as live.

## Traps
- Count "we measured it dead" only if the leaders' elite version ran.

## Done when
The red-teamed `postmortem.md` is final, the `LESSONS.md` row is merged, and the folder sits in `competitions/_finished/<slug>/`.
