---
name: coding-discipline
description: Four coding rules every agent follows; paste them verbatim at the top of every sub-agent brief. Use when writing code or briefing a helper.
---
# coding-discipline
The four rules the lead and every sub-agent follow when writing or changing code.

## Steps
1. **No silent assumptions (think before coding).** If a task is ambiguous, stop and ask; never guess and build the wrong thing.
   Sub-agents ask the lead. The lead asks the owner only for what `RULES.md` R1 lists; otherwise it states the assumption in one line before acting.
2. **Simplicity first.** Minimum viable implementation. If 50 lines solve it, do not write 500. No unrequested features, abstractions, or error handling for impossible cases.
3. **Surgical changes.** Touch exactly what was requested. No drive-by refactors or orthogonal edits; match existing style; remove only orphans you created.
4. **Explicit verification.** Never say "it should work". Run the relevant test / repro / metric, check the output, and show the command and result before handing back.

## Done when
Every agent brief starts with these four rules, copied verbatim, and has an `Output:` line (what comes back, how long); `kit/hooks/check_brief.py` blocks a brief missing the four rule names or that line.

Adapted from widely shared community coding guidelines for LLM agents.
