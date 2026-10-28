"""Preflight for remote runs > 1 h (skill kaggle-run). Only `code_file` uploads (TOOLING T15), so copy this function to the
top of the kernel, call it first, then run ONE item end to end and print its score.
Example: preflight("cuda", needs=("timm",), paths=("/kaggle/input/**/train.csv",))"""


def preflight(require_device=None, needs=(), paths=(), xla=False):
    import importlib, glob; bad = []
    for m in needs:
        try: importlib.import_module(m)
        except Exception as e: bad.append(f"import {m}: {type(e).__name__}: {e}")
    bad += [f"missing path: {p}" for p in paths if not glob.glob(p, recursive=True)]
    if require_device:
        import torch; got = (("xla" if __import__("torch_xla.runtime").runtime.device_type() == "TPU" else "no TPU") if xla
                             else ("cuda" if torch.cuda.is_available() else "cpu"))
        if got != require_device: bad.append(f"device is {got}, wanted {require_device}")
    if bad: raise SystemExit("PREFLIGHT FAILED:\n  " + "\n  ".join(bad))
    print("[preflight] ok", flush=True)
