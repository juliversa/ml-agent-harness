#!/usr/bin/env python3
"""PreToolUse hook (Agent): every helper brief has the four coding-discipline rules in its first 3000 chars (RULES R14) and has an
`Output:` line (what comes back, how long: R11, R33). kit/fanout.py runs the same check on its brief.md.
Exit 2 blocks the call and shows the reason to the agent."""
import json, re, sys


def problem(prompt):
    """The reason a brief is refused, or None if it passes."""
    if not all(r in prompt[:3000] for r in ("No silent assumptions", "Simplicity first", "Surgical changes", "Explicit verification")):
        return ("BLOCKED: the brief must start with the four rules of skill coding-discipline, verbatim (RULES R14): "
                "copy them from skills/coding-discipline/SKILL.md, then goal, what is ruled out, raw paths, narrow scope.")
    if not re.search(r"(?im)^\W*output\b.*(\d|page|line|word)", prompt):
        return ("BLOCKED: the brief needs an `Output:` line saying what comes back and how long (a file path, ≤ 1 page), "
                "so helper results stay out of the lead's context (RULES R11, R33).")


if __name__ == "__main__":
    msg = problem((json.load(sys.stdin).get("tool_input") or {}).get("prompt", ""))
    if msg:
        print(msg, file=sys.stderr)
        sys.exit(2)
