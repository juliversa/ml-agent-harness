#!/usr/bin/env python3
"""Pick the items the lead hand-reads (RULES R7, skill autopsy): 20 worst, 10 clean, 10 random controls, seeded.

  python3 kit/pick_items.py --oof <comp>/oof/<id>.npy --score-dir <comp> [--seed 0]      # writes <comp>/eda/pick-<id>.csv
  python3 kit/pick_items.py --oof <npy> --target <npy> [--ids <npy>] [--seed 0]           # prints the csv

Per-item error: |p − y| (binary, regression) or 1 − p_true (multiclass: oof of shape (n, k), y = class index).
worst = largest error, clean = smallest error, random = drawn from the rest. --target defaults to
<score-dir>/data/oof_target.npy; --ids (row ids) defaults to the row index."""
import argparse, sys
from pathlib import Path

import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("--oof", required=True), ap.add_argument("--target"), ap.add_argument("--score-dir")
ap.add_argument("--ids"), ap.add_argument("--seed", type=int, default=0)
a = ap.parse_args()
if not (a.target or a.score_dir):
    sys.exit("give --target or --score-dir")
p = np.load(a.oof)
y = np.load(a.target or Path(a.score_dir) / "data" / "oof_target.npy")
ids = np.load(a.ids, allow_pickle=True) if a.ids else np.arange(len(y))
if not len(p) == len(y) == len(ids):
    sys.exit(f"length mismatch: oof {len(p)}, target {len(y)}, ids {len(ids)}")
err = 1 - p[np.arange(len(y)), y.astype(int)] if p.ndim == 2 else np.abs(p.astype(float) - y)
scored = np.flatnonzero(np.isfinite(err))         # a 1-fold screen leaves NaN outside its fold: pick scored rows only
if not len(scored):
    sys.exit("no scored rows (all OOF NaN)")
order = scored[np.argsort(-err[scored], kind="stable")]
worst, clean = order[:20], order[::-1][:10]
rest = np.setdiff1d(scored, np.concatenate([worst, clean]))
rand = np.random.default_rng(a.seed).choice(rest, min(10, len(rest)), replace=False)
rows = ["id,group,error"] + [f"{ids[i]},{g},{err[i]:.6g}" for g, idx in
                             (("worst", worst), ("clean", clean), ("random", rand)) for i in idx]
print("\n".join(rows))
if a.score_dir:
    out = Path(a.score_dir) / "eda" / f"pick-{Path(a.oof).stem}.csv"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(rows) + "\n")
    print(f"wrote {out}", file=sys.stderr)
