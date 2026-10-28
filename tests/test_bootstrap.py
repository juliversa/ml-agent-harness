"""kit/compare.py --bootstrap: the paired group-bootstrap read (PLAYBOOK law 4) and kit/sim_bar.py (c). Fixture: tests/base.py."""
import importlib.util

import numpy as np

from base import KIT, Kit

spec = importlib.util.spec_from_file_location("sim_bar", KIT / "sim_bar.py")
sim = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sim)
MSE = "import numpy as np\ndef score(y, p):\n    return -float(np.mean((p - y) ** 2))\n"


class Arms:
    def arms(self, gain, n=2000, groups=200):
        r = np.random.default_rng(1)
        g = np.arange(n) % groups                                  # whole groups share a fold and a shift
        y = r.normal(size=n) + r.normal(size=groups)[g]
        np.save(self.comp / "data" / "oof_target.npy", y)
        np.save(self.comp / "data" / "folds.npy", g % 5)
        np.save(self.comp / "data" / "groups.npy", g)
        (self.comp / "score.py").write_text(MSE)
        np.save(self.root / "a.npy", y + r.normal(0, 1.0, n))
        np.save(self.root / "b.npy", y + r.normal(0, 1.0 - gain, n))

    def cmp(self, *x):
        return self.run_("python3", str(KIT / "compare.py"), str(self.comp), str(self.root / "a.npy"), str(self.root / "b.npy"), *x)


class Bootstrap(Arms, Kit):
    def test_clear_gain_reads(self):
        self.arms(0.3)
        rc, out = self.cmp("--bootstrap", "300", "--seed-noise", "0.01")
        self.assertEqual(rc, 0, out)
        self.assertIn("resamples of 200 groups", out)
        self.assertIn("READABLE: B ranks above A (bootstrap read", out)

    def test_no_gain_not_read(self):
        self.arms(0.0)
        rc, out = self.cmp("--bootstrap", "300", "--seed-noise", "0.01")
        self.assertEqual(rc, 1, out)
        self.assertIn("NOT READ", out)
        self.assertIn("pooled Δ < 2 SE (bootstrap)", out)

    def test_large_seed_noise_blocks_the_read(self):          # training noise counts, not just test rows
        self.arms(0.3)
        rc, out = self.cmp("--bootstrap", "300", "--seed-noise", "5")
        self.assertEqual(rc, 1, out)

    def test_without_seed_noise_fold_bar_decides(self):
        self.arms(0.3)
        rc, out = self.cmp("--bootstrap", "300")
        self.assertIn("95 % interval", out)
        self.assertIn("the fold bar decides", out)
        self.assertNotIn("bootstrap read:", out)

    def test_bad_args(self):
        self.arms(0.3)
        self.assertIn(">= 100 resamples", self.cmp("--bootstrap", "10")[1])
        self.assertIn("no such file", self.cmp("--bootstrap", "200", "--groups", str(self.root / "none.npy"))[1])


class SimC(Kit):
    def test_bootstrap_read_vs_fold_bar(self):
        for tau, rho in ((0.05, 0.25), (0.1, 0.5)):
            null, gain = sim.fold_vs_bootstrap(0, tau, rho, 3000), sim.fold_vs_bootstrap(1, tau, rho, 3000)
            self.assertLessEqual(null["bootstrap read"], null["fold bar"] + 0.01, (tau, rho))   # no more false passes
            self.assertLessEqual(null["bootstrap read"], 0.05, (tau, rho))
            self.assertGreater(null["boot alone"], null["bootstrap read"], (tau, rho))          # ignoring training noise is unsafe
        self.assertGreater(sim.fold_vs_bootstrap(1, 0.05, 0.25, 3000)["bootstrap read"],
                           sim.fold_vs_bootstrap(1, 0.05, 0.25, 3000)["fold bar"] + 0.08)        # more power at small training noise


class NanFolds(Arms, Kit):   # adversarial review 2026-10-28: NaN inside a run fold was compared on the rows left
    def test_partial_nan_fold_refused(self):
        self.arms(0.3)
        b = np.load(self.root / "b.npy"); b[::7] = np.nan; np.save(self.root / "b.npy", b)
        rc, out = self.cmp()
        self.assertNotEqual(rc, 0, out)
        self.assertIn("NaN on part of fold(s)", out)

    def test_whole_fold_nan_is_a_screen(self):
        self.arms(0.3)
        folds = np.load(self.comp / "data" / "folds.npy")
        b = np.load(self.root / "b.npy"); b[folds != 0] = np.nan; np.save(self.root / "b.npy", b)
        rc, out = self.cmp("--seed-noise", "0.01")
        self.assertIn("compared 400 of 2000 rows", out)
        self.assertIn("SCREEN READ", out)
