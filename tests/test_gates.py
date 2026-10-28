"""Offline tests of the submit and push gates, harvest, linters and the ML layer (train template, compare, graphs, fanout). Fixture: tests/base.py."""
import os, unittest

from base import KIT, Kit


class Gates(Kit):
    # submit gate -------------------------------------------------------------
    def test_file_matching_sample_passes(self):
        f = self.root / "s.csv"
        f.write_text("id,target\n3,0.2\n1,0.5\n2,0.4\n")
        rc, out = self.gate("--file", str(f))
        self.assertEqual(rc, 0, out)
        self.assertIn("DRY RUN", out)

    def test_file_submit_records_in_log_md(self):
        f, log = self.root / "s.csv", self.comp / "log.md"
        f.write_text("id,target\n3,0.2\n1,0.5\n2,0.4\n")
        rc, out = self.run_("python3", str(KIT / "submit_gate.py"), "--file", str(f), "--competition", "demo-ref",
                            "--desc", "t", "--probe", "test", "--log-md", str(log))
        self.assertEqual(rc, 0, out)
        self.assertIn("SUBMITTED: Successfully submitted to demo", out)
        self.assertIn(f"- **submitted** `file {f}` — t — PROBE: test — ref Successfully submitted to demo", log.read_text())

    def test_kaggle_not_on_path_aborts(self):
        import sys
        f = self.root / "s.csv"; f.write_text("id,target\n1,0.5\n2,0.1\n3,0.9\n")
        rc, out = self.run_(sys.executable, str(KIT / "submit_gate.py"), "--file", str(f), "--competition", "demo-ref", "--desc", "t",
                            "--probe", "test", "--dry-run", PATH=str(self.root / "empty"))
        self.assertNotEqual(rc, 0, out)
        self.assertIn("ABORT: kaggle not on PATH", out)
        self.assertNotIn("Traceback", out)

    def test_bad_files_abort(self):
        for body, why in [("id,target\n1,0.5\n2,nan\n3,1\n", "NaN"), ("id,target\n1,0.5\n2,0.1\n4,0.9\n", "ids"),
                          ("id,score\n1,0.5\n2,0.1\n3,0.9\n", "header"), ("id,target\n1,0.5\n2,0.1\n", "rows"),
                          ("id,target\n1,0.5\n\n3,1\n", "blank row")] + [
                          (f"id,target\n1,0.5\n2,{v}\n3,1\n", v) for v in ("inf", "-INF", "+Inf", "None", "null")]:
            f = self.root / "s.csv"
            f.write_text(body)
            rc, out = self.gate("--file", str(f))
            self.assertNotEqual(rc, 0, why)
            self.assertIn("ABORT", out, why)

    def test_unparsed_push_version_aborts(self):
        self.events("PUSH me/k1 v7", "PUSH me/k1 v?")
        rc, out = self.gate("--kernel", "me/k1", "--version", "7")
        self.assertNotEqual(rc, 0)
        self.assertIn("is v?, not v7", out)

    def test_stale_version_aborts(self):
        self.events("PUSH me/k1 v4", "PUSH me/k1 v5")
        rc, out = self.gate("--kernel", "me/k1", "--version", "4")
        self.assertNotEqual(rc, 0)
        self.assertIn("is v5, not v4", out)

    def test_kernel_log_gate(self):
        self.events("PUSH me/k1 v7")
        for log, extra, want in [("x\nTraceback (most recent call last):\n", (), "kernel log problems"),
                                 ("", (), "kernel log is EMPTY"), ("", ("--no-log-reason", "ran locally"), "DRY RUN"),
                                 ("epoch 1 ok\n", (), "DRY RUN")]:
            rc, out = self.run_("python3", str(KIT / "submit_gate.py"), "--competition", "demo-ref", "--desc", "t", "--probe", "test",
                                "--dry-run", "--kernel", "me/k1", "--version", "7", *extra, FAKE_LOG=log)
            self.assertEqual(rc != 0, want != "DRY RUN", out)
            self.assertIn(want, out)

    def test_code_submit_without_ref_aborts(self):
        self.events("PUSH me/k1 v7")
        api = self.root / "py" / "kaggle" / "api"
        api.mkdir(parents=True)
        (api.parent / "__init__.py").write_text("")
        (api / "__init__.py").write_text("")
        (api / "kaggle_api_extended.py").write_text(
            "class KaggleApi:\n    def authenticate(self): pass\n"
            "    def competition_submit_code(self, **kw):\n        return type('R', (), {'message': 'quota error', 'ref': None})()\n")
        rc, out = self.run_("python3", str(KIT / "submit_gate.py"), "--competition", "demo-ref", "--desc", "t", "--probe", "test",
                            "--kernel", "me/k1", "--version", "7", FAKE_LOG="ok\n", PYTHONPATH=str(self.root / "py"))
        self.assertNotEqual(rc, 0, out)
        self.assertIn("no submission ref in the response: quota error", out)

    def test_gpu_without_accelerator_refused(self):
        rc, out = self.run_("bash", str(KIT / "push_and_watch.sh"), str(self.kernel_dir()))
        self.assertEqual(rc, 2, out)

    def test_bogus_accelerator_refused(self):
        for acc in ("NvidiaTeslaT4x", "--accelerator=GpuT4"):
            args = ("--accelerator", acc) if "=" not in acc else (acc,)
            rc, out = self.run_("bash", str(KIT / "push_and_watch.sh"), str(self.kernel_dir()), *args)
            self.assertEqual(rc, 2, out)
            self.assertIn("TOOLING T8", out)

    def test_second_kernel_path_refused(self):
        for args in (("-p", "other"), ("--path", "other"), ("--path=other",), ("--accelerator", "NvidiaTeslaT4", "-p", "other")):
            rc, out = self.run_("bash", str(KIT / "push_and_watch.sh"), str(self.kernel_dir()), *args)
            self.assertEqual(rc, 2, out)
            self.assertIn("kernel dir is the first argument only", out)
        # the CLI takes option prefixes: --pa = --path, --acc = --accelerator (would skip the GO gate); only the allow-list passes
        for args in (("--pa", "other"), ("--acc", "NvidiaTeslaT4"), ("--acc=NvidiaTeslaT4",), ("other",), ("-t", "60", "x")):
            rc, out = self.run_("bash", str(KIT / "push_and_watch.sh"), str(self.kernel_dir()), *args)
            self.assertEqual(rc, 2, out)
            self.assertIn("only --accelerator and -t/--timeout pass", out)

    def test_timeout_option_passes(self):
        k, plan = self.kernel_dir(), self.comp / "plans" / "k1.md"
        plan.write_text("kind: base\nidea\n")
        self.sign(plan)
        for extra in (("-t", "600"), ("--timeout=600",)):
            rc, out = self.run_("bash", str(KIT / "push_and_watch.sh"), str(k), "--accelerator", "NvidiaTeslaT4", *extra)
            self.assertEqual(rc, 0, out)

    def test_unsigned_go_refused(self):
        k, plan = self.kernel_dir(), self.comp / "plans" / "k1.md"
        plan.write_text("kind: base\nidea\nVerdict: GO\n")
        rc, out = self.push(k)
        self.assertEqual(rc, 6, out)
        self.assertIn("is not GO for this plan's hash", out)
        self.sign(plan)
        for b in (self.comp / "plans").glob("k1-batch.*"):
            b.unlink()
        rc, out = self.push(k)
        self.assertEqual(rc, 6, out)
        self.assertIn("no " + str(self.comp / "plans" / "k1") + "-batch.* > 1 KB", out)

    def test_signed_go_pushes_then_edit_voids_it(self):
        k, plan = self.kernel_dir(), self.comp / "plans" / "k1.md"
        plan.write_text("kind: base\nidea\n")
        self.sign(plan)
        rc, out = self.push(k)
        self.assertEqual(rc, 0, out)
        self.assertIn("PUSH me/k1 v7", (self.comp / "events.log").read_text())
        plan.write_text(plan.read_text().replace("idea\n", "idea\nextra run\n"))
        rc, out = self.push(k)
        self.assertEqual(rc, 6, out)
        self.assertIn("plan edited after review?", out)

    def test_push_resets_kernel_state(self):
        k, plan = self.kernel_dir(), self.comp / "plans" / "k1.md"
        plan.write_text("kind: base\nidea\n")
        self.sign(plan)
        (self.comp / ".kstate").write_text("me/k1 complete\nme/k2 running\n")
        (self.comp / ".alerts").mkdir()
        (self.comp / ".alerts" / "k-me_k1-complete").touch()
        rc, out = self.push(k)
        self.assertEqual(rc, 0, out)
        self.assertEqual((self.comp / ".kstate").read_text(), "me/k2 running\n")   # a re-run that completes within one poll alerts again
        self.assertEqual(list((self.comp / ".alerts").iterdir()), [])
        rc, out = self.run_("bash", str(KIT / "watcher.sh"), "demo", "--once", CLAUDE_PROJECTS=str(self.root / "none"))
        self.assertIn("ALERT [k-me_k1-complete]", (self.comp / "events.log").read_text())

    def test_lever_needs_elite_spec(self):
        k, plan = self.kernel_dir(), self.comp / "plans" / "k1.md"
        plan.write_text("kind: lever\nlever: L1\n")                     # signed, no elite-spec line
        self.sign(plan)
        rc, out = self.push(k)
        self.assertEqual(rc, 6, out)
        self.assertIn("elite-spec", out)
        plan.write_text("kind: lever\nlever: L1\nelite-spec: plans/elite-L1.md\n")
        self.sign(plan)
        rc, out = self.push(k)                                              # names a file that does not exist yet
        self.assertEqual(rc, 6, out)
        self.assertIn("elite-spec", out)
        (self.comp / "plans" / "elite-L1.md").write_text("spec\n")
        rc, out = self.push(k)
        self.assertEqual(rc, 0, out)

    def test_missing_version_logged_as_unknown(self):
        k, plan = self.kernel_dir(), self.comp / "plans" / "k1.md"
        plan.write_text("kind: base\n")
        self.sign(plan)
        rc, out = self.push(k, FAKE_VERSION="")
        self.assertIn("WARN: no version", out)
        self.assertIn("PUSH me/k1 v?", (self.comp / "events.log").read_text())

    def test_astgate_function_local_is_not_global(self):
        for src in ("def f():\n    cfg = 1\nprint(cfg)\n", "def f():\n    cfg = 1\ndef g():\n    return cfg\n"):
            p = self.root / "a.py"
            p.write_text(src)
            rc, out = self.run_("python3", str(KIT / "astgate.py"), str(p))
            self.assertNotEqual(rc, 0, src)
        p.write_text("import os\nfor i in range(2):\n    x = i\ndef f():\n    global y\n    y = x\n    return os, y\n")
        self.assertEqual(self.run_("python3", str(KIT / "astgate.py"), str(p))[0], 0)
        p.write_text("def train():\n    lr = 1e-3\n    def step():\n        return lr * 2\n    return step()\n")   # closure
        self.assertEqual(self.run_("python3", str(KIT / "astgate.py"), str(p))[0], 0)
        p.write_text("class CFG:\n    epochs = 10\n    steps = epochs * 100\n")                 # a class body reads its own earlier names
        self.assertEqual(self.run_("python3", str(KIT / "astgate.py"), str(p))[0], 0)
        p.write_text("class A:\n    z = 1\nprint(z)\n")                                          # but they are not module names
        self.assertNotEqual(self.run_("python3", str(KIT / "astgate.py"), str(p))[0], 0)

    def test_astgate_comprehension_scope(self):
        p = self.root / "a.py"
        gate = lambda src: (p.write_text(src), self.run_("python3", str(KIT / "astgate.py"), str(p)))[1]
        rc, out = gate("print([y for y in range(2)])\nprint(y)\n")          # the loop variable does not leak
        self.assertNotEqual(rc, 0, out)
        self.assertIn("line 2: y", out)
        for src in ("print([y for y in range(2)])\n", "z = {k: v for k, v in [(1, 2)]}\n",
                    "s = sum(a * b for a in range(3) for b in range(a))\n", "print([n := 1 for _ in range(2)])\nprint(n)\n"):
            rc, out = gate(src)
            self.assertEqual(rc, 0, src + out)
        for own in ("astgate.py", "submit_gate.py", "compare.py", "video/engine.py"):                       # the kit itself
            self.assertEqual(self.run_("python3", str(KIT / "astgate.py"), str(KIT / own))[0], 0, own)

    def test_depslint_exact_names_and_all_mounts(self):
        k = self.root / "dk"
        k.mkdir()
        (k / "k.py").write_text('assert os.path.exists("/kaggle/input/deberta-xl-weights"), "deberta-xl-weights dataset not attached"\n'
                                'm = "/kaggle/input/mykern/out.csv"; w = "/kaggle/input/mymodel/1"\n')
        meta = {"id": "me/k", "code_file": "k.py", "dataset_sources": ["me/x"], "kernel_sources": ["me/mykern"],
                "model_sources": ["me/mymodel/pytorch/default/1"]}
        (k / "kernel-metadata.json").write_text(__import__("json").dumps(meta))
        rc, out = self.run_("python3", str(KIT / "depslint.py"), str(k))
        self.assertEqual(rc, 2, out)
        self.assertIn("deberta-xl-weights", out)
        self.assertNotIn("dataset 'mykern'", out)
        self.assertNotIn("dataset 'mymodel'", out)

    def test_push_refuses_bad_metadata_and_bad_elite_spec(self):
        k, plan = self.kernel_dir(), self.comp / "plans" / "k1.md"
        good = (k / "kernel-metadata.json").read_text()
        (k / "kernel-metadata.json").write_text("{not json")
        self.assertEqual(self.push(k, NOLINT="1")[0], 2)
        (k / "kernel-metadata.json").write_text(good)
        for spec in ("plans", "../escape.md", "/etc/hosts", "events.log-missing"):
            plan.write_text(f"kind: lever\nlever: L1\nelite-spec: {spec}\n")
            self.sign(plan)
            self.assertEqual(self.push(k)[0], 6, spec)

    def test_harvest_failed_pull_not_recorded(self):
        self.events("PUSH me/k1 v3")
        fake = self.root / "bin2"
        fake.mkdir()
        (fake / "kaggle").write_text('#!/bin/bash\ncase "$1 $2" in "kernels status") echo COMPLETE;; '
                                     '"kernels output") echo "404 Not Found"; exit 1;; esac\n')
        (fake / "kaggle").chmod(0o755)
        rc, out = self.run_("bash", str(KIT / "harvest.sh"), "me/k1", PATH=f"{fake}:{os.environ['PATH']}")
        self.assertEqual(rc, 1, out)
        self.assertNotIn("HARVEST", (self.comp / "events.log").read_text())

    def test_harvest_check_unreadable_status_fails(self):
        fake = self.root / "bin3"
        fake.mkdir()
        (fake / "kaggle").write_text('#!/bin/bash\ncase "$1 $2" in "kernels list") printf "ref,title\\nme/k1,K1\\n";; '
                                     '"kernels status") echo "403 Forbidden";; esac\n')
        (fake / "kaggle").chmod(0o755)
        rc, out = self.run_("bash", str(KIT / "harvest_check.sh"), str(self.comp), "k1", PATH=f"{fake}:{os.environ['PATH']}")
        self.assertNotEqual(rc, 0, out)
        self.assertIn("1 unreadable", out)

    def test_incumbent_lower_is_better_and_numeric_folds(self):
        (self.comp / ".lower").write_text("1\n")
        with open(self.comp / "experiments.csv", "a") as fh:
            fh.write("a,2026-01-01,x,base,5.0,,m,0.20,,,1,Y,\nb,2026-01-01,x,base,1,a,m,0.10,,,1,Y,\nc,2026-01-01,x,base,5,a,m,0.30,,,1,Y,\n")
        f = self.root / "s.csv"
        f.write_text("id,target\n1,0.5\n2,0.1\n3,0.9\n")
        rc, out = self.run_("python3", str(KIT / "submit_gate.py"), "--file", str(f), "--competition", "demo-ref",
                            "--desc", "t", "--cv", "0.25", "--agg", "pooled", "--dry-run")
        self.assertIn("incumbent OOF 0.2", out)
        self.assertIn("WORSE", out)
        rc, out = self.gate("--file", str(f), "--cv", "nan", "--agg", "x")
        self.assertNotEqual(rc, 0)

    def test_kept_p_is_valid_but_not_the_incumbent(self):   # budget mode (PLAYBOOK law 4): kept=P is provisional
        with open(self.comp / "experiments.csv", "a") as fh:
            fh.write("a,2026-01-01,x,floor,5,,m,0.80,,,1,Y,\nb,2026-01-02,x,lever,1,a,m,0.90,,,1,P,\n"
                     "c,2026-01-03,x,lever,5,a,m,0.95,,,1,P,\n")
        rc, out = self.run_("bash", str(KIT / "watcher.sh"), "demo", "--once")
        self.assertEqual(rc, 0, out)
        self.assertNotIn("csvbad", (self.comp / "events.log").read_text())
        self.assertIn("BEST: CV 0.80 (a)", self.run_("bash", str(KIT / "status.sh"), "demo")[1])
        f = self.root / "s.csv"
        f.write_text("id,target\n1,0.5\n2,0.1\n3,0.9\n")
        rc, out = self.run_("python3", str(KIT / "submit_gate.py"), "--file", str(f), "--competition", "demo-ref",
                            "--desc", "t", "--cv", "0.85", "--agg", "pooled", "--dry-run")
        self.assertIn("incumbent OOF 0.8", out)

    def test_kept_c_is_valid_but_not_kept(self):   # PLAYBOOK law 4: a candidate counts only once its stack passes the 5-fold bar
        with open(self.comp / "experiments.csv", "a") as fh:
            fh.write("a,2026-01-01,x,floor,5,,m,0.80,,,1,Y,\nb,2026-01-02,x,lever,5,a,m,0.95,,,1,C,\n")
        rc, out = self.run_("bash", str(KIT / "watcher.sh"), "demo", "--once")
        self.assertEqual(rc, 0, out)
        self.assertNotIn("csvbad", (self.comp / "events.log").read_text())
        self.assertIn("BEST: CV 0.80 (a)", self.run_("bash", str(KIT / "status.sh"), "demo")[1])
        f = self.root / "s.csv"
        f.write_text("id,target\n1,0.5\n2,0.1\n3,0.9\n")
        rc, out = self.run_("python3", str(KIT / "submit_gate.py"), "--file", str(f), "--competition", "demo-ref",
                            "--desc", "t", "--cv", "0.85", "--agg", "pooled", "--dry-run")
        self.assertIn("incumbent OOF 0.8", out)
        self.assertIn("(2 runs, 1 kept)", self.run_("python3", str(KIT / "graphs.py"), str(self.comp))[1])

    # ML layer: train template -> OOF + experiments row -> compare --------------
    def test_train_template_then_compare(self):
        import numpy as np
        rng = np.random.default_rng(0)
        n = 500
        np.save(self.comp / "data" / "folds.npy", np.arange(n) % 5)
        np.save(self.comp / "data" / "hard_ids.npy", np.arange(0, n, 10))
        (self.comp / "score.py").write_text("import numpy as np\ndef score(y, p):\n    return float(np.mean((p > .5) == y))\n")
        X = rng.normal(size=(n, 3))
        y = (X[:, 0] + 0.5 * rng.normal(size=n) > 0).astype(int)
        np.save(self.root / "X.npy", X)
        np.save(self.root / "y.npy", y)
        src = (KIT / "templates" / "train.py").read_text()
        src = src.replace('    """Return (X, y, groups) for train; X indexable by row arrays. Fill in per competition."""\n    raise NotImplementedError',
                          f'    return np.load("{self.root}/X.npy"), np.load("{self.root}/y.npy"), None')
        src = src.replace('    """Train on (X_tr, y_tr) with this seed, return predictions for X_va. Fill in per competition."""\n    raise NotImplementedError',
                          '    w = np.linalg.lstsq(X_tr[:, COLS], y_tr - .5, rcond=None)[0]\n    return X_va[:, COLS] @ w + .5')
        for name, cols in (("weak", "1:3"), ("strong", ":")):          # weak never sees the signal column 0
            (self.comp / "code" / f"train_{name}.py").write_text(src.replace("COLS", cols))
        for i, name in ((1, "weak"), (2, "strong")):
            rc, out = self.run_("python3", str(self.comp / "code" / f"train_{name}.py"), "--id", f"e{i}", "--parent",
                                "e1" if i == 2 else "", "--change", name, "--kind", "base" if i == 2 else "floor", "--mechanism", "m")
            self.assertEqual(rc, 0, out)
        rc, out = self.run_("python3", str(self.comp / "code" / "train_weak.py"), "--id", "e3", "--change", "x", "--kind", "lever", "--mechanism", "m")
        self.assertEqual(rc, 2, out)                                  # a non-floor row without --parent is refused
        self.assertIn("--parent is required on non-floor rows", out)
        rows = (self.comp / "experiments.csv").read_text().splitlines()
        self.assertEqual(len(rows), 3)
        self.assertIn("e2,", rows[2])
        self.assertIn(",5,e1,", rows[2])
        rc, out = self.run_("python3", str(KIT / "compare.py"), str(self.comp), str(self.comp / "oof" / "e1.npy"),
                            str(self.comp / "oof" / "e2.npy"), "--hard", str(self.comp / "data" / "hard_ids.npy"))
        self.assertEqual(rc, 0, out)
        self.assertIn("READABLE", out)
        rc, out = self.run_("python3", str(KIT / "compare.py"), str(self.comp), str(self.comp / "oof" / "e2.npy"),
                            str(self.comp / "oof" / "e1.npy"))
        self.assertEqual(rc, 1, out)
        self.assertIn("BELOW", out)                                   # t <= -2 and pooled Δ < 0

    def test_pick_items_groups_seeded(self):
        import numpy as np
        n = 100
        np.save(self.comp / "data" / "oof_target.npy", np.zeros(n))
        (self.comp / "oof").mkdir()
        np.save(self.comp / "oof" / "e1.npy", np.arange(n) / n)       # error grows with the row index
        rc, out = self.run_("python3", str(KIT / "pick_items.py"), "--oof", str(self.comp / "oof" / "e1.npy"),
                            "--score-dir", str(self.comp), "--seed", "1")
        self.assertEqual(rc, 0, out)
        rows = [r.split(",") for r in (self.comp / "eda" / "pick-e1.csv").read_text().splitlines()[1:]]
        g = {k: [int(r[0]) for r in rows if r[1] == k] for k in ("worst", "clean", "random")}
        self.assertEqual(g["worst"], list(range(99, 79, -1)))
        self.assertEqual(g["clean"], list(range(10)))
        self.assertEqual(len(g["random"]), 10)
        self.assertTrue(all(10 <= i < 80 for i in g["random"]))
        self.assertEqual(out, self.run_("python3", str(KIT / "pick_items.py"), "--oof", str(self.comp / "oof" / "e1.npy"),
                                        "--score-dir", str(self.comp), "--seed", "1")[1])   # same seed, same pick
        p3 = np.full((n, 3), .1)
        p3[np.arange(n), np.arange(n) % 3] = .8
        p3[5] = [.9, .05, .05]                                      # row 5 is class 2 with p_true .05
        np.save(self.root / "p3.npy", p3)
        np.save(self.root / "y3.npy", np.arange(n) % 3)
        rc, out = self.run_("python3", str(KIT / "pick_items.py"), "--oof", str(self.root / "p3.npy"),
                            "--target", str(self.root / "y3.npy"))
        self.assertEqual(rc, 0, out)
        self.assertEqual(out.splitlines()[1], "5,worst,0.95")

    def train_src(self, n=40, groups="None"):
        """The template filled with a perfect predictor on n rows (y = row % 2), groups from the expression `groups`."""
        import numpy as np
        np.save(self.root / "y.npy", np.arange(n) % 2)
        src = (KIT / "templates" / "train.py").read_text()
        src = src.replace("    raise NotImplementedError", f'    y = np.load("{self.root}/y.npy")\n    return y[:, None].astype(float), y, {groups}', 1)
        src = src.replace("    raise NotImplementedError", "    return X_va[:, 0] if variant != 'flip' else 1 - X_va[:, 0]", 1)
        return src

    def test_train_group_spanning_folds_refused_and_variant_recorded(self):
        import numpy as np
        np.save(self.comp / "data" / "folds.npy", np.arange(40) % 5)
        (self.comp / "score.py").write_text("import numpy as np\ndef score(y, p):\n    return float(np.mean((p > .5) == y))\n")
        t = self.comp / "code" / "train.py"
        t.write_text(self.train_src(groups="np.arange(40) // 2"))      # rows 0,1 share a group but sit in folds 0 and 1
        rc, out = self.run_("python3", str(t), "--id", "e1", "--change", "c", "--kind", "floor", "--mechanism", "m")
        self.assertNotEqual(rc, 0, out)
        self.assertIn("a group spans folds (PLAYBOOK law 3)", out)
        t.write_text(self.train_src(groups="np.arange(40) % 5"))        # one group per fold: whole
        rc, out = self.run_("python3", str(t), "--id", "e1", "--change", "c", "--kind", "floor", "--mechanism", "m", "--variant", "flip")
        self.assertEqual(rc, 0, out)
        row = (self.comp / "experiments.csv").read_text().splitlines()[-1].split(",")
        self.assertEqual((row[2], row[7]), ("c [variant=flip]", "0.000000"))   # the variant reached fit_predict and the change text

    def test_hard_slice_missing_or_undefined(self):
        import numpy as np
        np.save(self.comp / "data" / "folds.npy", np.arange(40) % 5)
        (self.comp / "score.py").write_text("import numpy as np\ndef score(y, p):\n    assert len(set(y.tolist())) == 2, 'one class'\n"
                                            "    return float(np.mean((p > .5) == y))\n")
        t = self.comp / "code" / "train.py"
        t.write_text(self.train_src())
        for i in (1, 2):
            rc, out = self.run_("python3", str(t), "--id", f"e{i}", "--parent", "e1" if i == 2 else "", "--change", "c",
                                "--kind", "floor" if i == 1 else "base", "--mechanism", "m")
            self.assertEqual(rc, 0, out)
        hard = self.comp / "data" / "hard_ids.npy"
        cmp = ("python3", str(KIT / "compare.py"), str(self.comp), str(self.comp / "oof" / "e1.npy"), str(self.comp / "oof" / "e2.npy"), "--hard", str(hard))
        rc, out = self.run_(*cmp)
        self.assertIn(f"hard slice: {hard} missing (freeze it in week 1, PLAYBOOK)", out)
        self.assertIn("NOT READ", out)                                  # the read itself still runs
        np.save(hard, np.arange(0, 40, 2))                               # even rows: one class only
        rc, out = self.run_(*cmp)
        self.assertIn("hard slice Δ: n/a (metric undefined on slice)", out)
        rc, out = self.run_("python3", str(t), "--id", "e3", "--parent", "e1", "--change", "c", "--kind", "base", "--mechanism", "m")
        self.assertEqual(rc, 0, out)
        self.assertIn("oof_hard: n/a (metric undefined on slice)", out)
        self.assertEqual((self.comp / "experiments.csv").read_text().splitlines()[-1].split(",")[8], "")

    def test_train_from_oof_records_kaggle_run(self):
        import numpy as np
        n = 50
        y = np.arange(n) % 2
        np.save(self.comp / "data" / "oof_target.npy", y)
        np.save(self.comp / "data" / "folds.npy", np.arange(n) % 5)
        (self.comp / "score.py").write_text("import numpy as np\ndef score(y, p):\n    return float(np.mean((p > .5) == y))\n")
        (self.comp / "code" / "train.py").write_text((KIT / "templates" / "train.py").read_text())   # load()/fit_predict() unfilled: must not be called
        oof = y.astype(float)
        oof[:5] = 1 - oof[:5]                                         # 5 of 50 wrong -> 0.9
        np.save(self.root / "harvested.npy", oof)
        rc, out = self.run_("python3", str(self.comp / "code" / "train.py"), "--id", "e9", "--parent", "e1", "--change", "kaggle run",
                            "--kind", "lever", "--mechanism", "m", "--from-oof", str(self.root / "harvested.npy"), "--gpu-h", "2.5")
        self.assertEqual(rc, 0, out)
        self.assertTrue(np.array_equal(np.load(self.comp / "oof" / "e9.npy"), oof))
        row = (self.comp / "experiments.csv").read_text().splitlines()[-1].split(",")
        self.assertEqual((row[0], row[4], row[7], row[10]), ("e9", "5", "0.900000", "2.50"))
        (self.comp / "data" / "oof_target.npy").unlink()             # no scoring target saved yet: refuse, do not crash
        rc, out = self.run_("python3", str(self.comp / "code" / "train.py"), "--id", "e10", "--parent", "e1", "--change", "kaggle run",
                            "--kind", "lever", "--mechanism", "m", "--from-oof", str(self.root / "harvested.npy"))
        self.assertEqual(rc, 2, out)
        self.assertIn("data/oof_target.npy missing: np.save the scoring target once before recording a harvested OOF", out)

    def test_train_scores_against_frozen_target_after_relabel(self):
        import numpy as np
        n = 50
        y0 = np.arange(n) % 2                                         # frozen truth, written on day 0
        y1 = y0.copy(); y1[:5] = 1 - y1[:5]                           # round-1 relabel: training labels changed
        np.save(self.comp / "data" / "oof_target.npy", y0)
        np.save(self.comp / "data" / "folds.npy", np.arange(n) % 5)
        np.save(self.comp / "data" / "hard_ids.npy", np.arange(5))
        np.save(self.root / "X.npy", y0[:, None].astype(float))
        np.save(self.root / "y1.npy", y1)
        (self.comp / "score.py").write_text("import numpy as np\ndef score(y, p):\n    return float(np.mean((p > .5) == y))\n")
        src = (KIT / "templates" / "train.py").read_text()
        src = src.replace("    raise NotImplementedError", f'    return np.load("{self.root}/X.npy"), np.load("{self.root}/y1.npy"), None', 1)
        src = src.replace("    raise NotImplementedError", "    return X_va[:, 0]", 1)   # predicts the frozen truth exactly
        (self.comp / "code" / "train.py").write_text(src)
        rc, out = self.run_("python3", str(self.comp / "code" / "train.py"), "--id", "e1", "--parent", "e0", "--change", "relabel",
                            "--kind", "lever", "--mechanism", "m")
        self.assertEqual(rc, 0, out)
        row = (self.comp / "experiments.csv").read_text().splitlines()[-1].split(",")
        self.assertEqual((row[7], row[8]), ("1.000000", "1.000000"))    # vs load()'s labels: 0.900000 and 0.000000
        self.assertTrue(np.array_equal(np.load(self.comp / "data" / "oof_target.npy"), y0))

    def test_train_labels_from_oof_need_fold_safe_flag(self):   # RSNA e013/e014: OOF-blended labels inflated CV (LESSONS L2)
        import numpy as np
        n = 50
        np.save(self.comp / "data" / "folds.npy", np.arange(n) % 5)
        np.save(self.root / "X.npy", (np.arange(n) % 2)[:, None].astype(float))
        (self.comp / "score.py").write_text("import numpy as np\ndef score(y, p):\n    return float(np.mean((p > .5) == y))\n")
        src = (KIT / "templates" / "train.py").read_text().replace("LABELS_FROM_OOF = False", "LABELS_FROM_OOF = True")
        src = src.replace("    raise NotImplementedError", f'    X = np.load("{self.root}/X.npy"); return X, X[:, 0], None', 1)
        src = src.replace("    raise NotImplementedError", "    return X_va[:, 0]", 1)
        (self.comp / "code" / "train.py").write_text(src)
        run = lambda *f: self.run_("python3", str(self.comp / "code" / "train.py"), "--id", "e1", "--parent", "e0", "--change", "soft labels",
                                   "--kind", "lever", "--mechanism", "m", *f)
        rc, out = run()
        self.assertNotEqual(rc, 0, out)
        self.assertIn("teacher for fold k never saw fold k", out)
        self.assertFalse((self.comp / "oof" / "e1.npy").exists())
        rc, out = run("--labels-oof-fold-safe")
        self.assertEqual(rc, 0, out)
        self.assertTrue((self.comp / "oof" / "e1.npy").exists())

    def test_compare_identical_arms_no_warning(self):
        import numpy as np
        n = 50
        y = np.arange(n) % 2
        np.save(self.comp / "data" / "oof_target.npy", y)
        np.save(self.comp / "data" / "folds.npy", np.arange(n) % 5)
        (self.comp / "score.py").write_text("import numpy as np\ndef score(y, p):\n    return float(np.mean((p > .5) == y))\n")
        np.save(self.root / "a.npy", y + 0.1 * (np.arange(n) % 3))
        rc, out = self.run_("python3", "-W", "error", str(KIT / "compare.py"), str(self.comp), str(self.root / "a.npy"), str(self.root / "a.npy"))
        self.assertNotIn("Warning", out)
        self.assertIn("corrected t = 0.00", out)
        self.assertNotEqual(rc, 0, out)

    def test_train_from_oof_screen_records_its_folds(self):
        import numpy as np
        n = 50
        y, folds = np.arange(n) % 2, np.arange(n) % 5
        np.save(self.comp / "data" / "oof_target.npy", y)
        np.save(self.comp / "data" / "folds.npy", folds)
        (self.comp / "score.py").write_text("import numpy as np\ndef score(y, p):\n    return float(np.mean((p - y) ** 2))\n")
        (self.comp / "code" / "train.py").write_text((KIT / "templates" / "train.py").read_text())
        oof = np.full(n, np.nan)
        oof[folds == 2] = y[folds == 2]                               # a 1-fold Kaggle screen on fold 2
        np.save(self.root / "harvested.npy", oof)
        rc, out = self.run_("python3", str(self.comp / "code" / "train.py"), "--id", "s1", "--parent", "e1", "--change", "screen",
                            "--kind", "lever", "--mechanism", "m", "--from-oof", str(self.root / "harvested.npy"))
        self.assertEqual(rc, 0, out)
        row = (self.comp / "experiments.csv").read_text().splitlines()[-1].split(",")
        self.assertEqual((row[0], row[4], row[7]), ("s1", "1", "0.000000"))

    def test_train_from_oof_partly_filled_fold_refused(self):
        import numpy as np
        n = 50
        y, folds = np.arange(n) % 2, np.arange(n) % 5
        np.save(self.comp / "data" / "oof_target.npy", y)
        np.save(self.comp / "data" / "folds.npy", folds)
        (self.comp / "score.py").write_text("import numpy as np\ndef score(y, p):\n    return float(np.mean((p - y) ** 2))\n")
        (self.comp / "code" / "train.py").write_text((KIT / "templates" / "train.py").read_text())
        oof = np.full(n, np.nan)
        oof[folds <= 1] = y[folds <= 1]                               # folds 0 and 1 full
        oof[np.where(folds == 2)[0][:3]] = 0.5                        # fold 2 only partly
        np.save(self.root / "harvested.npy", oof)
        run = lambda: self.run_("python3", str(self.comp / "code" / "train.py"), "--id", "s2", "--parent", "e1", "--change", "screen",
                                "--kind", "lever", "--mechanism", "m", "--from-oof", str(self.root / "harvested.npy"))
        rc, out = run()
        self.assertEqual(rc, 2, out)
        self.assertIn("fills fold(s) [2] only partly", out)
        self.assertFalse((self.comp / "oof" / "s2.npy").exists())    # the id is not used up
        oof[folds == 2] = np.nan
        np.save(self.root / "harvested.npy", oof)
        rc, out = run()
        self.assertEqual(rc, 0, out)
        row = (self.comp / "experiments.csv").read_text().splitlines()[-1].split(",")
        self.assertEqual((row[0], row[4]), ("s2", "2"))

    def test_compare_multiclass_screen_and_bad_noise(self):
        import numpy as np
        n = 60
        y = np.arange(n) % 3
        folds = np.arange(n) % 5
        np.save(self.comp / "data" / "oof_target.npy", y)
        np.save(self.comp / "data" / "folds.npy", folds)
        (self.comp / "score.py").write_text("import numpy as np\ndef score(y, p):\n    return float(np.mean(p.argmax(1) == y))\n")
        a, b = np.full((n, 3), np.nan), np.full((n, 3), np.nan)
        m = folds == 0                                         # a 1-fold screen: NaN outside fold 0
        a[m] = np.eye(3)[(y[m] + 1) % 3]                       # always wrong
        b[m] = np.eye(3)[y[m]]                                 # always right
        np.save(self.root / "a.npy", a)
        np.save(self.root / "b.npy", b)
        cmp = lambda *x: self.run_("python3", str(KIT / "compare.py"), str(self.comp), str(self.root / "a.npy"), str(self.root / "b.npy"), *x)
        rc, out = cmp("--seed-noise", "0.05")
        self.assertEqual(rc, 0, out)
        self.assertIn("SCREEN READ", out)
        self.assertIn("compared 12 of 60 rows (NaN in A or B)", out)
        self.assertNotEqual(cmp("--seed-noise", "0")[0], 0)
        self.assertNotEqual(cmp()[0], 0)                       # a screen without σΔ is never read

    def test_compare_three_fold_screen_needs_seed_noise(self):   # 1 < k < 5: a screen, never READABLE (law 4, kept=P)
        import numpy as np
        n = 100
        y, folds = np.arange(n) % 2, np.arange(n) % 5
        np.save(self.comp / "data" / "oof_target.npy", y)
        np.save(self.comp / "data" / "folds.npy", folds)
        (self.comp / "score.py").write_text("import numpy as np\ndef score(y, p):\n    return float(np.mean((p > .5) == y))\n")
        a, b = np.full(n, np.nan), np.full(n, np.nan)
        m = folds < 3
        b[m] = y[m]                                            # always right on folds 0-2
        a[m] = np.where(np.arange(n)[m] % 10 < 5, 1 - y[m], y[m])   # half wrong: every fold Δ = +0.5
        np.save(self.root / "a.npy", a)
        np.save(self.root / "b.npy", b)
        cmp = lambda *x: self.run_("python3", str(KIT / "compare.py"), str(self.comp), str(self.root / "a.npy"), str(self.root / "b.npy"), *x)
        rc, out = cmp()
        self.assertEqual(rc, 1, out)
        self.assertIn("NOT READ", out)
        self.assertIn("3 folds need --seed-noise", out)
        rc, out = cmp("--seed-noise", "0.1")
        self.assertEqual(rc, 0, out)
        self.assertIn("SCREEN READ (3 folds): rank only; keep only as kept=P (budget mode, law 4)", out)
        self.assertNotIn("READABLE", out)
        rc, out = cmp("--seed-noise", "0.3")                   # Δ 0.5 < 2 σΔ on every fold
        self.assertEqual(rc, 1, out)
        self.assertIn("a fold Δ < 2 σΔ", out)

    def test_compare_screens_on_different_folds(self):
        import numpy as np
        n = 50
        y, folds = np.arange(n) % 2, np.arange(n) % 5
        np.save(self.comp / "data" / "oof_target.npy", y)
        np.save(self.comp / "data" / "folds.npy", folds)
        (self.comp / "score.py").write_text("import numpy as np\ndef score(y, p):\n    return float(np.mean((p > .5) == y))\n")
        a, b = np.full(n, np.nan), np.full(n, np.nan)
        a[folds == 0], b[folds == 1] = y[folds == 0], y[folds == 1]      # 1-fold screens on folds 0 and 1
        np.save(self.root / "a.npy", a)
        np.save(self.root / "b.npy", b)
        rc, out = self.run_("python3", str(KIT / "compare.py"), str(self.comp), str(self.root / "a.npy"), str(self.root / "b.npy"), "--seed-noise", "0.05")
        self.assertNotEqual(rc, 0, out)
        self.assertIn("A and B share no scored rows (screens on different folds?)", out)

    def test_compare_pooled_negative_not_read(self):
        import numpy as np
        r, n = np.random.default_rng(0), 5000
        y, folds = r.integers(0, 2, n), np.arange(n) % 5
        a, b = y + r.normal(0, 1.5, n), y + r.normal(0, 1.4, n)
        b[folds == 2] *= 100                                   # scale shift in one fold: every fold Δ > 0, pooled AUC Δ < 0
        np.save(self.comp / "data" / "oof_target.npy", y)
        np.save(self.comp / "data" / "folds.npy", folds)
        (self.comp / "score.py").write_text("import numpy as np\ndef score(y, p):\n    r = p.argsort().argsort() + 1\n"
                                            "    n1 = y.sum(); return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * (len(y) - n1)))\n")
        np.save(self.root / "a.npy", a)
        np.save(self.root / "b.npy", b)
        rc, out = self.run_("python3", str(KIT / "compare.py"), str(self.comp), str(self.root / "a.npy"), str(self.root / "b.npy"))
        self.assertIn("worst fold +", out)
        self.assertIn("pooled Δ -", out)
        self.assertNotEqual(rc, 0, out)
        self.assertIn("NOT READ", out)

    def test_push_treats_machine_shape_as_gpu(self):
        k = self.kernel_dir()
        (k / "kernel-metadata.json").write_text('{"id": "me/k1", "code_file": "k.py", "machine_shape": "NvidiaTeslaT4"}')
        rc, out = self.run_("bash", str(KIT / "push_and_watch.sh"), str(k))
        self.assertEqual(rc, 6, out)
        self.assertIn("plan older than 24 h", out)

    def test_daily_cap_and_duplicate(self):
        import datetime as dt
        d = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
        subs = f"ref,date,description\\n1,{d} 01:00:00,a | x\\n2,{d} 02:00:00,b | y"
        f = self.root / "s.csv"; f.write_text("id,target\n1,0.5\n")
        rc, out = self.run_("python3", str(KIT / "submit_gate.py"), "--file", str(f), "--competition", "demo-ref", "--desc", "t",
                            "--probe", "test", "--dry-run", FAKE_SUBS=subs)
        self.assertNotEqual(rc, 0)
        self.assertIn("cap is 2 per day", out)
        rc, out = self.run_("python3", str(KIT / "submit_gate.py"), "--file", str(f), "--competition", "demo-ref", "--desc", "a",
                            "--probe", "test", "--dry-run", FAKE_SUBS=f"ref,date,description\\n1,{d} 01:00:00,a | x")
        self.assertIn("DUPLICATE", out)

    def test_push_fails_on_dropped_source(self):   # TOOLING T10: invalid sources are dropped, the push still prints success
        k, plan = self.kernel_dir(), self.comp / "plans" / "k1.md"
        plan.write_text("kind: base\n")
        self.sign(plan)
        rc, out = self.push(k, FAKE_PUSH_EXTRA="The following are not valid dataset sources and could not be added to the kernel: ['me/x']")
        self.assertEqual(rc, 1, out)
        self.assertFalse((self.comp / "kernels.txt").exists())

    def test_push_warns_competition_kernel_with_internet(self):   # TOOLING T18: the CLI defaults enable_internet to true
        k, plan = self.kernel_dir(), self.comp / "plans" / "k1.md"
        plan.write_text("kind: base\n")
        self.sign(plan)
        warn = "WARN: competition_sources set and enable_internet not false (TOOLING T18)"
        for net, warned in (("", True), (', "enable_internet": true', True), (', "enable_internet": false', False)):
            (k / "kernel-metadata.json").write_text('{"id": "me/k1", "code_file": "k.py", "enable_gpu": "true", "competition_sources": ["c"]%s}' % net)
            rc, out = self.push(k)
            self.assertEqual(rc, 0, out)
            self.assertEqual(warn in out, warned, out)

    def test_push_validates_machine_shape(self):
        k = self.kernel_dir()
        for shape in ("NvidiaTeslaP100", "GpuT4"):
            (k / "kernel-metadata.json").write_text('{"id": "me/k1", "code_file": "k.py", "machine_shape": "%s"}' % shape)
            rc, out = self.run_("bash", str(KIT / "push_and_watch.sh"), str(k))
            self.assertEqual(rc, 2, out)
            self.assertIn("machine_shape", out)
        rc, out = self.run_("bash", str(KIT / "push_and_watch.sh"), str(self.kernel_dir()), "--accelerator", "NvidiaTeslaP100")
        self.assertEqual(rc, 2, out)                                      # P100 (sm_60) is off the allow-list (TOOLING T8)
        self.assertIn("--accelerator NvidiaTeslaP100", out)

    def test_push_refuses_public_kernel(self):
        k, plan = self.kernel_dir(), self.comp / "plans" / "k1.md"
        plan.write_text("kind: base\n")
        self.sign(plan)
        (k / "kernel-metadata.json").write_text('{"id": "me/k1", "code_file": "k.py", "enable_gpu": "true", "is_private": false}')
        rc, out = self.push(k)
        self.assertEqual(rc, 2, out)
        self.assertIn("is_private", out)

    def test_preflight_recursive_glob(self):
        import sys
        sys.path.insert(0, str(KIT))
        from preflight import preflight
        (self.root / "a" / "b").mkdir(parents=True)
        (self.root / "a" / "b" / "train.csv").write_text("x\n")
        preflight(paths=(f"{self.root}/**/train.csv",))                  # two levels down: needs recursive=True
        with self.assertRaises(SystemExit):
            preflight(paths=(f"{self.root}/**/test.csv",))

    def test_graphs_from_experiments(self):
        with open(self.comp / "experiments.csv", "a") as fh:
            fh.write("e1,2026-01-01,base,base,5,,m0,0.80,0.7,0.79,1,Y,\ne2,2026-01-02,lr,lever,5,e1,m1,0.81,0.7,0.80,1,Y,\n"
                     "e3,2026-01-03,aug,lever,1,e2,m2,0.805,,,1,N,\ne4,2026-01-04,pl,pseudo,5,e2,m3,0.83,0.72,0.815,2, yes,\n"
                     "e5,2026-01-05,ema,lever,5.0,e4,m4,0.835,0.72,0.82,1,N,\ne6,2026-01-06,nan,lever,5,e5,m5,nan,,nan,1,N,\n")   # 5.0: folds written as a float; e6: a NaN 5-fold row
        (self.comp / ".goldcut").write_text("0.84\n")
        rc, out = self.run_("python3", str(KIT / "graphs.py"), str(self.comp))
        self.assertEqual(rc, 0, out)
        self.assertIn("(5 runs, 3 kept)", out)   # ' yes' counts as kept
        self.assertIn("(4 five-fold subs)", out)                      # e6 (NaN) is left out, so the fit line is still drawn
        for f in ("progress.png", "lineage.png", "cv_vs_lb.png"):
            self.assertGreater((self.comp / "graphs" / f).stat().st_size, 5000, f)

    def test_graphs_empty_no_warning(self):
        rc, out = self.run_("python3", "-W", "error", str(KIT / "graphs.py"), str(self.comp))   # header only: no legend warning
        self.assertEqual(rc, 0, out)
        self.assertIn("(0 runs, 0 kept)", out)

    def test_fanout_estimate_resume_summary(self):
        import csv
        j = self.root / "job"
        j.mkdir()
        (j / "manifest.csv").write_text("id,path\na,x/a.png\nb,x/b.png\nc,x/c.png\n")
        (j / "brief.md").write_text("Read {path}.\nOutput: {jobdir}/{id}.md\n")
        fan = lambda *a, **e: self.run_("python3", str(KIT / "fanout.py"), str(j), *a, **e)
        rc, out = fan("--go")
        self.assertNotEqual(rc, 0)
        self.assertIn("coding-discipline", out)                               # R14 holds for batch briefs too
        (j / "brief.md").write_text("No silent assumptions. Simplicity first. Surgical changes. Explicit verification.\n"
                                    "job: {id}\nRead {path}; keep {braces}.\nOutput: {jobdir}/{id}.md, ≤ 1 page\n")
        rc, out = fan()
        self.assertEqual(rc, 0, out)
        self.assertIn("3 of 3 jobs pending · model opus · estimate 0.9M", out)
        self.assertFalse(list((j / "out").iterdir()))                          # estimate only: nothing ran
        log = self.root / "calls"
        rc, out = fan("--go", "-j", "2", FAKE_CLAUDE_FAIL="b", FAKE_CLAUDE_LOG=str(log))
        self.assertEqual(rc, 1, out)
        st = {r["id"]: r for r in csv.DictReader((j / "summary.csv").read_text().splitlines())}
        self.assertEqual([st[i]["status"] for i in "abc"], ["ok", "error", "ok"])
        self.assertEqual(st["a"]["result"], "read a")
        rc, out = fan("--go", FAKE_CLAUDE_LOG=str(log))                        # resume: only the failed job runs again
        self.assertEqual(rc, 0, out)
        self.assertEqual(sorted(log.read_text().split()), ["a", "b", "b", "c"])
        self.assertIn("3 ok, 0 not ok · $1.50", out)
        (j / "out" / "a.json").unlink()
        rc, out = fan("--go", "--", "--x", "y", FAKE_CLAUDE_ARGS=str(self.root / "args"))   # args after -- reach claude
        self.assertEqual(rc, 0, out)
        self.assertEqual((self.root / "args").read_text(), "-p --output-format json --model opus --x y\n")

    # harvest -----------------------------------------------------------------
    def test_harvest_counts_only_harvest_lines(self):
        (self.comp / "code" / "k1").mkdir()
        (self.comp / "code" / "k1" / "kernel-metadata.json").write_text('{"id": "me/k1"}')   # a mention, not a harvest
        self.events("PUSH me/k1 v3")
        check = lambda: self.run_("bash", str(KIT / "harvest_check.sh"), str(self.comp), "k1")
        self.assertIn("2 UNHARVESTED", check()[1])
        rc, out = self.run_("bash", str(KIT / "harvest.sh"), "me/k1")
        self.assertEqual(rc, 0, out)
        self.assertTrue((self.comp / "runs" / "k1" / "v3" / "out.csv").exists())
        self.assertIn("1 UNHARVESTED", check()[1])          # k10 is still unread
        self.events("PUSH me/k1 v4")                        # a new version is unread again
        self.assertIn("2 UNHARVESTED", check()[1])

    def test_harvest_error_kernel_tagged_other_states_refused(self):
        self.events("PUSH me/k1 v5")
        rc, out = self.run_("bash", str(KIT / "harvest.sh"), "me/k1", FAKE_STATUS="RUNNING")
        self.assertEqual(rc, 1, out)
        self.assertIn("REFUSING: me/k1 is not COMPLETE or ERROR", out)
        rc, out = self.run_("bash", str(KIT / "harvest.sh"), "me/k1", FAKE_STATUS="ERROR")
        self.assertEqual(rc, 0, out)
        self.assertTrue((self.comp / "runs" / "k1" / "v5" / "k1.log").exists())   # the crash log is pulled
        self.assertRegex((self.comp / "events.log").read_text(), r"HARVEST me/k1 v5 \(error\)\n")


if __name__ == "__main__":
    unittest.main()
