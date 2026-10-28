---
name: lean-replies
description: Terse reply style (lite/full/ultra) for the lead and every helper, required by RULES R26 at level full; load at session start. Switch level on 'be brief' / 'fewer tokens' or /lean-replies; 'normal mode' turns it off.
---
# lean-replies
Say each thing once, briefly: output tokens cost about 5× input (RULES R20, the daily token budget), and every reply is re-read as context on every later turn.

## Steps
1. Keep all technical substance; drop filler, pleasantries and hedging. Short phrases are fine where a full sentence adds nothing.
2. Follow the pattern `[thing] [action] [reason]. [next step].` Keep code, commands, errors and numbers exact and unabbreviated.
3. Pick the level:
   - **lite**: full sentences, no filler.
   - **full** (default): compact phrases, plain short words.
   - **ultra**: standard abbreviations (DB, fn, cfg) and arrows for cause and effect.
4. Write reports in short sentences, one idea each, terms defined once, numbers kept.
5. Use normal prose for security warnings, irreversible-action confirmations, ordered multi-step instructions, clarifications the owner asks for, and documents. Code, commits and PRs: normal.

## Done when
The reply carries every fact, number and command with no filler, at the chosen level; "normal mode" switches the style off.

Adapted from a community terse-reply skill; the token rationale and budget link are this repo's.
