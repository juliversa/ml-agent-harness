#!/usr/bin/env python3
"""The watcher's experiments.csv reads (PLAYBOOK laws 4, 9, §7), called once per pass by kit/watcher.sh.

  python3 kit/exps.py <comp> <days left>

Prints "<n 5-fold rows with oof_mean+public> <bad csv lines, comma-separated, 0 if none> <ruler failure or na>
<plateau message or -> <looping mechanism@row id or -> <ids with no error file or ->", tab-separated (messages hold spaces). Direction: <comp>/.lower == 1 = lower is better."""
import csv, datetime as dt, math, os, re, sys
from collections import Counter
from statistics import median


def read(comp, name):
    try:
        with open(f"{comp}/{name}") as fh:
            return fh.read().strip()
    except OSError:
        return ""


def num(x):
    """A finite float, else None (a NaN row never enters a fit)."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def load(comp):
    """(header, raw body lines, rows as dicts)."""
    try:
        with open(f"{comp}/experiments.csv", newline="") as fh:
            raw = [r for r in csv.reader(fh) if r]
    except OSError:
        raw = []
    hdr, body = (raw[0], raw[1:]) if raw else ([], [])
    return hdr, body, [dict(zip(hdr, r)) for r in body]


def bad_lines(hdr, body, rows):
    """File line numbers with a wrong field count or non-ISO date; '<n>:noparent' for a non-floor row with no parent."""
    bad = []
    for i, r in enumerate(rows):
        if len(body[i]) != len(hdr) or not re.match(r"\d{4}-\d{2}-\d{2}", r.get("date", "")):
            bad.append(str(i + 2))
        elif "parent" in hdr and r.get("kind", "").strip() != "floor" and not r.get("parent", "").strip():
            bad.append(f"{i + 2}:noparent")
    return bad


def five_fold(r):
    return num(r.get("folds")) == 5 if "folds" in r else True   # board statistics use 5-fold rows only


def is_kept(r):
    return (r.get("kept") or "").strip().lower() in ("y", "yes", "1", "true")


def scored(rows):
    """(oof_mean, public) of the 5-fold rows that have both."""
    return [(num(r.get("oof_mean")), num(r.get("public"))) for r in rows
            if five_fold(r) and num(r.get("oof_mean")) is not None and num(r.get("public")) is not None]


def line_fit(pairs):
    """Least-squares slope of y on x and the residual SD (ddof 2)."""
    xs, ys = [x for x, _ in pairs], [y for _, y in pairs]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    vx = sum((x - mx) ** 2 for x in xs)
    slope = sum((x - mx) * (y - my) for x, y in pairs) / vx if vx else 0
    sd = (sum((y - my - slope * (x - mx)) ** 2 for x, y in pairs) / (len(pairs) - 2)) ** .5
    return slope, sd


def ruler(pairs, lb_noise):
    """Law 4: over >= 5 scored subs, public must rise with CV (slope >= 0.5, read over a CV range >= 3 x LB noise)
    and stay within 1.5 x LB noise of its line. Returns the failure, or 'na'."""
    if len(pairs) < 5:
        return "na"
    slope, sd = line_fit(pairs)
    xs = [x for x, _ in pairs]
    if lb_noise is None:
        return "LB noise not measured (.lbnoise is empty, WEEK0 item 10)"
    if slope < 0.5 and max(xs) - min(xs) >= 3 * lb_noise:   # a narrower CV range cannot show the slope through LB noise
        return f"slope {slope:.2f} " + ("(CV rises while the public score falls)" if slope < 0 else "(public gains < half of CV gains)")
    if sd > 1.5 * lb_noise:
        return f"public scatters {sd:.4g} around its CV line, more than 1.5 x LB noise ({1.5 * lb_noise:.4g})"
    return "na"


def cut_in_cv(gold_cut, pairs):
    """Public gold cut -> CV units: minus the median (public - oof_mean) over scored subs (PLAYBOOK "board-adjusted");
    None without a scored sub (keeper.cut_in_cv agrees)."""
    if gold_cut is None or not pairs:
        return None
    return gold_cut - median(y - x for x, y in pairs)


def plateau(kept, gold_cv, days_left, today, sign):
    """Law 9. kept = [(oof_mean * sign, date)] of kept 5-fold rows. With a gold cut in CV units and a row >= 14 d old:
    half the 14-d gain must cover the gap per week left; otherwise: best not improved for 7 d. Returns message or '-'."""
    if not kept:
        return "-"
    best = max(v for v, _ in kept)
    old = [v for v, d in kept if d <= str(today - dt.timedelta(14))]
    if gold_cv is not None and old:
        need = (gold_cv * sign - best) / (max(days_left, 1) / 7)
        gain = (best - max(old)) / 2
        if gain < need:
            return f"14-d gain / 2 = {gain:.4g} < {need:.4g}/week needed to reach CV {gold_cv:.4g} (.goldcut in CV units) in {days_left} d"
        return "-"
    try:
        flat = (today - dt.date.fromisoformat(min(d for v, d in kept if v == best))).days
    except ValueError:
        flat = -1
    return f"best oof_mean not improved for {flat} d" if flat >= 7 else "-"


def safe(s):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", (s or "").strip())


def loops(rows, sign):
    """'<mechanism>@<id>' when the idea and 2 variants failed (R9): 3 kept=N rows on one mechanism since its last kept=Y,
    each with a CV no better than its parent's at the same folds. A kept=N row that beat its parent was superseded, not a failure."""
    cv, folds = {r.get("id"): num(r.get("oof_mean")) for r in rows}, {r.get("id"): r.get("folds") for r in rows}
    fails, out = Counter(), {}
    for r in rows:
        m = safe(r.get("mechanism")).lower()
        if not m:
            continue
        if is_kept(r):
            fails[m] = 0
        elif (r.get("kept") or "").strip().lower() in ("n", "no"):
            v, p = num(r.get("oof_mean")), cv.get(r.get("parent"))
            same = folds.get(r.get("parent")) == r.get("folds")                 # a 1-fold screen is not read against a 5-fold CV
            if v is not None and p is not None and same and v * sign <= p * sign:
                fails[m] += 1
                if fails[m] >= 3:
                    out[m] = safe(r.get("id"))
    return [f"{m}@{i}" for m, i in out.items() if fails[m] >= 3]


def no_error_file(comp, rows):
    """Ids of scored kept or lever rows with no eda/err-<id>.md: nobody read their failing items (PLAYBOOK §7, D5)."""
    return [i for i in dict.fromkeys(safe(r.get("id")) for r in rows if num(r.get("oof_mean")) is not None
                                     and (is_kept(r) or (r.get("kind") or "").strip() == "lever"))
            if i and not os.path.exists(f"{comp}/eda/err-{i}.md")]


def main(comp, days_left):
    hdr, body, rows = load(comp)
    pairs = scored(rows)
    sign = -1 if read(comp, ".lower") == "1" else 1
    kept = [(num(r["oof_mean"]) * sign, (r.get("date") or "")[:10]) for r in rows
            if num(r.get("oof_mean")) is not None and five_fold(r) and is_kept(r)]
    today = dt.datetime.now(dt.timezone.utc).date()
    pl = plateau(kept, cut_in_cv(num(read(comp, ".goldcut")), pairs), days_left, today, sign)
    print(len(pairs), ",".join(bad_lines(hdr, body, rows)) or 0, ruler(pairs, num(read(comp, ".lbnoise"))), pl,
          ",".join(loops(rows, sign)) or "-", ",".join(no_error_file(comp, rows)) or "-", sep="\t")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]))
