#!/usr/bin/env python3
"""PreToolUse hook (Bash): commands the agent may not run directly, whatever the permission list says.
Exit 2 blocks the call and shows the reason to the agent.
  - kaggle kernels push / competitions submit outside the kit gates (push_and_watch.sh, submit_gate.py)
  - recursive or forced deletes (rm -r/-f, find -delete / -exec rm) of a relative path, ~, or anything inside the repo
    (or containing it); any delete of a path under competitions/ or .git; git clean (not -n dry run) / reset --hard /
    rm -r / checkout -- / checkout -f / switch -f / restore (all but --staged alone) / stash (all forms but list, show) /
    push --force, also behind git global options (RULES R36: no deletes without the owner's yes)
    Allowed: those deletes on absolute paths outside the repo (/tmp, scratch dirs), plain rm outside competitions/.
  - deleting on Kaggle or GitHub: kaggle datasets/kernels/models delete, gh repo delete, gh api -X DELETE, git push --delete / :branch (R36)
  - making anything public: kaggle datasets create --public, gh repo create --public / edit --visibility public,
    gh api … private=false / visibility=public (R35, R1)
  - `cd X && …` (style, not safety: a predictable working directory, R37; use absolute paths, git -C)
Matches only where a command begins, so a grep pattern or a commit message passed via `cat` heredoc (`git commit -m "$(cat <<'EOF' … EOF)"`) is not blocked;
`-m` text containing `;`, `|`, `{`, `!`, a backtick, or a shell keyword (then/do/else/env/time…) before a command can be blocked.
It stops the direct shortcuts, not a determined adversary: the gates in kit/ are the real control."""
import json, os, re, shlex, sys
from pathlib import Path

OPTS = r"(?:\s+-[^\s;&|]+(?:\s+[^\s;&|-][^\s;&|]*)?)*"   # a wrapper's options, each with an optional value
# where a command begins
START_AT = [
    r"^\s*",                                               # start of the command line
    r"[;&|(\n{!`]\s*",                                     # after a separator, group, negation or backtick
    r"\$\(\s*",                                            # inside $( … )
    r"\bxargs(?:\s+-[^\s;&|]+(?:\s+\d+)?)*\s+",            # run by xargs (with its options)
    r"\b(?:then|do|else)\s+",                                # shell keywords
    r"\b(?:sudo|exec|time|nohup|command|nice|ionice|stdbuf|env)" + OPTS + r"\s+",   # wrappers, with options (sudo -u x, nice -n 5)
    r"\btimeout" + OPTS + r"\s+[^\s;&|]+\s+",                 # timeout [-s KILL] 5
    r"\b(?:(?:ba|z)?sh\s+(?:-\w+\s+)*-\w*c|eval)\s+[\"']?",   # a string run by sh -c / bash -lc / eval
]
START = "(?:" + "|".join(START_AT) + r")(?:\w+=\S*\s+)*"   # then any VAR=value prefixes
KAGGLE = r"(?:\S*/)?kaggle\s+"
GIT = r"(?:\S*/)?git\s+(?:(?:-[Cc]\s+\S+|--[\w-]+(?:=\S+)?)\s+)*"   # global options (-C dir, -c k=v, --no-pager, --git-dir=…)
ARG = r"(?:[^\s;&|]+[ \t]+)*"   # this command's own arguments: never past ; && || | or a newline
# git commands that lose work for good
DISCARD_PARTS = [
    r"clean\s+(?!(?:-\w+\s+)*(?:-[a-zA-Z]*n|--dry-run\b))(?:-\w*[fdxX]|--force\b)",   # git clean (not -n / --dry-run)
    r"reset\s+" + ARG + r"--hard\b",                                              # git reset --hard
    r"rm\s+(?!.*--cached)(-\w+\s+)*-r",                                           # git rm -r (not --cached)
    r"checkout\s+" + ARG + r"(?:--\s|\.(?:\s|$)|-f\b|--force\b)",                 # git checkout -- / . / -f
    r"switch\s+" + ARG + r"(?:-f\b|--force\b|--discard-changes)",                 # git switch -f
    r"restore\s(?!\s*--staged\b)",                                                # git restore (not --staged first)
    r"restore\s+" + ARG + r"(?:--worktree\b|-\w*W)",                              # git restore --worktree / -W
    r"stash\b(?!\s+(?:list|show))",                                               # git stash (not list, show)
    r"push\s+" + ARG + r"(?:-f\b|--force|\+\S)",                                  # git push --force / +ref
    r"branch\s+" + ARG + r"(?:-D\b|--delete\s+" + ARG + r"--force\b|--force\s+" + ARG + r"--delete\b)",   # git branch -D
]
DISCARD = "|".join(DISCARD_PARTS)
REPO = os.path.realpath(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
OWNER = re.compile(r"(?:^|/)(?:competitions|\.git)(?:/|$)")   # owner trees, as whole path segments (not /tmp/setup.log)

GATED_MSG = ("BLOCKED: `{}` goes through the gate: bash kit/push_and_watch.sh (push) "
             "or python3 kit/submit_gate.py (submit). See skills kaggle-run, kaggle-submit.")
REMOTE_DELETE_MSG = "BLOCKED: deletes on Kaggle or GitHub are the owner's call (RULES R36). Ask the owner."
PUBLIC_MSG = "BLOCKED: this makes something public (RULES R35, R1: anything public is the owner's call). Keep it private; the owner publishes."
DISCARD_MSG = "BLOCKED: this deletes or discards owner files (RULES R36: no deletes without the owner's yes). Ask, then the owner runs it."
CD_MSG = "BLOCKED: no `cd X && …` (RULES R37). Work from the repo root (bash kit/x.sh); elsewhere use git -C <dir> or a path."


def strip_heredoc_bodies(cmd):   # a `cat` heredoc body is text (commit message, plan file), not commands: keep only its first line
    return re.sub(r"\bcat\b(?![^\n]*\|\s*(?:\S*/)?(?:sudo\s+)?(?:ba|z)?sh\b)([^;&|\n]*<<-?\s*(['\"]?)(\w+)\2[^\n]*)\n.*?\n[ \t]*\3[ \t]*(?=\n|$|\))",
                  r"cat\1", cmd, flags=re.S)


def gated_kaggle_call(cmd, bare):   # kaggle kernels push/update or competitions submit, typed or from inline Python; the match or None
    # CLI 2.x aliases: k = kernels, c = competitions, update = push; the Python API and `python -m kaggle` reach the same calls.
    typed = re.search(START + KAGGLE + r"(?:k|kernels)\s+(?:push|update)\b|" + START + KAGGLE + r"(?:c|competitions)\s+submit\b", bare)
    if typed:
        return typed
    # inline Python (-c, stdin, heredoc, -m kaggle)
    python = re.search(r"\bpython3?\b[^;&|\n]*(?:[ \t]-c\s|[ \t]-\s|<<|[ \t]-m\s+kaggle\b)", cmd)
    if not python:
        return None
    code = re.sub(r"""\\+(?=["'])""", "", cmd[python.start():])   # \" inside a double-quoted -c is a plain quote to Python
    return re.search(r"competition_submit|kernels_push|-m\s+kaggle\s+(?:k|kernels|c|competitions)\s+(?:push|update|submit)"
                     r"|\bkaggle\s+(?:k|kernels)\s+(?:push|update)\b|\bkaggle\s+(?:c|competitions)\s+submit\b"   # os.system / shell=True strings
                     r"""|["'](?:k|kernels)["']\s*,\s*["'](?:push|update)["']|["'](?:c|competitions)["']\s*,\s*["']submit["']""",   # subprocess list args
                     code)


def kaggle_or_github_delete(text):   # datasets/kernels/models delete, models instances [versions] delete, gh repo delete, remote branch delete
    return re.search(START + KAGGLE + r"(?:d|datasets|k|kernels|m|models)\s+(?:instances\s+(?:versions\s+)?)?delete\b|"
                     + START + r"gh\s+repo\s+delete\b|"
                     + START + r"gh\s+api\s+" + ARG + r"(?:-X|--method)[= ]?DELETE\b|"                 # gh api -X DELETE …
                     + START + GIT + r"push\s+" + ARG + r"(?:--delete\b|-d\b|:[^\s;&|]+)", text)   # git push --delete / origin :branch


def makes_public(bare):   # kaggle datasets create --public / -u, gh repo create --public / edit --visibility public, gh api … private=false
    return re.search(START + KAGGLE + r"(?:d|datasets)\s+create\s+" + ARG + r"(?:-u|--public)(?:\s|$)|"
                     + START + r"gh\s+repo\s+(?:create|edit)\s+" + ARG + r"(?:--public|--visibility[= ]public)(?:\s|$)|"
                     + START + r"gh\s+api\s+" + ARG + r"[^\s;&|]*\b(?:private=false|visibility=public)\b", bare)


def discards_work(text):   # a git command that loses work for good, also behind git global options
    return re.search(START + GIT + "(?:" + DISCARD + ")", text)


def cd_and(text):   # style (not safety): R37
    return re.search(START + r"cd\s+[^;&|\n]*&&", text)


def words(args):   # shell words of one command's arguments; a # comment ends them
    try:
        return shlex.split(args, comments=True)
    except ValueError:
        return args.split()


def unsafe(path):  # a recursive/forced delete target that may hold owner files
    if not re.search(r"[*?\[]", path) and ".." not in path.split("/") and os.path.basename(path.rstrip("/")) == "__pycache__":
        return False                    # a __pycache__ dir is never an owner file (not __pycache__/.., not a glob)
    if OWNER.search(path) or not path.startswith(("/", "~/")):
        return True                     # owner trees; relative paths, ~, $VARS and globs resolve inside the repo or unknowably
    if re.search(r"[*?\[]", path):     # a glob may expand to the repo or a folder holding it: judge the dir before the first glob char
        glob_dir = os.path.realpath(os.path.expanduser(re.split(r"[*?\[]", path)[0].rsplit("/", 1)[0] or "/"))
        if glob_dir == REPO or REPO.startswith(glob_dir.rstrip("/") + "/") or glob_dir == os.path.realpath(os.path.expanduser("~")):
            return True                 # rm -rf /*, /workspace/*, /w*, ~/*
    real = os.path.realpath(os.path.expanduser(path))
    return real == REPO or real.startswith(REPO + "/") or REPO.startswith(real.rstrip("/") + "/")   # inside the repo, or the repo inside it


def bad_delete(text):
    for match in re.finditer(START + r"(?:\S*/)?rm(?=\s|$)([^;&|\n]*)", re.sub(r"-exec(?:dir)?\s", " ", text)):   # find -exec rm: below
        args, opts, targets = [arg for arg in words(match.group(1)) if not re.match(r"\d*[<>&]", arg)], "", []   # drop redirections
        for i, arg in enumerate(args):
            if arg == "--":
                targets += args[i + 1:]; break
            if arg.startswith("-") and len(arg) > 1:
                opts += " " + arg
            else:
                targets.append(arg)
        if re.search(r" (?:-[a-zA-Z]*[rRf]|--recursive|--force)", opts):
            if not targets or any(unsafe(t) for t in targets):   # no targets: they come from stdin (xargs)
                return True
        elif any(OWNER.search(t) for t in targets):              # plain rm: only owner trees are off limits
            return True
    for match in re.finditer(START + r"find(?=\s|$)([^;&|\n]*)", text):
        args = words(match.group(1))
        if not ("-delete" in args or re.search(r"(?:^|\s)-exec(?:dir)?\s+(?:\S*/)?rm\s", match.group(1))):
            continue
        names = [args[i + 1] for i, arg in enumerate(args[:-1]) if arg in ("-name", "-iname")]
        if names and all(n == "__pycache__" for n in names) and not {"-o", "-or"} & set(args):   # -o: deletes more than __pycache__
            continue
        roots = [arg for arg in args[:next((i for i, arg in enumerate(args) if arg[:1] in "-(!"), len(args))]] or ["."]
        if any(unsafe(r) for r in roots):
            return True
    return False


def check(cmd):   # the block message for one Bash command line, or None
    cmd = re.sub(r"\\\r?\n", " ", cmd)   # join \-continued lines
    text = strip_heredoc_bodies(cmd)
    bare = re.sub(r"[\"']", "", text)   # quoted words are the same words to the shell: `kaggle 'kernels' push`, `"kaggle" k push`
    plain = re.sub(r"""(?<![^\s;&|(`{!])[\\"']*r[\\"']*m[\\"']*(?=\s)""", "rm", text)   # "rm", \rm, r''m are rm; other quotes kept
    gated = gated_kaggle_call(cmd, bare)
    if gated:   # the gate scripts call the CLI themselves, so a command line that names it is never a gate call
        return GATED_MSG.format(gated.group(0).strip())
    if kaggle_or_github_delete(text):
        return REMOTE_DELETE_MSG
    if makes_public(bare):
        return PUBLIC_MSG
    if bad_delete(plain) or discards_work(text):
        return DISCARD_MSG
    if cd_and(text):
        return CD_MSG
    return None


def main():
    msg = check((json.load(sys.stdin).get("tool_input") or {}).get("command", ""))
    if msg:                # exit 2 = block; stderr goes to the agent
        print(msg, file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
