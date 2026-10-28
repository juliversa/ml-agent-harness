#!/usr/bin/env python3
"""Three pictures of a competition from experiments.csv, for the weekly brief.

  python3 kit/graphs.py <comp>      → <comp>/graphs/progress.png, lineage.png, cv_vs_lb.png

progress: best kept five-fold CV by date, against the gold cut moved to CV terms (.goldcut − median(public − CV)).
          The gap between the line and the cut is what is left to win (PLAYBOOK law 9).
lineage:  every row with oof_mean, in file order; a line from each run to its `parent` (the control it changed);
          kept=Y filled, kept=N, P (provisional, budget mode) or C (candidate, law 4) hollow. Shows which ideas grew and which died.
cv_vs_lb: five-fold rows with oof_mean and public; dashed line = best fit; the band = ±1.5 × .lbnoise around it (the ruler's residual-SD bar).
          A visual aid; the trust test is the watcher's ruler (PLAYBOOK law 4)."""
import csv, sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import numpy as np

C = Path(sys.argv[1]) if len(sys.argv) == 2 else sys.exit("usage: graphs.py <comp>")
num = lambda s: (v if np.isfinite(v := float(s)) else None) if s not in (None, "") else None   # NaN/inf: no score, kept out of the fit
def is_five(r):   # same rule as kit/exps.py five_fold: no folds column = 5-fold
    if "folds" not in r:
        return True
    try:
        return float(r["folds"]) == 5
    except (TypeError, ValueError):
        return False
is_kept = lambda r: (r.get("kept") or "").strip().lower() in ("y", "yes", "1", "true")
rows = []
for r in csv.DictReader(open(C / "experiments.csv")):
    try:
        r["cv"], r["lb"] = num(r.get("oof_mean")), num(r.get("public"))
    except ValueError:
        continue
    if r["cv"] is not None:
        rows.append(r)
out = C / "graphs"
out.mkdir(exist_ok=True)
lower = (C / ".lower").exists() and (C / ".lower").read_text().strip() == "1"

fig, ax = plt.subplots(figsize=(10, 5))
pos = {r["id"]: (i, r["cv"]) for i, r in enumerate(rows)}
for r in rows:
    if r.get("parent") in pos:
        (x0, y0), (x1, y1) = pos[r["parent"]], pos[r["id"]]
        ax.plot([x0, x1], [y0, y1], color="0.7", lw=1, zorder=1)
for r in rows:
    x, y = pos[r["id"]]
    kept = is_kept(r)
    ax.scatter(x, y, s=50, zorder=2, marker="o" if is_five(r) else "^", facecolor="tab:blue" if kept else "white", edgecolor="tab:blue")
    ax.annotate(r["id"], (x, y), textcoords="offset points", xytext=(0, 7), ha="center", fontsize=7)
ax.xaxis.set_major_locator(MaxNLocator(integer=True))
ax.set(xlabel="run, in order", ylabel="CV (oof_mean)" + (", lower is better" if lower else ""),
       title=f"{C.name}: experiment lineage (filled = kept, triangle = 1 fold, line = changed from parent)")
fig.tight_layout()
fig.savefig(out / "lineage.png", dpi=110)
plt.close(fig)

five = [r for r in rows if is_five(r)]
fig, ax = plt.subplots(figsize=(10, 4))
best, xs, ys = None, [], []
for r in sorted((r for r in five if is_kept(r)), key=lambda r: r.get("date", "")):
    if best is None or (r["cv"] < best if lower else r["cv"] > best):
        best = r["cv"]
    xs.append(r.get("date", "")), ys.append(best)
if xs:
    ax.step(range(len(xs)), ys, where="post", color="tab:blue", label="best kept CV (5 folds)")
    ax.set_xticks(range(len(xs)), xs, rotation=45, ha="right", fontsize=7)
gap = [r["lb"] - r["cv"] for r in five if r["lb"] is not None]
cut = num((C / ".goldcut").read_text().strip()) if (C / ".goldcut").exists() else None
if cut is not None and gap:
    ax.axhline(cut - float(np.median(gap)), color="goldenrod", ls="--", label="gold cut in CV terms")
if ax.get_legend_handles_labels()[0]:              # no legend (and no matplotlib warning) on an empty chart
    ax.legend(fontsize=8)
ax.set(ylabel="CV" + (", lower is better" if lower else ""), title=f"{C.name}: progress toward the gold cut")
fig.tight_layout()
fig.savefig(out / "progress.png", dpi=110)
plt.close(fig)

pts = [(r["cv"], r["lb"], r["id"]) for r in rows if r["lb"] is not None and is_five(r)]
fig, ax = plt.subplots(figsize=(6, 5))
if pts:
    cv, lb = np.array([p[0] for p in pts]), np.array([p[1] for p in pts])
    ax.scatter(cv, lb, color="tab:blue", zorder=2)
    for c, l, i in pts:
        ax.annotate(i, (c, l), textcoords="offset points", xytext=(4, 4), fontsize=7)
    if len(pts) >= 3 and np.ptp(cv) > 0:
        a, b = np.polyfit(cv, lb, 1)
        xs = np.linspace(cv.min(), cv.max(), 50)
        ax.plot(xs, a * xs + b, "--", color="0.4", label=f"fit: slope {a:.2f}")
        noise = num((C / ".lbnoise").read_text().strip()) if (C / ".lbnoise").exists() else None
        if noise:
            ax.fill_between(xs, a * xs + b - 1.5 * noise, a * xs + b + 1.5 * noise, color="tab:blue", alpha=0.1,
                            label="±1.5 × LB noise (bar is on the SD; ~1 in 7 points outside is normal)")
        ax.legend(fontsize=8)
else:
    ax.text(0.5, 0.5, "no five-fold run with a public score yet", ha="center", transform=ax.transAxes)
ax.set(xlabel="CV (oof_mean, 5 folds)", ylabel="public leaderboard", title=f"{C.name}: does CV track the leaderboard?")
fig.tight_layout()
fig.savefig(out / "cv_vs_lb.png", dpi=110)
plt.close(fig)
print(f"wrote {out}/progress.png, {out}/lineage.png ({len(rows)} runs, {sum(map(is_kept, rows))} kept), {out}/cv_vs_lb.png ({len(pts)} five-fold subs)")
