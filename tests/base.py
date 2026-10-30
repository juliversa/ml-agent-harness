"""Shared fixture for the offline kit tests (stdlib + numpy): python3 -m unittest discover -s tests
A fake `kaggle` (tests/bin/kaggle) stands in for the CLI; every test runs in a temp competition root."""
import hashlib, os, subprocess, tempfile, time, unittest
from pathlib import Path

os.environ["TZ"] = "UTC"; time.tzset()   # the kit's day is UTC: a local date.today() is a day off east of UTC in the morning

KIT = Path(__file__).resolve().parent.parent / "kit"
BIN = Path(__file__).resolve().parent / "bin"


class Kit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.comp = self.root / "comps" / "demo"
        for d in ("plans", "data", "code"):
            (self.comp / d).mkdir(parents=True)
        (self.comp / ".kref").write_text("demo-ref\n")
        (self.comp / ".lower").write_text("")
        (self.comp / "experiments.csv").write_text("id,date,change,kind,folds,parent,mechanism,oof_mean,oof_hard,public,gpu_h,kept,note\n")
        (self.comp / "data" / "sample_submission.csv").write_text("id,target\n1,0.5\n2,0.1\n3,0.9\n")
        self.env = dict(os.environ, PATH=f"{BIN}:{os.environ['PATH']}", KAGGLE_USER="me",
                        COMP_ROOT=str(self.root / "comps"), COMP_SLUG="demo", PYTHONDONTWRITEBYTECODE="1",
                        CLAUDE_PROJECT_DIR=str(KIT.parent))

    def tearDown(self):
        self.tmp.cleanup()

    def run_(self, *cmd, **env):
        r = subprocess.run(cmd, capture_output=True, text=True, env={**self.env, **env}, timeout=120)
        return r.returncode, r.stdout + r.stderr

    def events(self, *lines):
        with open(self.comp / "events.log", "a") as fh:
            fh.writelines(f"2026-01-01T00:0{i}Z {l}\n" for i, l in enumerate(lines))

    def gate(self, *args):
        return self.run_("python3", str(KIT / "submit_gate.py"), "--competition", "demo-ref", "--desc", "t",
                         "--probe", "test", "--dry-run", *args)

    def kernel_dir(self):
        k = self.root / "kdir"
        k.mkdir(exist_ok=True)
        (k / "kernel-metadata.json").write_text('{"id": "me/k1", "code_file": "k.py", "enable_gpu": "true"}')
        (k / "k.py").write_text("print(1)\n")
        (self.comp / "plans" / "k1-batch.bin").write_bytes(os.urandom(2000))
        return k

    def push(self, k, **env):
        return self.run_("bash", str(KIT / "push_and_watch.sh"), str(k), "--accelerator", "NvidiaTeslaT4", **env)

    def sign(self, plan):
        h = hashlib.sha256("".join(l for l in plan.read_text().splitlines(True) if not l.startswith("Verdict:")).encode()).hexdigest()[:16]
        with open(plan, "a") as fh:
            fh.write(f"Verdict: GO sha256={h}\n")

    def watcher_pass(self, rows=None, findings_age_h=0):
        """Scaffold w1, make it day 8 with nine 5-fold subs (or `rows`), run one watcher pass from kit/. Returns (comp dir, events.log, digest.md)."""
        import datetime as dt, json, re
        rc, out = self.run_("bash", str(KIT / "setup-competition.sh"), "w1", "W One", "2099-01-01", "w1-ref")
        self.assertEqual(rc, 0, out)
        c = self.root / "comps" / "w1"
        pid = re.search(r"watcher PID (\d+)", out)
        if pid:
            subprocess.run(["kill", pid.group(1)], capture_output=True)            # the scaffold starts one; run our own pass
        subprocess.run(["flock", "-w", "20", str(c / ".lock"), "true"])          # its children may hold the lock a moment longer
        (c / ".entry").write_text((dt.date.today() - dt.timedelta(8)).isoformat() + "\n")
        today = dt.date.today().isoformat()
        rows = rows or [f"e{i},{today},c{i},lever,5,{'e1' if i > 1 else ''},m1,0.8{i},0.7,0.9{10 - i},1,Y," for i in range(1, 10)]
        (c / ".lbnoise").write_text("0.002\n")
        (c / "experiments.csv").write_text((c / "experiments.csv").read_text() + "\n".join(rows) + "\n")
        (c / "FINDINGS.md").write_text((c / "FINDINGS.md").read_text() + f"| f1 | {today} | close m9 | .80 | | closed |\n")
        if findings_age_h:                                                         # no new finding for that long
            os.utime(c / "FINDINGS.md", (os.path.getmtime(c / "FINDINGS.md") - 3600 * findings_age_h,) * 2)
        (self.root / "proj").mkdir()
        now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")       # the lead ran at 200k context all day
        (self.root / "proj" / "s.jsonl").write_text("".join(json.dumps({"timestamp": now, "message": {
            "id": f"m{i}", "usage": {"input_tokens": 1, "cache_read_input_tokens": 200000}}}) + "\n" for i in range(3)))
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)   # nothing committed; log.md last touched 3 h ago
        os.utime(c / "log.md", (os.path.getmtime(c / "log.md") - 10800,) * 2)
        (c / "acks.txt").write_text("2000-01-01T00:00Z none old ack\n")              # harness-written: never "uncommitted"
        os.utime(c / "acks.txt", (os.path.getmtime(c / "log.md"),) * 2)
        (c / "keeper.md").write_text("keeper: lead alive\n")                             # harness-written: never "uncommitted"
        os.utime(c / "keeper.md", (os.path.getmtime(c / "log.md"),) * 2)
        rc, out = self.run_("bash", str(KIT / "watcher.sh"), "w1", "--once", CLAUDE_PROJECTS=str(self.root / "proj"))
        self.assertEqual(rc, 0, out)
        return c, (c / "events.log").read_text(), (c / "digest.md").read_text()

    def hook(self, name, payload, **env):
        r = subprocess.run(["python3", str(KIT / "hooks" / name)], input=__import__("json").dumps(payload),
                           capture_output=True, text=True, env={**self.env, **env}, timeout=60)
        return r.returncode, r.stderr

    def keeper(self, lead_age_h, **env):
        """One keeper pass; the lead's last transcript was written lead_age_h hours ago. Returns (keeper.md lines, notes sent)."""
        import time
        lead, proj = self.root / "lead", self.root / "proj"
        tr = proj / str(lead).replace("/", "-").replace("_", "-").replace(".", "-") / "s.jsonl"
        tr.parent.mkdir(parents=True, exist_ok=True)
        lead.mkdir(exist_ok=True)
        tr.write_text("{}\n")
        os.utime(tr, (0, time.time() - lead_age_h * 3600))
        notes = self.root / "notes"
        rc, out = self.run_("python3", str(KIT / "keeper.py"), **{"LEAD_DIR": str(lead), "CLAUDE_PROJECTS": str(proj),
                            "CLAUDE_BIN": str(BIN / "claude"), "FAKE_CLAUDE_ARGS": str(self.root / "args"), "NTFY_TOPIC": "t",
                            "NTFY_URL": "http://stub", "FAKE_CURL_LOG": str(notes), "OWNER_TZ": self.tz(3), **env})
        self.assertEqual(rc, 0, out)
        read = lambda f: f.read_text().splitlines() if f.exists() else []
        return read(self.comp / "keeper.md"), read(notes)

    def tz(self, h):                                                                       # a POSIX zone where the owner's clock reads h:xx
        import time
        return f"KPR{time.gmtime().tm_hour - h:+d}"

    def keeper_comp(self):
        (self.comp / "STATE.md").write_text("# state\n")
        (self.comp / ".tokens_today").write_text("1000000\n")                         # a live watcher
        self.events("ALERT [k-me_k1-error] kernel me/k1 error")                         # unacked tier 1, 2026: quiet for 24 h
