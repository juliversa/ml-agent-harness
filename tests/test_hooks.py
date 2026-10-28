"""Offline tests of the hooks (kit/hooks, wired in kit/settings.example.json). Fixture: tests/base.py."""
import os, tempfile, unittest
from pathlib import Path

from base import KIT, Kit


class Hooks(Kit):
    def test_guard_blocks_ungated_kaggle_and_deletes(self):
        for cmd in ("kaggle competitions submit -c x -f a.csv -m hi", "kaggle kernels push -p k",
                    "echo push_and_watch.sh; kaggle kernels push -p k", "rm -rf competitions/demo/runs",
                    "rm -r -f ./competitions/demo", "kaggle k push -p .", "kaggle kernels update -p .",
                    "kaggle c submit x -f a.csv -m m", "python3 -c 'from kaggle.api.kaggle_api_extended import KaggleApi as K; K().competition_submit(1)'",
                    "~/.local/bin/kaggle k push -p .", "cd x && kaggle c submit y", "git clean -fdx",
                    "git -C /repo clean -fdx", "git -C /repo reset --hard", "git -C /repo rm -r competitions/x",
                    "/bin/rm -rf /repo/competitions/x", 
                    f"rm -rf {KIT.parent}", f"rm -rf {KIT.parent}/notes", f"rm -rf '{KIT.parent}/data/x'", "rm -rf \".\"",
                    "python3 - <<'PY'\nKaggleApi().competition_submit_code(1)\nPY", "FOO=1 kaggle kernels push -p .",
                    "bash -c \"kaggle kernels push -p .\"", "eval \"kaggle kernels push\"", "eval kaggle k push", "command kaggle kernels push -p .", "git -C /repo checkout .", "rm -rf competitions/x __pycache__", "git reset --hard  # clears __pycache__",
                    "rm --recursive --force competitions/x", "rm -v -rf competitions/x", "git checkout -f main", "git switch -f main", "git checkout --force main", "git switch --force main","cd /repo && rm -rf *", "rm -rf .", 
                    "git -C /repo checkout -- .", "git -C /repo restore .", "git -C /repo stash", "git push --force origin main", "git branch -D old", "git -C /repo branch --delete --force old",
                    "python3 -m kaggle kernels push -p .", "rm -rf ./competitions", "find competitions -name '*.csv' -delete",
                    "ls competitions/x\nrm -rf competitions/x/runs", "# push it\nkaggle kernels push -p k", "git status\n  git reset --hard",
                    "find competitions/x -name '*.tmp' -exec rm -f {} +", "git push origin main \\\n  --force", "cat <<EOF | bash\nkaggle kernels push -p k\nEOF",
                    "cat notes.md; bash <<'EOF'\nkaggle kernels push -p k\nEOF",
                    "kaggle datasets create -p d --public", "kaggle datasets delete me/x", "kaggle k delete me/k", "kaggle models instances delete me/m/pt/v", "kaggle models instances versions delete me/m/pt/v/1", "gh repo delete me/r --yes", "kaggle d create -p d -u", "gh repo create x --public",
                    "gh repo edit me/x --visibility public", "cd /repo && ls", "ls; cd kit && bash x.sh",
                    "python3 -c 'import subprocess; subprocess.run([\"kaggle\", \"kernels\", \"push\", \"-p\", \".\"])'",
                    "python3 - <<'PY'\nimport subprocess as s\ns.run(['kaggle','competitions','submit','x','-f','a.csv'])\nPY",
                    "rm -rf kit", "rm -rf skills/ LESSONS.md", "rm competitions/x/experiments.csv", "rm -f LESSONS.md", "rm -rf *",
                    "find . -name '*.csv' -delete", "find kit -delete", "rm -rf ~", "ls | xargs rm -rf", "find competitions -name \"*.ckpt\" -print0 | xargs -0 rm -f", "ls | xargs -n1 rm -r",
                    "echo k | xargs -I{} kaggle kernels push -p {}", "rm -rf \"$D\"",
                    f"rm -rf {KIT.parent.parent}", f"rm {KIT.parent}/competitions/x/notes.md", "rm -rf /tmp/x competitions",
                    "git --no-pager reset --hard", "git -c k=v reset --hard", "git restore --staged --worktree f", "git restore -SW f",
                    "git reset HEAD --hard", "git push origin +main",
                    "{ kaggle kernels push -p k; }", "! kaggle competitions submit -c x", "echo `kaggle kernels push -p k`",
                    "nice kaggle kernels push -p k", "stdbuf -oL kaggle kernels push -p k", "true && { rm -rf competitions; }",
                    "git commit -m 'doc; kaggle kernels push is gated'", "kaggle 'kernels' push -p x", "\"kaggle\" kernels push -p x",
                    "kaggle c 'submit' x -f a.csv"):   # documented limit: `-m` text with ; or | can be blocked
            self.assertEqual(self.hook("guard_command.py", {"tool_input": {"command": cmd}})[0], 2, cmd)
        for cmd in ("bash kit/push_and_watch.sh k --accelerator NvidiaTeslaT4", "kaggle kernels status me/k1",
                    "python3 kit/submit_gate.py --file a.csv --competition x --desc d --probe p", "rm /tmp/x.txt",
                    "grep -rn 'kaggle kernels push' TOOLING.md", "git commit -m 'doc: never kaggle competitions submit directly'",
                    "rm -f /tmp/setup.log", "rm -rf /tmp/pip-setup-abc", "rm -f /tmp/work/memory.csv",
                    "git -C /repo rm --cached -r big/", "git -C /repo stash list", "git -C /repo push origin main",
                    "git -C /repo status", "git -C /repo diff", "rm -rf /tmp/scratch/out", "rm -rf /tmp/build/setup/",
                    "git -C /repo restore --staged x", "git branch -d merged", "git branch --delete merged", f"rm -rf {KIT.parent}/kit/__pycache__", "git checkout main", "find kit -name __pycache__ -exec rm -rf {} +", "git checkout main && tail -f competitions/x/train.log", "git push origin main && ls -f",
                    "git checkout main\ntail -f competitions/x/train.log", "grep -rn competition_submit kit/ | python3 -c 'import sys; print(1)'",
                    "git commit -m \"$(cat <<'EOF'\nsubmit_gate\n\n- CLI 400 -> python3 API\n- competition_submit_code fallback\nEOF\n)\"",
                    "rm -f /tmp/out.csv\ntail competitions/x/events.log", "git commit -m \"$(cat <<'EOF'\nguard\n\ngit reset --hard is blocked\nEOF\n)\"",
                    "cat > competitions/x/plans/k1.md <<'EOF'\nkind: base\nkaggle kernels push -p competitions/x/code/k1\nEOF",
                    "kaggle datasets create -p d", "gh repo create x --private", "git commit -m 'R37: never cd X && y'", "cd /repo",
                    "rm notes.txt", "rm -rf /tmp/scratch/l3", "find /tmp/x -name '*.tmp' -delete", "rm -rf ~/scratch/x",
                    "rm -rf /tmp/x 2>/dev/null", "rm -f /tmp/a.csv /tmp/b.csv", "git clean -nfd", "git clean -fd -n", "git --no-pager log",
                    "git push origin main", "git reset --soft HEAD~1", "ls *.py | xargs -n1 wc -l", "git commit -m \"a +b\""):
            self.assertEqual(self.hook("guard_command.py", {"tool_input": {"command": cmd}})[0], 0, cmd)

    def test_guard_globs_over_repo_parents_and_gh_api_public(self):
        repo = KIT.parent
        for cmd in ("rm -rf /*", f"rm -rf {repo.parent}/*", f"rm -rf {repo}/*", "rm -rf ~/*", "sudo rm -rf /w*", f"rm -rf {repo.parent}/?s*",
                    "gh api -X PATCH repos/me/x -f private=false", "gh api repos/me/x -X PATCH -F visibility=public",
                    "gh api repos/me/x --field 'private=false'"):
            self.assertEqual(self.hook("guard_command.py", {"tool_input": {"command": cmd}})[0], 2, cmd)
        for cmd in ("rm -rf /tmp/x/*", "rm -f /tmp/x/*.csv", "rm -rf /tmp/scratch/l?", "gh api repos/me/x", "gh api -X PATCH repos/me/x -f private=true",
                    "git commit -m 'guard: gh api private=false is blocked'"):
            self.assertEqual(self.hook("guard_command.py", {"tool_input": {"command": cmd}})[0], 0, cmd)

    def test_brief_hook_needs_coding_discipline(self):
        rules = (KIT.parent / "skills" / "coding-discipline" / "SKILL.md").read_text().split("---")[-1]
        self.assertEqual(self.hook("check_brief.py", {"tool_input": {"prompt": "Find the bug in train.py"}})[0], 2)
        self.assertEqual(self.hook("check_brief.py", {"tool_input": {"prompt": rules + "\nGoal: find the bug"}})[0], 2)   # no Output line
        self.assertEqual(self.hook("check_brief.py", {"tool_input": {"prompt": rules + "\nGoal: find the bug\nOutput: /tmp/x/bug.md, ≤ 1 page"}})[0], 0)

    def test_read_hook_keeps_big_files_out(self):
        big, small = self.root / "big.jsonl", self.root / "small.md"
        big.write_text("x" * 50000), small.write_text("ok\n")
        rd = lambda **ti: self.hook("check_read.py", {"tool_name": "Read", "tool_input": ti})[0]
        sh = lambda c: self.hook("check_read.py", {"tool_name": "Bash", "tool_input": {"command": c}})[0]
        self.assertEqual(rd(file_path=str(big)), 2)
        self.assertEqual(rd(file_path=str(big), offset=1, limit=50), 0)
        self.assertEqual(rd(file_path=str(big), limit=5000), 2)
        self.assertEqual(rd(file_path=str(big), limit=0), 2)
        self.assertEqual(rd(file_path=str(small)), 0)
        nb = self.root / "big.ipynb"
        nb.write_text("x" * 50000)
        rc, err = self.hook("check_read.py", {"tool_name": "Read", "tool_input": {"file_path": str(nb)}})
        self.assertEqual(rc, 2)
        self.assertIn("jq -r '.cells[].source[]'", err)
        for c in (f"cat {big}", f"tail -c 30000 {big}", f"ls; cat {small} {big}", f"head -n 5000 {big}", f"tail -n +2 {big}",
                  f"sed 's/a/b/' {big}", f"sed -n 1,5000p {big}", f"awk '{{print $1}}' {big}", f"less {big}", f"more {big}",
                  f"head -2000 {big}", f"head -n -1 {big}", f"tail -n+1 {big}", f"tail -n+5 {big}", f"head -c9000 {big}",
                  f"head -n5000 {big}", f"cat {big} | head -n 5000", f"grep x {big} | tail -n +2", f"{{ cat {big}; }}",
                  f"nl {big}", f"tac {big}", f"cut -c1-80 {big}", f"cut -d, -f1 {big}", f"awk 1 {big}", f"sed -n '1,999p;5000,9000p' {big}"):
            self.assertEqual(sh(c), 2, c)
        for c in (f"cat {big} | grep x", f"tail -n 20 {big}", f"cat {small}", f"cat {big} > /tmp/copy", f"grep -c x {big}",
                  f"head -n 1000 {big}", f"sed -n '10,60p' {big}", f"sed -i 's/a/b/' {big}", f"awk 'NR<=50' {big}",
                  f"sed 's/a/b/' {big} | head -n 5", f"sed 's/a/b/' {small}", f"head -20 {big}", f"tail -n -5 {big}",
                  f"head -c500 {big}", f"cat {big} | head -n 1000", f"cat {small} | head -n 5000", f"nl {small}", f"cut -d, -f1 {big} | head -n 5",
                  f"awk 'NR<=50' {big} | head -n 5", f"sed -n '1,9p;20,30p' {small}", f"grep 'x;y' {big}", f"grep -c 'a&&b' {big}"):
            self.assertEqual(sh(c), 0, c)
        rc, err = self.hook("check_read.py", {"tool_name": "Read", "tool_input": {"file_path": str(big)}})
        self.assertIn("Read a part (limit <= 1000 lines, any offset)", err)

    def test_context_hook_asks_for_handoff_once_per_step(self):
        import json
        tp = self.root / "t.jsonl"
        msg = lambda n, side=False: json.dumps({"isSidechain": side, "message": {"usage": {"input_tokens": 1, "cache_read_input_tokens": n}}})
        tp.write_text(msg(90000) + "\n" + msg(400000, side=True) + "\n")       # a sub-agent's big context is not the lead's
        call = lambda: self.hook("check_context.py", {"transcript_path": str(tp), "session_id": f"test-{os.getpid()}"})[0]
        self.assertEqual(call(), 0)
        with open(tp, "a") as fh:
            fh.write(msg(160000) + "\n")
        try:
            self.assertEqual(call(), 2)
            self.assertEqual(call(), 0)                          # asked once at this size
        finally:
            Path(tempfile.gettempdir(), f"ctx-alert-test-{os.getpid()}").unlink(missing_ok=True)

    def test_python_hook_catches_bad_code(self):
        (self.comp / "STATE.md").write_text("")
        p = self.comp / "code" / "t.py"
        p.write_text("def f():\n    return undefined_name\n")
        rc, err = self.hook("check_python.py", {"tool_input": {"file_path": str(p)}})
        self.assertEqual(rc, 2)
        self.assertIn("undefined_name", err)
        p.write_text("import os\ndef f():\n    return os.sep\n")
        self.assertEqual(self.hook("check_python.py", {"tool_input": {"file_path": str(p)}})[0], 0)

    def test_stop_hook_until_tier1_acked(self):
        import datetime as dt
        (self.comp / "STATE.md").write_text("# state\n")
        (self.comp / ".tokens_today").write_text("0\n")                                  # a live watcher's heartbeat
        now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
        with open(self.comp / "events.log", "a") as fh:
            fh.write(f"{now} ALERT [k-me_k1-complete] kernel me/k1 complete\n{now} ALERT [budget] token budget: 31M\n{now} PUSH me/k1 v8\n")
        rc, err = self.hook("check_stop.py", {})
        self.assertEqual(rc, 2)
        self.assertIn("demo (2)", err)
        self.assertIn("COMP_SLUG=demo bash kit/ack.sh", err)
        self.assertEqual(self.hook("check_stop.py", {"stop_hook_active": True})[0], 0)   # never loops
        ack = lambda *a: self.run_("bash", str(KIT / "ack.sh"), *a)
        self.assertEqual(ack("buget", "typo")[0], 1)                                      # no such alert: nothing written
        self.assertEqual(ack("k-*", "  ")[0], 2)                                          # a blank reason acks nothing
        self.assertEqual(ack("k-*", "e12")[0], 0)
        rc, err = self.hook("check_stop.py", {})
        self.assertEqual(rc, 2)
        self.assertNotIn("kernel me/k1", err)
        self.assertEqual(ack("budget", "planned", "pseudo-label run")[0], 0)
        self.assertEqual(self.hook("check_stop.py", {})[0], 0)
        self.assertIn("OPEN ALERTS: 0", self.run_("bash", str(KIT / "status.sh"), "demo")[1])   # status.sh agrees with the hook
        later = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%MZ")
        with open(self.comp / "events.log", "a") as fh:                                   # a repeat after the ack needs a new ack
            fh.write(f"{later} ALERT [budget] token budget: 35M\n")
        self.assertEqual(self.hook("check_stop.py", {})[0], 2)
        self.assertIn("OPEN ALERTS: 1", self.run_("bash", str(KIT / "status.sh"), "demo")[1])

    def test_repeat_in_the_same_minute_needs_a_new_ack(self):   # events and acks carry seconds (review 2026-10-28)
        import datetime as dt
        (self.comp / "STATE.md").write_text("# state\n")
        (self.comp / ".tokens_today").write_text("0\n")
        t0 = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        with open(self.comp / "events.log", "a") as fh:
            fh.write(f"{t0:%Y-%m-%dT%H:%M:%SZ} ALERT [k-me_k1-complete] kernel me/k1 complete\n")
        self.assertEqual(self.run_("bash", str(KIT / "ack.sh"), "k-*", "e12")[0], 0)
        with open(self.comp / "events.log", "a") as fh:
            fh.write(f"{t0 + dt.timedelta(seconds=1):%Y-%m-%dT%H:%M:%SZ} ALERT [k-me_k1-complete] kernel me/k1 complete\n")
        acks = (self.comp / "acks.txt").read_text().splitlines()[-1].split()[0]
        if acks >= f"{t0 + dt.timedelta(seconds=1):%Y-%m-%dT%H:%M:%SZ}":
            self.skipTest("ack landed after the repeat's stamp")
        self.assertEqual(self.hook("check_stop.py", {})[0], 2)
        self.assertIn("OPEN ALERTS: 1", self.run_("bash", str(KIT / "status.sh"), "demo")[1])

    def test_stop_hook_dead_watcher_and_old_alert(self):
        import datetime as dt
        (self.comp / "STATE.md").write_text("# state\n")
        hb = self.comp / ".tokens_today"
        hb.write_text("0\n")
        os.utime(hb, (0, dt.datetime.now().timestamp() - 20 * 60))                     # last pass 20 min ago
        rc, err = self.hook("check_stop.py", {})
        self.assertEqual(rc, 2)
        self.assertIn("demo: heartbeat .tokens_today 20 min old", err)
        self.assertIn("nohup bash", err)
        import fnmatch, json, re                                                         # both printed restarts pass an allow rule
        allow = [p[5:-1].replace(":*", "*") for p in json.loads((KIT / "settings.example.json").read_text())["permissions"]["allow"]]
        status = self.run_("bash", str(KIT / "status.sh"), "demo")[1]
        for text in (err, status):
            cmd = re.search(r"restart: (.*&)", text).group(1)
            self.assertTrue(any(fnmatch.fnmatchcase(cmd, p) for p in allow), cmd)
        self.assertEqual(self.hook("check_stop.py", {"stop_hook_active": True})[0], 0)  # blocks once
        (self.comp / ".deadline").write_text("2000-01-01\n")                              # past the deadline the watcher exits
        self.assertEqual(self.hook("check_stop.py", {})[0], 0)
        (self.comp / ".deadline").unlink()
        hb.write_text("0\n")
        with open(self.comp / "events.log", "w") as fh:                                   # an old unacked alert, then 600 other lines
            fh.write("2026-01-01T00:00Z ALERT [k-me_k1-error] kernel me/k1 error\n" + "2026-01-01T00:01Z KERNEL me/k2 running\n" * 600)
        rc, err = self.hook("check_stop.py", {})
        self.assertEqual(rc, 2)
        self.assertIn("kernel me/k1 error", err)


if __name__ == "__main__":
    unittest.main()
