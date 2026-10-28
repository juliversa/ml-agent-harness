#!/usr/bin/env python3
"""PreToolUse hook (Read|Bash): keep big files out of the lead's context (RULES R33; rsna: the 20 largest results were
53-55k-char whole-file reads). Blocks a Read of a text file over 40 KB unless 0 < `limit` <= 1000 lines; in Bash, `cat` / `less` / `more` / `nl` / `tac` / `cut` of one,
`head`/`tail -c` > 8000, `-n` (or `-NUM`) > 1000, `+N` or `-N` (also as one word: `-n+1`, `-c9000`; also as the last stage of a pipe reading one), `sed` without `-n 'A,Bp'` (<= 1000 lines; `-i` is fine), `awk` without an NR bound. Exit 2 blocks the call and shows the reason to the agent."""
import json, os, re, shlex, sys

MAX = 40_000
IMG = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf")


def big(p):
    try:
        return os.path.getsize(os.path.expanduser(p)) > MAX
    except OSError:
        return False


def block(msg):            # exit 2 = block; stderr goes to the agent
    print(msg, file=sys.stderr)
    sys.exit(2)


hook = json.load(sys.stdin)
ti = hook.get("tool_input") or {}
if hook.get("tool_name") == "Read":
    p = ti.get("file_path", "")
    try:
        limit = int(ti.get("limit") or 0)
    except (TypeError, ValueError):
        limit = 0                     # unreadable limit = no limit (a crash would not block)
    if not p.lower().endswith(IMG) and not 0 < limit <= 1000 and big(p):
        block(f"BLOCKED: {p} is over 40 KB. Read a part (limit <= 1000 lines, any offset), or grep for what you need (RULES R33)." + (f" Notebook: jq -r '.cells[].source[]' {p}" if p.lower().endswith(".ipynb") else ""))
    sys.exit(0)
READERS = ("cat", "tail", "head", "sed", "awk", "less", "more", "nl", "tac", "cut")   # commands that can print a whole file
MSG = "BLOCKED: that prints a file over 40 KB into context. Use grep, head/tail -n <= 1000, sed -n 'A,Bp', or awk with an NR range (RULES R33)."
for cmd in re.split(r"[;\n]+|&&|\|\|", ti.get("command", "")):
    *up, seg = cmd.split("|")         # only the last stage of a pipeline prints; `cat big | grep x` is fine (a guard rail: `cat big | cat`, xxd pass)
    try:
        w = shlex.split(seg)
    except ValueError:                # a quote cut by the split above (`sed -n '1,9p;5000,9000p' big`): judge the whole command
        first = [a for a in seg.split() if a not in ("{", "(", "!")][:1]
        if first and first[0] in READERS and any(big(a.strip("\"'")) for a in ti.get("command", "").split()):
            block(MSG)                # only for a whole-read command: `grep 'x;y' big` prints matches, not the file
        continue
    while w and w[0] in ("{", "(", "!"):   # `{ cat big; }`, `( cat big )`, `! cat big`
        w = w[1:]
    if not w or w[0] not in READERS or any(a.startswith(">") for a in w):
        continue                      # a redirect writes a file, it prints nothing
    def opt(f):                       # value of -n / -c: `-n 5`, `-n5`, `-n+5`; head/tail -NUM means -n NUM
        for i, a in enumerate(w[1:], 1):
            if a == f:
                return w[i + 1] if i + 1 < len(w) else ""
            if a.startswith(f) and len(a) > 2:
                return a[2:]
        return next((a[1:] for a in w[1:] if f == "-n" and re.fullmatch(r"-\d+", a)), "")
    many = lambda v, top: (v[:1] == "+") or (v[:1] == "-" and w[0] == "head") or (v.lstrip("-").isdigit() and int(v.lstrip("-")) > top)   # tail +N: from N on; head -N: all but the last N; tail -N: the last N
    args = [a for a in w[1:] if not a.startswith("-")]
    script = args[0] if w[0] in ("sed", "awk") and args else ""        # their first word is the script (`awk 1 big`)
    files = [a for a in args[1 if script else 0:] if not a.lstrip("+").isdigit()]
    if w[0] in ("head", "tail") and not files:   # `cat big | head -n 5000` prints the big file too
        files = [a for u in up for a in u.split()]
    c, n = opt("-c"), opt("-n")
    rng = re.fullmatch(r"(\d+)(?:,(\d+))?p", script)
    wide = (w[0] in ("cat", "less", "more", "nl", "tac", "cut")
            or w[0] in ("head", "tail") and (many(c, 8000) or many(n, 1000))
            or w[0] == "sed" and not any(a.startswith("-i") for a in w) and not ("-n" in w and rng and int(rng[2] or rng[1]) - int(rng[1]) <= 1000)
            or w[0] == "awk" and not re.search(r"NR\s*(?:<|==)", script))
    if wide and any(big(f) for f in files):
        block(MSG)
