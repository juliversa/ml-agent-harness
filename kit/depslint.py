#!/usr/bin/env python3
"""Pre-push dependency lint: source-vs-metadata cross-check (each mismatch costs a failed push).
  REFUSE: a dataset slug named in source (assert strings AND /kaggle/input/ paths) missing from
  kernel-metadata.json dataset_sources, kernel_sources or model_sources (exact mount names). One signal alone = WARN (a wildcard fallback may cover it).
"""
import json, re, sys
from pathlib import Path

if len(sys.argv) < 2: sys.exit("usage: depslint.py <kernel-dir>")
d = Path(sys.argv[1])
if not (d / "kernel-metadata.json").is_file(): sys.exit(f"no kernel-metadata.json in {d}")
meta = json.load(open(d / "kernel-metadata.json"))
src = open(d / meta["code_file"]).read()
# Mount name under /kaggle/input/: dataset and kernel = last segment, model = second ("owner/model/framework/variation/v").
sources = {s.split("/")[-1] for s in meta.get("dataset_sources", []) + meta.get("kernel_sources", [])}
sources |= {s.split("/")[1] for s in meta.get("model_sources", []) if s.count("/") >= 1}
fail = False

# Dataset = FIRST segment after /kaggle/input/, or the second when the first is a declared OWNER.
# An owner is never a dataset to attach (a glob path `/kaggle/input/<owner>/*` captures the owner).
_owners = {t.split("/")[0] for t in meta.get("dataset_sources", []) if "/" in t}
named = set()
for _a, _b in re.findall(r"/kaggle/input/(?:datasets/)?([\w][\w-]*)(?:/([\w][\w-]*))?", src):
    named.add(_b if (_a in _owners and _b) else _a)
named |= set(re.findall(r'"([\w-]+)"?\s*dataset not attached', src))
named -= {"competitions", "datasets", meta["id"].split("/")[-1]} | _owners
comp = {c.split("/")[-1] for c in meta.get("competition_sources", [])}
for n in sorted(named):
    if n in comp or n in sources:
        continue
    literal = f"/kaggle/input/{n}" in src or "/kaggle/input/datasets/" in src and f"/{n}/" in src
    asserted = bool(re.search(rf"assert[^\n]*{re.escape(n)}", src))
    if literal and asserted:
        print(f"REFUSING (depslint): source references dataset '{n}' but the attached mounts are {sorted(sources)}")
        fail = True
    else:
        print(f"WARN (depslint): source mentions dataset '{n}' not in dataset_sources -- "
              f"verify a wildcard fallback covers it")
sys.exit(2 if fail else 0)
