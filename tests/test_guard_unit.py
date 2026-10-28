"""Direct tests of kit/hooks/guard_command.check(): the block message, or None when allowed."""
import importlib.util, unittest

from base import KIT

spec = importlib.util.spec_from_file_location("guard_command", KIT / "hooks" / "guard_command.py")
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class GuardCheck(unittest.TestCase):
    def test_allowed(self):
        self.assertIsNone(guard.check("git -C /repo status"))

    def test_gated_push(self):
        self.assertEqual(guard.check("kaggle kernels push -p k"),
                         "BLOCKED: `kaggle kernels push` goes through the gate: bash kit/push_and_watch.sh (push) "
                         "or python3 kit/submit_gate.py (submit). See skills kaggle-run, kaggle-submit.")

    def test_discard(self):
        self.assertEqual(guard.check("git reset --hard"), guard.DISCARD_MSG)

    def test_public(self):
        self.assertEqual(guard.check("gh repo create x --public"), guard.PUBLIC_MSG)

    def test_cd_and(self):
        self.assertEqual(guard.check("cd /repo && ls"), guard.CD_MSG)

    def test_review_bypasses_closed(self):   # found by a hostile review (2026-10-28); each was allowed before
        for cmd in (f"rm -rf {guard.REPO}/__pycache__/..", "rm -rf __pycache__/../..", "find . -name __pycache__ -o -type f -delete",
                    "git clean --force", '"rm" -rf kit', "\\rm -rf kit", "r''m -rf kit",
                    "bash -lc 'kaggle kernels push -p k'", "env -i kaggle kernels push -p k",
                    'python3 -c "import subprocess;subprocess.run([\\"kaggle\\",\\"competitions\\",\\"submit\\",\\"x\\"])"',
                    "git push --delete origin main", "git push origin :main", "gh api -X DELETE repos/x/y"):
            with self.subTest(cmd=cmd):
                self.assertIsNotNone(guard.check(cmd))

    def test_still_allowed(self):
        for cmd in ("rm -rf /tmp/x/__pycache__", "find /tmp/x -name __pycache__ -exec rm -rf {} +", "git clean -n",
                    "git push origin HEAD:main", 'python3 -c "print(1)"', "env FOO=1 python3 kit/compare.py"):
            with self.subTest(cmd=cmd):
                self.assertIsNone(guard.check(cmd))

    def test_confirm_round(self):   # second hostile review (2026-10-28)
        for cmd in (f"nice -n 5 rm -rf {guard.REPO}", f"sudo -u x rm -rf {guard.REPO}", f"ionice -c3 rm -rf {guard.REPO}",
                    "timeout -s KILL 5 kaggle kernels push -p k", "sudo -E kaggle competitions submit -f x", "timeout 60 kaggle k push"):
            with self.subTest(cmd=cmd):
                self.assertIsNotNone(guard.check(cmd))
        for cmd in ('rm -rf "/tmp/a b"', "time python3 x.py", "nice -n 5 python3 train.py", 'git commit -m "rm stale files"'):
            with self.subTest(cmd=cmd):
                self.assertIsNone(guard.check(cmd))
