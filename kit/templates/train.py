"""One train script per competition (RULES R38): copy to <comp>/code/train.py and fill load() and fit_predict().
The harness part is fixed: the folds file, seeds, OOF on disk, the experiments.csv row with its parent.
The row is scored against data/oof_target.npy (frozen on the first run): labels used for training may change; the scoring target never does.
Role: local screens and CPU models; for a Kaggle run: harvest its OOF, then record it with `train.py --from-oof <path>`.

  python3 competitions/<slug>/code/train.py --id e12 --parent e7 --change "add site term" --kind lever --mechanism site [--folds 0,1,2,3,4] [--seed 0] [--gpu-h 0]
  python3 competitions/<slug>/code/train.py --id e13 --parent e12 --change "..." --kind lever --mechanism m --from-oof <harvested.npy> --gpu-h 2.5

--variant <name> (default "") is passed to load() and fit_predict() to switch arms inside one script; a non-empty one is
recorded in the row's `change` text as "<change> [variant=<name>]".

Writes oof/<id>.npy (NaN outside the folds run), test/<id>.npy if predict_test() is filled (RULES R3: OOF + test of every 5-fold run;
for a Kaggle run, harvest its test predictions to test/<id>.npy too) and appends one experiments.csv row (5-fold or screen), then compare:
  python3 kit/compare.py competitions/<slug> competitions/<slug>/oof/<parent>.npy competitions/<slug>/oof/<id>.npy \
      --hard competitions/<slug>/data/hard_ids.npy
--hard: control = a re-run, not a run that selected the slice (PLAYBOOK Terms)."""
import argparse, csv, datetime as dt, importlib.util
from pathlib import Path

import numpy as np

C = Path(__file__).resolve().parent.parent          # the competition folder
# True if load()'s training labels (pseudo / soft / blended) are built from model OOF predictions. Such labels inflate CV
# unless built per fold: the teacher whose OOF labels fold k never saw fold k (a k-fold teacher). Then pass --labels-oof-fold-safe.
LABELS_FROM_OOF = False


def load(variant=""):
    """Return (X, y, groups) for train; X indexable by row arrays. Fill in per competition."""
    raise NotImplementedError


def fit_predict(X_tr, y_tr, X_va, seed, variant=""):
    """Train on (X_tr, y_tr) with this seed, return predictions for X_va. Fill in per competition."""
    raise NotImplementedError


def predict_test(X_tr, y_tr, seed, variant=""):
    """Optional: return test predictions of a model fit on (X_tr, y_tr); called per fold right after fit_predict().
    Filled → the fold mean is saved to test/<id>.npy. Unfilled → None, nothing saved."""
    return None


def main():
    ap = argparse.ArgumentParser()
    for f in ("--id", "--change", "--kind", "--mechanism"):
        ap.add_argument(f, required=True)
    ap.add_argument("--parent", default="")
    ap.add_argument("--folds", default="0,1,2,3,4")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--note", default="")
    ap.add_argument("--gpu-h", type=float, default=0.0)   # GPU hours spent (0 for local runs)
    ap.add_argument("--from-oof", default="")              # harvested OOF .npy from a Kaggle run: score and record, no training
    ap.add_argument("--variant", default="")               # passed to load() and fit_predict(); recorded in `change`
    ap.add_argument("--labels-oof-fold-safe", action="store_true")   # LABELS_FROM_OOF: labels for fold k came from a teacher that never saw fold k
    a = ap.parse_args()
    if LABELS_FROM_OOF and not a.labels_oof_fold_safe:
        ap.error("labels built from OOF predictions inflate CV unless produced per fold (teacher for fold k never saw fold k); see PLAYBOOK law 4 / LESSONS L2")
    if a.kind != "floor" and not a.parent:
        ap.error("--parent is required on non-floor rows (PLAYBOOK §7)")
    if (C / "oof" / f"{a.id}.npy").exists():
        ap.error(f"id {a.id} is taken (oof/{a.id}.npy exists): one id per run, so every experiments.csv number traces to its file")
    if a.from_oof:
        if not (C / "data" / "oof_target.npy").exists():
            ap.error("data/oof_target.npy missing: np.save the scoring target once before recording a harvested OOF")
        y = np.load(C / "data" / "oof_target.npy")
    else:
        X, y, g = load(a.variant)
    folds = np.load(C / "data" / "folds.npy")          # fixed on day 0 (PLAYBOOK law 3); never re-split
    assert len(folds) == len(y), f"folds.npy has {len(folds)} rows, load() {len(y)}"
    if not a.from_oof and g is not None:
        g = np.asarray(g)
        assert all(len(set(folds[g == v])) == 1 for v in np.unique(g)), "a group spans folds (PLAYBOOK law 3)"
        if not (C / "data" / "groups.npy").exists():
            np.save(C / "data" / "groups.npy", g.astype(str))  # read by kit/compare.py --bootstrap (whole groups resampled)
    spec = importlib.util.spec_from_file_location("score", C / "score.py")
    score = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(score)
    run = [int(k) for k in a.folds.split(",")]
    oof = np.load(a.from_oof) if a.from_oof else None
    assert oof is None or len(oof) == len(y), f"{a.from_oof} has {len(oof)} rows, oof_target.npy {len(y)}"
    if oof is not None:                                # the folds the harvested OOF covers, not --folds
        fin = np.isfinite(oof.reshape(len(oof), -1)).all(1)
        if part := [int(k) for k in np.unique(folds) if fin[folds == k].any() and not fin[folds == k].all()]:
            ap.error(f"{a.from_oof} fills fold(s) {part} only partly: fix the harvest; id {a.id} not used")
        run = [int(k) for k in np.unique(folds) if fin[folds == k].all()]
    tests = []
    for k in ([] if a.from_oof else run):
        tr, va = np.where(folds != k)[0], np.where(folds == k)[0]
        p = np.asarray(fit_predict(X[tr], y[tr], X[va], a.seed, a.variant), dtype=float)
        if not np.isfinite(p).all():                   # a partial fold would be scored, and compared, on the rows it chose
            ap.error(f"fold {k}: fit_predict returned {(~np.isfinite(p)).sum()} non-finite predictions; impute or fix the model")
        if (pt := predict_test(X[tr], y[tr], a.seed, a.variant)) is not None:
            tests.append(np.asarray(pt, dtype=float))
        if oof is None:                                # (n,) or (n, classes)
            oof = np.full((len(y),) + p.shape[1:], np.nan)
        oof[va] = p
        print(f"fold {k}: {score.score(y[va], oof[va]):.5f}", flush=True)
    (C / "oof").mkdir(exist_ok=True)
    if not (C / "data" / "oof_target.npy").exists():
        np.save(C / "data" / "oof_target.npy", y)     # the target kit/compare.py scores OOF files against
    y = np.load(C / "data" / "oof_target.npy")         # frozen truth: the row is scored against it, not load()'s labels
    assert len(y) == len(oof), f"oof_target.npy has {len(y)} rows, OOF {len(oof)}"
    np.save(C / "oof" / f"{a.id}.npy", oof)
    if tests:
        (C / "test").mkdir(exist_ok=True)
        np.save(C / "test" / f"{a.id}.npy", np.mean(tests, axis=0))
    m = np.isin(folds, run)
    hard = C / "data" / "hard_ids.npy"
    h = np.intersect1d(np.load(hard), np.where(m)[0]) if hard.exists() else []
    try:
        oof_hard = f"{score.score(y[h], oof[h]):.6f}" if len(h) else ""
    except Exception:                                  # e.g. one class on the slice: AUC undefined
        print("oof_hard: n/a (metric undefined on slice)")
        oof_hard = ""
    row = [a.id, dt.datetime.now(dt.timezone.utc).date().isoformat(), f"{a.change} [variant={a.variant}]" if a.variant else a.change, a.kind, len(run), a.parent, a.mechanism,
           f"{score.score(y[m], oof[m]):.6f}", oof_hard, "",
           f"{a.gpu_h:.2f}", "", "; ".join(filter(None, (a.note, f"seed={a.seed}")))]   # seed: pairs for σΔ stay traceable
    with open(C / "experiments.csv", "a", newline="") as fh:
        csv.writer(fh).writerow(row)                   # public and kept are filled when known
    print("experiments.csv +=", row)


if __name__ == "__main__":
    main()
