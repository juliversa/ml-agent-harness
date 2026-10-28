#!/usr/bin/env python3
"""Is arm B better than control A? The PLAYBOOK law 4 read, from two OOF prediction files on the same folds.

  python3 kit/compare.py <comp> <A.npy> <B.npy> [--hard hard_ids.npy] [--seed-noise σΔ] [--bootstrap N [--groups g.npy]]

<comp>/data/oof_target.npy (y), <comp>/data/folds.npy (fold of each row) and <comp>/score.py (`score(y, p)`, higher
is better unless <comp>/.lower = 1) are the competition's own; A and B are OOF predictions aligned to them.
Prints per-fold Δ, the corrected resampled t (Nadeau & Bengio 2003; k-fold form, Bouckaert & Frank 2004:
se = std(Δ)·√(1/k + 1/(k−1))), whether the gain is readable (t ≥ 2, no fold negative and pooled Δ ≥ 0, a screening
bar, not a significance test; with --seed-noise, also mean Δ ≥ 2 σΔ/√k, σΔ being one fold's seed noise; under
5 folds a screen: --seed-noise required, every fold Δ ≥ 2 σΔ, rank only), the worst fold, and Δ on the hard slice.
--bootstrap N: paired group bootstrap of the pooled Δ (N resamples of whole groups: --groups, else <comp>/data/groups.npy,
else rows), printed as a 95 % interval. With --seed-noise on >= 5 folds it replaces the fold bar: pooled Δ ≥ 2 SE, where
SE² = bootstrap SE² (test rows) + σΔ²·(1/k + 1/(k−1)) (training noise; the Nadeau–Bengio factor, i.e. assuming fold
training noise correlated about ρ ≈ .3 at k = 5), and no fold below −2 σΔ.
The bootstrap alone ignores training noise; kit/sim_bar.py (c) gives both reads' false-pass and power rates."""
import argparse, importlib.util, math, sys
from pathlib import Path

import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("comp"), ap.add_argument("a"), ap.add_argument("b")
ap.add_argument("--hard", help=".npy of row indices in the frozen hard slice")
ap.add_argument("--seed-noise", type=float, help="σΔ from >= 5 fresh seed pairs (PLAYBOOK Terms)")
ap.add_argument("--bootstrap", type=int, metavar="N", help="paired group-bootstrap resamples (e.g. 2000)")
ap.add_argument("--groups", help=".npy of each row's group (patient, site, well); default <comp>/data/groups.npy")
a = ap.parse_args()
if a.seed_noise is not None and not a.seed_noise > 0:
    sys.exit("--seed-noise must be > 0 (measure it: PLAYBOOK Terms)")
if a.bootstrap is not None and a.bootstrap < 100:
    sys.exit("--bootstrap needs >= 100 resamples")
C = Path(a.comp)
spec = importlib.util.spec_from_file_location("score", C / "score.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
y, folds = np.load(C / "data" / "oof_target.npy"), np.load(C / "data" / "folds.npy")
pa, pb = np.load(a.a), np.load(a.b)
if not (len(y) == len(folds) == len(pa) == len(pb)):
    sys.exit(f"length mismatch: y {len(y)}, folds {len(folds)}, A {len(pa)}, B {len(pb)}")
# a 1-fold screen leaves NaN outside its fold: compare where both ran; NaN inside a fold it ran is a broken model
for name, arr in (("A", pa), ("B", pb)):
    fin = ~np.isnan(arr.reshape(len(arr), -1)).any(1)
    if part := [int(f) for f in np.unique(folds) if fin[folds == f].any() and not fin[folds == f].all()]:
        sys.exit(f"{name} has NaN on part of fold(s) {part}: a run must predict every row of each fold it ran")
keep = ~(np.isnan(pa).reshape(len(pa), -1).any(1) | np.isnan(pb).reshape(len(pb), -1).any(1))
if not keep.any():
    sys.exit("A and B share no scored rows (screens on different folds?)")
gpath = Path(a.groups) if a.groups else C / "data" / "groups.npy"
if a.groups and not gpath.exists():
    sys.exit(f"--groups {a.groups}: no such file")
if a.groups and not a.bootstrap:
    sys.exit("--groups is read only with --bootstrap N")
groups = np.load(gpath, allow_pickle=True) if a.bootstrap and gpath.exists() else np.arange(len(y))   # own file: ids as objects ok
if len(groups) != len(y):
    sys.exit(f"length mismatch: groups {len(groups)}, y {len(y)}")
y, folds, pa, pb, groups, rows = y[keep], folds[keep], pa[keep], pb[keep], groups[keep], np.where(keep)[0]
if not keep.all():
    print(f"compared {keep.sum()} of {len(keep)} rows (NaN in A or B)")
sign = -1 if (C / ".lower").exists() and (C / ".lower").read_text().strip() == "1" else 1   # Δ > 0 = B better

ks = sorted(set(folds.tolist()))
d = np.array([sign * (mod.score(y[folds == k], pb[folds == k]) - mod.score(y[folds == k], pa[folds == k])) for k in ks])
k = len(d)
se = d.std(ddof=1) * math.sqrt(1 / k + 1 / (k - 1)) if k > 1 else float("nan")
t = d.mean() / se if se > 0 else (0.0 if d.mean() == 0 else math.copysign(math.inf, d.mean()))
pooled = sign * (mod.score(y, pb) - mod.score(y, pa))
print("per-fold Δ: " + "  ".join(f"{x:+.5f}" for x in d))
print(f"mean Δ {d.mean():+.5f}   pooled Δ {pooled:+.5f}   "
      + (f"corrected t = {t:.2f} on {k - 1} df   " if k > 1 else "1 fold: no t   ") + f"worst fold {d.min():+.5f}")
screen = k < 5                                    # a screen (< 5 folds) reads on σΔ alone: every fold Δ >= 2 σΔ


def group_bootstrap(n_resamples, seed=0):
    """Pooled Δ on n_resamples resamples of whole groups, both arms on the same rows (paired)."""
    _, inv = np.unique(groups, return_inverse=True)
    n_groups, rng, out = inv.max() + 1, np.random.default_rng(seed), []
    for _ in range(n_resamples):
        idx = np.repeat(np.arange(len(y)), np.bincount(rng.integers(0, n_groups, n_groups), minlength=n_groups)[inv])
        try:
            out.append(sign * (mod.score(y[idx], pb[idx]) - mod.score(y[idx], pa[idx])))
        except Exception:                         # e.g. one class in a resample: skip it
            pass
    return np.array(out)


boot = bool(a.bootstrap) and not screen and a.seed_noise is not None   # the bootstrap read replaces the fold bar
if a.bootstrap:
    bd = group_bootstrap(a.bootstrap)
    if len(bd) < a.bootstrap // 2:
        sys.exit(f"bootstrap: metric undefined on {a.bootstrap - len(bd)} of {a.bootstrap} resamples")
    lo, hi = np.percentile(bd, [2.5, 97.5])
    print(f"group bootstrap ({len(bd)} resamples of {len(np.unique(groups))} {'groups' if gpath.exists() else 'rows (no groups file)'}): "
          f"pooled Δ 95 % interval [{lo:+.5f}, {hi:+.5f}]")
    if screen:
        print("(context only: a screen reads on σΔ per fold, not on the bootstrap)")
    if boot:
        bse = math.sqrt(bd.std(ddof=1) ** 2 + a.seed_noise ** 2 * (1 / k + 1 / (k - 1)))
        print(f"bootstrap read: SE {bse:.5f} (test rows + training noise): pooled Δ = {pooled / bse:.1f} SE")
    elif not screen:
        print("bootstrap read needs --seed-noise (the interval alone ignores training noise); the fold bar decides")
if a.seed_noise and not screen and not boot:                     # σΔ is one fold's seed noise; a k-fold mean carries σΔ/√k
    sn = a.seed_noise / math.sqrt(k)
    print(f"seed noise of a {k}-fold mean {sn:.5f}: mean Δ = {d.mean() / sn:.1f} SE")
if a.hard and not Path(a.hard).exists():
    print(f"hard slice: {a.hard} missing (freeze it in week 1, PLAYBOOK)")
elif a.hard:
    h = np.searchsorted(rows, np.intersect1d(np.load(a.hard), rows))
    try:
        hd = sign * (mod.score(y[h], pb[h]) - mod.score(y[h], pa[h]))
        print(f"hard slice Δ ({len(h)} rows; context, not in the bar): {hd:+.5f}")
    except Exception:                             # e.g. one class on the slice: AUC undefined
        print("hard slice Δ: n/a (metric undefined on slice)")
reasons = []
fold_bar = not screen and not boot
if boot and pooled < 2 * bse:
    reasons.append("pooled Δ < 2 SE (bootstrap)")
if boot and d.min() < -2 * a.seed_noise:
    reasons.append(f"worst fold {d.min():+.4f} < −2 σΔ")
if fold_bar and t < 2:
    reasons.append(f"t {t:.2f} < 2")
if fold_bar and d.min() < 0:
    reasons.append(f"worst fold {d.min():+.4f} < 0")
if fold_bar and pooled < 0:
    reasons.append(f"pooled Δ {pooled:+.4f} < 0")
if a.seed_noise and fold_bar and d.mean() < 2 * a.seed_noise / math.sqrt(k):
    reasons.append("mean Δ < 2 SE seed noise")
if screen and a.seed_noise is None:
    reasons.append(f"{k} fold{'s' * (k > 1)} need{'s' * (k == 1)} --seed-noise")
if screen and a.seed_noise is not None and d.min() < 2 * a.seed_noise:
    reasons.append(("a fold Δ" if k > 1 else "mean Δ") + " < 2 σΔ")
ok = not reasons                                  # one rule: the bar is exactly the list of reasons it fails
if ok and k == 1:
    print("SCREEN READ: B ranks above A (>= 2 σΔ on 1 fold; rank and pause, adopt on 5 folds, law 4)")
elif ok and screen:
    print(f"SCREEN READ ({k} folds): rank only; keep only as kept=P (budget mode, law 4)")
elif ok and boot:
    print("READABLE: B ranks above A (bootstrap read, law 4: pooled Δ >= 2 SE, no fold below -2 σΔ)")
elif ok:
    print("READABLE: B ranks above A (law 4 bar: t >= 2, no fold negative, pooled Δ >= 0"
          + (", >= 2 SE seed noise)" if a.seed_noise else ")"))
elif not screen and (pooled <= -2 * bse if boot else t <= -2 and pooled < 0):
    print("BELOW: B reads below A (this build; the lane stays open, law 8)")
else:
    print("NOT READ: below the bar (law 4: " + ("; ".join(reasons) or "bar not met") + "); not 'dead' either (law 8)")
sys.exit(0 if ok else 1)
