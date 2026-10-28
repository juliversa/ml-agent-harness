#!/usr/bin/env python3
"""PostToolUse hook (Write|Edit): run astgate.py on every kernel .py file the agent writes (under code/ or next to
kernel-metadata.json), so an undefined name or a
forward reference surfaces now, not 40 minutes into a GPU run. Exit 2 shows the error to the agent."""
import json, subprocess, sys
from pathlib import Path


def block(msg):            # exit 2 = block; stderr goes to the agent
    print(msg, file=sys.stderr)
    sys.exit(2)


path = (json.load(sys.stdin).get("tool_input") or {}).get("file_path", "")
f = Path(path)
kernel_code = any(p.name == "code" and (p.parent / "STATE.md").exists() for p in f.resolve().parents) or (f.parent / "kernel-metadata.json").exists()
if path.endswith(".py") and kernel_code and f.is_file():
    r = subprocess.run([sys.executable, str(Path(__file__).resolve().parent.parent / "astgate.py"), path],
                       capture_output=True, text=True)
    if r.returncode:
        block(f"astgate: {(r.stdout + r.stderr).strip()[-600:]}")
