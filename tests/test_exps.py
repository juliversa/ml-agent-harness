"""Unit tests of the watcher's log checks (kit/exps.py); the end-to-end alerts are in tests/test_watcher.py."""
import datetime as dt, importlib.util, unittest

from base import KIT

spec = importlib.util.spec_from_file_location("exps", KIT / "exps.py")
exps = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exps)
TODAY = dt.date(2026, 10, 20)


class Exps(unittest.TestCase):
    def test_num_drops_nan_and_text(self):
        self.assertEqual([exps.num(x) for x in ("0.5", "nan", "inf", "", None, "x")], [0.5, None, None, None, None, None])

    def test_ruler(self):
        line = [(x / 100, x / 100) for x in range(90, 95)]
        self.assertEqual(exps.ruler(line[:4], 0.004), "na")                       # < 5 subs: not read
        self.assertEqual(exps.ruler(line, 0.004), "na")                           # public = CV
        self.assertIn("not measured", exps.ruler(line, None))
        self.assertIn("CV rises while the public score falls", exps.ruler([(x, -x) for x, _ in line], 0.004))
        self.assertIn("slope", exps.ruler([(x, 0.5 * x * 0.8) for x, _ in line], 0.004))
        self.assertEqual(exps.ruler([(x, -x) for x, _ in line], 0.02), "na")      # CV range .04 < 3 x LB noise: slope unreadable
        noisy = [(x, x + e) for (x, _), e in zip(line, (.02, -.02, .02, -.02, .02))]
        self.assertIn("scatters", exps.ruler(noisy, 0.004))

    def test_cut_in_cv_uses_median_offset(self):
        self.assertIsNone(exps.cut_in_cv(0.959, []))
        self.assertIsNone(exps.cut_in_cv(None, [(0.9, 0.95)]))
        self.assertAlmostEqual(exps.cut_in_cv(0.959, [(0.90, 0.89), (0.93, 0.91), (0.95, 0.94)]), 0.969)

    def test_plateau(self):
        old, new = "2026-10-01", "2026-10-18"
        self.assertEqual(exps.plateau([], 0.97, 10, TODAY, 1), "-")
        self.assertIn("14-d gain", exps.plateau([(0.90, old), (0.91, new)], 0.97, 7, TODAY, 1))   # .005 / week < .06 needed
        self.assertEqual(exps.plateau([(0.90, old), (0.96, new)], 0.97, 7, TODAY, 1), "-")
        self.assertIn("not improved for 9 d", exps.plateau([(0.90, "2026-10-11")], None, 7, TODAY, 1))
        self.assertEqual(exps.plateau([(0.90, "2026-10-15")], None, 7, TODAY, 1), "-")

    def test_bad_lines(self):
        hdr = ["id", "date", "kind", "parent"]
        body = [["a", "2026-10-01", "floor", ""], ["b", "10/01", "model", "a"], ["c", "2026-10-02", "model", ""], ["d", "2026-10-02", "model"]]
        rows = [dict(zip(hdr, r)) for r in body]
        self.assertEqual(exps.bad_lines(hdr, body, rows), ["3", "4:noparent", "5"])


if __name__ == "__main__":
    unittest.main()


class PickItems(unittest.TestCase):
    def test_screen_oof_picks_scored_rows_only(self):   # a 1-fold screen: NaN outside its fold
        import subprocess, tempfile
        import numpy as np
        with tempfile.TemporaryDirectory() as t:
            p = np.full(100, np.nan); p[:20] = np.linspace(0, 1, 20)
            np.save(f"{t}/oof.npy", p); np.save(f"{t}/y.npy", np.zeros(100))
            out = subprocess.run(["python3", str(KIT / "pick_items.py"), "--oof", f"{t}/oof.npy", "--target", f"{t}/y.npy"],
                                 capture_output=True, text=True).stdout.splitlines()[1:]
        self.assertTrue(out)
        self.assertTrue(all(int(line.split(",")[0]) < 20 for line in out), out)


class AstGateScopes(unittest.TestCase):   # comprehension scope inside a class body (review 2026-10-28)
    def gate(self, code):
        import subprocess, tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".py") as f:
            f.write(code); f.flush()
            return subprocess.run(["python3", str(KIT / "astgate.py"), f.name], capture_output=True).returncode

    def test_class_name_in_comprehension_body_fails(self):
        self.assertNotEqual(self.gate("class A:\n    xs = [1]\n    ys = [x + len(xs) for x in xs]\n"), 0)

    def test_valid_scopes_pass(self):
        for code in ("class A:\n    xs = [1]\n    ys = [x for x in xs]\n", "def f():\n    return __builtins__\n",
                     "ys = [[a + b for b in range(a)] for a in range(3)]\n"):
            with self.subTest(code=code):
                self.assertEqual(self.gate(code), 0)
