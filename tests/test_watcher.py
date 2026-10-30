"""Offline tests of the watcher, status, agentmeter and keeper. Fixture: tests/base.py."""
import os, unittest

from base import KIT, Kit


class Watcher(Kit):
    def test_watcher_alerts(self):
        c, ev, dg = self.watcher_pass(findings_age_h=80)                          # 80 h without a new finding
        for f in ("STATE.md", "STATUS.md", "NOW.md", "WEEK0.md", "FINDINGS.md", "experiments.csv", "log.md", ".kref", ".lbnoise"):
            self.assertTrue((c / f).exists(), f)
        self.assertFalse((c / "watcher.sh").exists(), "the kit runs in place: no per-competition copy")
        for key in ("ALERT [uncommitted] uncommitted: 2 files", "ALERT [csvbad-2] csvbad: experiments.csv line 2: parent is empty",
                    "] step-back overdue", "ALERT [noerr-e9-", "] noerr: rows e1 e2 e3 e4 e5 e6 e7 e8 e9 have oof_mean",
                    "] ruler: CV vs public over 9 subs: slope -"):
            self.assertIn(key, ev, key)                                            # tier 1
        for key in ("[context] context: median main-session context today 200k",):
            self.assertIn(key, dg, key)                                            # tier 2
            self.assertNotIn(key, ev, key)
        st = (c / "STATUS.md").read_text()
        self.assertLessEqual(len(st.splitlines()), 20)
        for key in ("NOW: day 0", "OPEN ALERTS: 5", "context p50 200k", "BEST: CV 0.89 (e9)", "nohup bash kit/watcher.sh w1"):
            self.assertIn(key, st, key)

    def test_step_back_every_72h_sooner_when_stalled(self):
        import time
        c, ev, _ = self.watcher_pass()                                             # entry 8 d ago, no step-back yet: due despite a finding today
        self.assertIn("step-back overdue", ev)
        (c / "intel").mkdir(exist_ok=True)
        note = c / "intel" / "stepback-x.md"
        for note_h, findings_h, due in ((30, 0, False), (30, 30, True)):           # 30 h after a step-back: due only without progress
            (c / ".alerts").exists() and [p.unlink() for p in (c / ".alerts").glob("stepback-*")]
            (c / "events.log").write_text("")
            note.write_text("LEVER: x\nEDGE: y\n")
            os.utime(note, (time.time() - 3600 * note_h,) * 2)
            os.utime(c / "FINDINGS.md", (time.time() - 3600 * findings_h,) * 2)
            rc, out = self.run_("bash", str(KIT / "watcher.sh"), "w1", "--once", CLAUDE_PROJECTS=str(self.root / "proj"))
            self.assertEqual(rc, 0, out)
            self.assertEqual("step-back overdue" in (c / "events.log").read_text(), due, (note_h, findings_h))

    def test_watcher_reports_every_bad_csv_line(self):
        import datetime as dt
        t = dt.date.today().isoformat()
        rows = [f"e1,{t},c1,floor,5,,m1,0.81,0.7,0.91,1,Y,", f"e2,{t},c2,lever,5,,m1,0.82,0.7,0.92,1,Y,",
                f"e3,{t},c3,lever,5,,m1,0.83,0.7,0.93,1,Y,", f"e4,not-a-date,c4,lever,5,e1,m1,0.84,0.7,0.94,1,Y,"]
        _, ev, _ = self.watcher_pass(rows)                                         # lines 3, 4 no parent; line 5 bad date
        self.assertEqual(ev.count("ALERT [csvbad-"), 3, ev)
        for key in ("[csvbad-3]", "[csvbad-4]", "[csvbad-5] csvbad: experiments.csv line 5 has a missing/extra field"):
            self.assertIn(key, ev, key)

    # fail-closed on bad input ---------------------------------------------------
    def test_ruler_quiet_when_cv_ranks_a_scaled_board(self):
        import datetime as dt
        today = dt.date.today().isoformat()
        rows = [f"e{i},{today},c{i},lever,5,e1,m1,{.8 + .01 * i:.2f},0.7,{.4 + .005 * i:.3f},1,Y," for i in range(1, 10)]   # public = CV / 2
        _, ev, dg = self.watcher_pass(rows)
        self.assertNotIn("ruler", ev + dg)

    def test_ruler_fires_when_public_lags_cv(self):            # RSNA-like: CV .80 -> .88, public .800 -> .805
        import datetime as dt
        today = dt.date.today().isoformat()
        rows = [f"e{i},{today},c{i},lever,5,e1,m1,{x},0.7,{y},1,Y," for i, (x, y) in
                enumerate(zip((0.80, 0.82, 0.84, 0.86, 0.88), (0.800, 0.801, 0.802, 0.804, 0.805)), 1)]
        _, ev, _ = self.watcher_pass(rows)
        self.assertRegex(ev, r"ALERT \[ruler-[\d-]+\] ruler: CV vs public over 5 subs: slope 0.07 \(public gains < half of CV gains\)")

    def test_ruler_slope_unread_below_3x_lb_noise(self):     # CV range .005 = 2.5 x LB noise (.002): too narrow to read a slope
        import datetime as dt
        today = dt.date.today().isoformat()
        rows = [f"e{i},{today},c{i},lever,5,e1,m1,{x},0.7,{y},1,Y," for i, (x, y) in
                enumerate(zip((0.800, 0.801, 0.802, 0.803, 0.804, 0.805), (0.800, 0.800, 0.801, 0.800, 0.801, 0.801)), 1)]
        _, ev, dg = self.watcher_pass(rows)
        self.assertNotIn("ruler", ev + dg)

    def test_plateau(self):
        import datetime as dt
        d = lambda n: (dt.date.today() + dt.timedelta(n)).isoformat()
        with open(self.comp / "experiments.csv", "a") as fh:      # +0.01 in 20 d; 0.09 still to go in 4 weeks (public = CV)
            fh.write(f"e1,{d(-20)},c,floor,5,,m,0.80,,0.80,1,Y,\ne2,{d(0)},c,lever,5,e1,m,0.81,,,1,Y,\n")
        (self.comp / ".goldcut").write_text("0.90\n")
        (self.comp / ".deadline").write_text(d(28) + "\n")
        rc, out = self.run_("bash", str(KIT / "watcher.sh"), "demo", "--once", CLAUDE_PROJECTS=str(self.root))
        self.assertEqual(rc, 0, out)
        self.assertRegex((self.comp / "events.log").read_text(), r"plateau: 14-d gain / 2 = 0.005 < 0.02\d*/week needed to reach CV 0.9 ")

    def test_plateau_and_keeper_agree_on_cut_in_cv(self):
        import datetime as dt
        d = lambda n: (dt.date.today() + dt.timedelta(n)).isoformat()
        cv, pub = (0.80, 0.81, 0.82, 0.83, 0.84, 0.85), (0.801, 0.803, 0.812, 0.814, 0.822, 0.823)   # slope 0.48; median(public - CV) = -.012
        with open(self.comp / "experiments.csv", "a") as fh:
            fh.writelines(f"e{i},{d(-20 if i == 0 else 0)},c,{'floor' if i == 0 else 'lever'},5,{'' if i == 0 else 'e0'},m,{x},,{y},1,Y,\n"
                          for i, (x, y) in enumerate(zip(cv, pub)))
        (self.comp / ".goldcut").write_text("0.88\n")
        (self.comp / ".deadline").write_text(d(7) + "\n")
        cuts = []
        for lbn in ("0.03\n", ""):                                # quiet ruler (CV range < 3 x LB noise) or fired (no LB noise): the same median offset
            (self.comp / ".lbnoise").write_text(lbn)
            for f in (self.comp / ".alerts").glob("plateau*"): f.unlink()    # the plateau alert fires once a week
            rc, out = self.run_("bash", str(KIT / "watcher.sh"), "demo", "--once", CLAUDE_PROJECTS=str(self.root))
            self.assertEqual(rc, 0, out)
            rc, cut = self.run_("python3", "-c", "import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); import keeper; "
                                "print(keeper.cut_in_cv(Path(sys.argv[2]), 0.88))", str(KIT), str(self.comp))
            self.assertEqual(rc, 0, cut)
            self.assertIn(f"to reach CV {float(cut):.4g} (.goldcut in CV units)", (self.comp / "events.log").read_text())
            cuts.append(float(cut))
        self.assertEqual(cuts[0], cuts[1])
        self.assertAlmostEqual(cuts[0], 0.892, places=6)

    def step_back_pass(self, tokens):
        """FINDINGS.md last changed 4 h ago, `tokens` spent since, no kernel running; one watcher pass. Returns events.log."""
        import datetime as dt, json, time
        f = self.comp / "FINDINGS.md"
        if not (self.root / "proj").exists():                       # first pass: the clock starts 4 h ago and stays put
            f.write_text("| id | date | decision | number | example ids | verdict |\n|-|-|-|-|-|-|\n")
            os.utime(f, (int(time.time()) - 4 * 3600,) * 2)
            (self.root / "proj").mkdir()
        (self.root / "proj" / f"s{tokens}.jsonl").write_text(json.dumps({"timestamp": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                                               "message": {"id": f"m{tokens}", "usage": {"input_tokens": tokens}}}) + "\n")
        rc, out = self.run_("bash", str(KIT / "watcher.sh"), "demo", "--once", CLAUDE_PROJECTS=str(self.root / "proj"))
        self.assertEqual(rc, 0, out)
        return (self.comp / "events.log").read_text()

    def test_step_back_alerts_are_tier_1(self):
        import datetime as dt
        t = dt.date.today().isoformat()
        with open(self.comp / "experiments.csv", "a") as fh:      # m1: the idea + 2 variants, each no better than its parent
            fh.write(f"e1,{t},c1,floor,5,,m1,0.80,,,1,Y,\n" + "".join(f"e{i},{t},c{i},lever,5,e1,M1,0.7{i},,,1,N,\n" for i in (2, 3, 4)))
            fh.write(f"e5,{t},knob,,5,e1,m2,0.79,,,1,N,\n")            # a knob row needs no error file
        (self.comp / "eda").mkdir()
        (self.comp / "eda" / "err-e3.md").write_text("e3 errors read\n")
        ev = self.step_back_pass(6_000_000)
        for key in ("] stuck: FINDINGS.md unchanged for 4 h while 6M tokens were spent, no kernel running; step back: run skill autopsy",
                    "] stuck: 6M weighted tokens since FINDINGS.md last changed", "ALERT [loop-m1-e4] loop: mechanism m1 failed 3 times",
                    "] noerr: rows e1 e2 e4 have oof_mean"):   # e1 kept, e2/e4 lever; e3 read; e5 a knob
            self.assertIn(key, ev, key)
        self.assertEqual(ev.count("ALERT [stuck-time-"), 1)
        self.assertNotIn("step-back overdue", ev)                   # no .entry: the clocks start today
        (self.comp / "STATE.md").write_text("# state\n")              # a live competition
        _, err = self.hook("check_stop.py", {})
        self.assertIn("step back: run skill autopsy", err)          # the agent sees the instruction, not a cut-off key
        self.step_back_pass(6_000_000)
        self.assertEqual((self.comp / "events.log").read_text().count(" ALERT "), ev.count(" ALERT "))   # same state: no re-fire
        ev2 = self.step_back_pass(5_000_000)                        # 5M more tokens (11M), still no finding: stuck-tokens re-arms
        self.assertEqual(ev2.count("ALERT [stuck-tokens-"), 2)

    def test_idle_lead_is_not_stuck(self):
        self.assertNotIn("stuck", self.step_back_pass(1000))       # 4 h without a finding, but no work either

    def test_keeper_ignores_step_back_alerts(self):
        import datetime as dt
        now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        (self.comp / "STATE.md").write_text("# state\n")
        (self.comp / ".tokens_today").write_text("1000000\n")
        with open(self.comp / "events.log", "a") as fh:            # recent progress, one open step-back alert only
            fh.write(f"{now} PUSH me/k1 v1\n{now} ALERT [stuck-time-1] stuck: FINDINGS.md unchanged for 3 h\n")
        lines, _ = self.keeper(3)
        self.assertFalse([l for l in lines if "restart-lead" in l], lines)

    def test_plateau_goldcut_without_public_uses_flat_rule(self):
        import datetime as dt
        d = lambda n: (dt.date.today() + dt.timedelta(n)).isoformat()
        with open(self.comp / "experiments.csv", "a") as fh:      # no scored sub: the LB cut cannot be put in CV units
            fh.write(f"e1,{d(-20)},c,floor,5,,m,0.80,,,1,Y,\ne2,{d(-10)},c,lever,5,e1,m,0.81,,,1,Y,\n"
                     f"e3,{d(-1)},c,lever,5,e2,m,nan,,0.85,1,Y,\n")   # a NaN row (a screen recorded badly) is not a sub
        (self.comp / ".goldcut").write_text("0.90\n")
        (self.comp / ".deadline").write_text(d(28) + "\n")
        rc, out = self.run_("bash", str(KIT / "watcher.sh"), "demo", "--once", CLAUDE_PROJECTS=str(self.root))
        self.assertEqual(rc, 0, out)
        self.assertIn("plateau: best oof_mean not improved for 10 d", (self.comp / "events.log").read_text())

    def test_plateau_flat_rule_before_any_row_is_14_days_old(self):
        import datetime as dt
        d = lambda n: (dt.date.today() + dt.timedelta(n)).isoformat()
        with open(self.comp / "experiments.csv", "a") as fh:      # a scored sub, but no kept 5-fold row 14 days old yet
            fh.write(f"e1,{d(-10)},c,floor,5,,m,0.80,,0.80,1,Y,\ne2,{d(-1)},c,lever,5,e1,m,0.79,,,1,Y,\n")
        (self.comp / ".goldcut").write_text("0.90\n")
        (self.comp / ".deadline").write_text(d(28) + "\n")
        rc, out = self.run_("bash", str(KIT / "watcher.sh"), "demo", "--once", CLAUDE_PROJECTS=str(self.root))
        self.assertEqual(rc, 0, out)
        self.assertIn("plateau: best oof_mean not improved for 10 d", (self.comp / "events.log").read_text())

    def test_status_best_accepts_float_folds(self):
        with open(self.comp / "experiments.csv", "a") as fh:
            fh.write("e1,2026-01-01,c,base,5.0,,m1,0.8,0.7,,1,Y,\n")
        self.assertIn("BEST: CV 0.8 (e1)", self.run_("bash", str(KIT / "status.sh"), "demo")[1])

    def test_status_without_kept_row_or_transcripts(self):
        with open(self.comp / "experiments.csv", "a") as fh:
            fh.write("e1,2026-01-01,c,floor,5,,m1,0.8,0.7,,1,,\ne2,2026-01-02,c,base,1,e1,m1,0.81,,,1,,\n")
        out = self.run_("bash", str(KIT / "status.sh"), "demo", CLAUDE_PROJECTS=str(self.root / "none"))[1]
        self.assertIn("BEST: — (no kept=Y row yet; 2 scored)", out)
        self.assertIn("lead: no transcripts for this repo", out)

    def test_setup_competition_without_kaggle_and_relative_paths(self):
        import shutil
        if not shutil.which("kaggle", path="/usr/bin:/bin"):
            rc, out = self.run_("bash", str(KIT / "setup-competition.sh"), "w2", "W", "2099-01-01", PATH="/usr/bin:/bin")
            self.assertEqual(rc, 1, out)
            self.assertIn("kaggle CLI not on PATH", out)
        rc, out = self.run_("bash", str(KIT / "setup-competition.sh"), "w2", "W", "2099-01-01", HARNESS_ROOT=str(self.root), COMP_ROOT="")
        import re
        pid = re.search(r"watcher PID (\d+)", out)
        if pid:
            __import__("subprocess").run(["kill", pid.group(1)], capture_output=True)
        self.assertEqual(rc, 0, out)
        w0 = (self.root / "competitions" / "w2" / "WEEK0.md").read_text()
        self.assertIn("-p competitions/w2/data", w0)
        self.assertNotIn(str(self.root), w0)

    def test_second_watcher_names_the_lock_holder(self):
        import subprocess, time
        p = subprocess.Popen(["bash", str(KIT / "watcher.sh"), "demo"], env={**self.env, "CLAUDE_PROJECTS": str(self.root / "none")},
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            for _ in range(100):                                         # wait until it holds the lock and wrote its PID
                if (self.comp / ".lock").exists() and (self.comp / ".lock").read_text().strip() == str(p.pid):
                    break
                time.sleep(0.1)
            rc, out = self.run_("bash", str(KIT / "watcher.sh"), "demo", "--once")
            self.assertEqual(rc, 1, out)
            self.assertIn(f"PID {p.pid} holds", out)
            self.assertIn("kill it or wait for its next pass", out)
        finally:
            os.killpg(p.pid, 9); p.wait()                                 # the watcher and its sleeping child

    def test_budget_alert_level_from_env(self):
        (self.comp / ".entry").write_text("2026-01-01\n")
        (self.comp / ".deadline").write_text("2099-01-01\n")
        import json, datetime as dt
        proj = self.root / "proj" / str(KIT.parent).replace("/", "-").replace("_", "-").replace(".", "-")
        proj.mkdir(parents=True)
        now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        (proj / "s.jsonl").write_text(json.dumps({"timestamp": now, "message": {"id": "m", "usage": {"input_tokens": 2000000}}}) + "\n")
        for level, fired in (("45", False), ("1", True)):
            rc, out = self.run_("bash", str(KIT / "watcher.sh"), "demo", "--once", CLAUDE_PROJECTS=str(self.root / "proj"), TOKEN_ALERT_M=level)
            self.assertEqual(rc, 0, out)
            self.assertEqual("ALERT [budget]" in (self.comp / "events.log").read_text(), fired, level)

    def test_watcher_refuses_bad_dates(self):
        for f, v in ((".deadline", "2026-13-01"), (".entry", "2026-1O-01")):
            (self.comp / ".entry").write_text("2026-01-01\n")
            (self.comp / ".deadline").write_text("2099-01-01\n")
            (self.comp / f).write_text(v + "\n")
            rc, out = self.run_("bash", str(KIT / "watcher.sh"), "demo", "--once")
            self.assertEqual(rc, 2, out)
            self.assertIn("bad date", out)

    def test_watcher_without_kaggle_on_path(self):                                    # e.g. cron's bare PATH
        import shutil
        if shutil.which("kaggle", path="/usr/bin:/bin"):
            self.skipTest("a kaggle CLI is installed in /usr/bin or /bin")
        rc, out = self.run_("bash", str(KIT / "watcher.sh"), "demo", "--once", PATH="/usr/bin:/bin")
        self.assertEqual(rc, 2, out)
        self.assertIn("watcher: kaggle not on PATH", out)

    def test_agentmeter_daily_rows(self):
        import csv, datetime as dt, json
        d = dt.datetime.now(dt.timezone.utc)
        ts, y = d.strftime("%Y-%m-%dT%H:%M:%SZ"), (d - dt.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        msg = lambda i, t=ts, **k: json.dumps({"timestamp": t, **k.pop("top", {}), "message": {"id": i, "usage": k}})
        proj = self.root / "proj" / "p"
        (proj / "s1" / "subagents").mkdir(parents=True)
        (proj / "s1.jsonl").write_text("\n".join([
            msg("a", cache_read_input_tokens=100000), msg("b", cache_read_input_tokens=200000), msg("b", cache_read_input_tokens=200000),
            msg("c", cache_read_input_tokens=300000), msg("y", t=y, input_tokens=500000),
            msg("p", cache_read_input_tokens=1000000, top={"entrypoint": "sdk-cli"}),            # a `claude -p` job is a helper
            json.dumps({"timestamp": ts, "type": "system", "subtype": "compact_boundary", "uuid": "u1"})]) + "\n")
        (proj / "s1" / "subagents" / "agent-1.jsonl").write_text(msg("s", input_tokens=40000, top={"isSidechain": True}) + "\n")
        (self.comp / "FINDINGS.md").write_text(f"| id | date |\n|---|---|\n| f1 | {d.date()} |\n| f2 | {d.date()} |\n")
        (self.comp / "agentmeter.csv").write_text("date,wM,ctx_p50_k,ctx_p90_k,compactions,helper_share,findings,wM_per_finding\n"
                                                  "2020-01-01,9.00,50,80,0,0.10,1,9.00\n")
        rc, out = self.run_("python3", str(KIT / "agentmeter.py"), str(self.comp), "--since", "0", CLAUDE_PROJECTS=str(self.root / "proj"))
        self.assertEqual(rc, 0, out)
        self.assertEqual(out.split(), ["200000", "700000", "700000"])         # today, since epoch 0, 7 d
        rows = {r["date"]: r for r in csv.DictReader((self.comp / "agentmeter.csv").read_text().splitlines())}
        self.assertEqual(rows["2020-01-01"]["wM"], "9.00")                    # outside the window: kept
        self.assertEqual(rows[str((d - dt.timedelta(days=1)).date())]["wM"], "0.50")
        self.assertEqual({k: v for k, v in rows[str(d.date())].items() if k != "date"},
                         {"wM": "0.20", "ctx_p50_k": "200", "ctx_p90_k": "300", "compactions": "1", "helper_share": "0.70",
                          "findings": "2", "wM_per_finding": "0.10"})

    def test_agentmeter_restarted_lead_is_not_a_helper(self):
        import csv, datetime as dt, json, re
        ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        msg = lambda i: json.dumps({"timestamp": ts, "entrypoint": "sdk-cli", "message": {"id": i, "usage": {"input_tokens": 100000}}})
        lead = (self.root / "repo").resolve()
        (self.root / "proj" / re.sub(r"[^A-Za-z0-9]", "-", str(lead))).mkdir(parents=True)
        (self.root / "proj" / re.sub(r"[^A-Za-z0-9]", "-", str(lead)) / "s1.jsonl").write_text(msg("lead") + "\n")   # keeper's `claude -p` in LEAD_DIR
        (self.root / "proj" / "jobdir").mkdir()
        (self.root / "proj" / "jobdir" / "j1.jsonl").write_text(msg("job") + "\n")                                    # a fanout job elsewhere
        rc, out = self.run_("python3", str(KIT / "agentmeter.py"), str(self.comp), CLAUDE_PROJECTS=str(self.root / "proj"), LEAD_DIR=str(lead))
        self.assertEqual(rc, 0, out)
        row = list(csv.DictReader((self.comp / "agentmeter.csv").read_text().splitlines()))[-1]
        self.assertEqual((row["wM"], row["helper_share"]), ("0.20", "0.50"))

    def test_keeper_restarts_stuck_lead_then_stops(self):
        import time
        self.keeper_comp()
        log, notes = self.keeper(3)
        self.assertIn("restart-lead · idle 3.0 h, 1 open tier-1 alerts · noted", log[0])
        self.assertIn("lead was stuck; restarted (idle 3.0 h, 1 open tier-1 alerts) -> http://stub/t", notes[0])
        for _ in range(50):                                                                # the fake claude runs in the background
            if (self.root / "args").exists():
                break
            time.sleep(0.1)
        args = (self.root / "args").read_text()
        self.assertIn("-p --permission-mode acceptEdits You are the lead (CLAUDE.md)", args)
        self.assertIn("competition demo", args)
        log, notes = self.keeper(3)                                                        # no progress: second restart
        self.assertEqual([l.split(" · ")[1] for l in log], ["restart-lead", "restart-lead"])
        log, notes = self.keeper(3)                                                        # two restarts moved nothing: stop
        self.assertIn("stop · ", log[-1])
        self.assertIn("2 restarts made no progress · noted", log[-1])
        self.assertIn("stuck twice, stopped: please look", notes[-1])
        self.assertEqual(self.keeper(3)[0], log)                                           # stays stopped, says it once

    def test_keeper_restarts_one_lead_per_pass(self):                                   # R11: one lead
        import shutil
        self.keeper_comp()
        shutil.copytree(self.comp, self.comp.parent / "demo2")                            # a second stuck competition
        self.keeper(3)
        a, b = (self.comp / "keeper.md").read_text(), (self.comp.parent / "demo2" / "keeper.md").read_text()
        self.assertIn("restart-lead · idle 3.0 h", a)
        self.assertIn("no-restart · idle 3.0 h, 1 open tier-1 alerts; another competition's restart this pass (demo)", b)
        self.assertNotIn("restart-lead", b)

    def test_keeper_without_claude_cli_asks_owner(self):
        self.keeper_comp()
        log, notes = self.keeper(3, CLAUDE_BIN=str(self.root / "no-such-claude"))
        self.assertIn("no-restart · idle 3.0 h, 1 open tier-1 alerts; no claude CLI here", log[0])
        self.assertIn("restart the lead", notes[0])

    def test_keeper_active_lead_budget_and_dead_watcher(self):
        import signal
        self.keeper_comp()
        self.assertEqual(self.keeper(0.5), ([], []))                                      # lead active, before 08:00: nothing
        self.assertFalse((self.root / "args").exists())
        (self.comp / ".tokens_today").write_text("50000000\n")
        (self.comp / ".tokens_today").touch()
        log, notes = self.keeper(3)
        self.assertIn("no-restart · idle 3.0 h, 1 open tier-1 alerts; tokens today 50M > 45M (R20) · noted", log[0])
        self.assertIn("budget reached, lead not restarted", notes[0])
        self.assertFalse((self.root / "args").exists())
        (self.comp / ".keeper").unlink()                                                   # the level comes from TOKEN_ALERT_M, as the watcher's
        log, _ = self.keeper(3, TOKEN_ALERT_M="60")
        self.assertNotIn("tokens today", log[-1])
        (self.comp / ".keeper").unlink()
        (self.comp / "keeper.md").write_text("")
        log, _ = self.keeper(3, TOKEN_ALERT_M="40")
        self.assertIn("tokens today 50M > 40M (R20)", log[-1])
        (self.root / "args").unlink(missing_ok=True)
        (self.comp / ".tokens_today").unlink()                                             # dead watcher
        (self.comp / ".deadline").write_text("2099-01-01\n")
        log, _ = self.keeper(3)
        w = [l for l in log if "restart-watcher" in l]
        os.killpg(int(w[0].rsplit("PID ", 1)[1]), signal.SIGTERM)                         # we only check it was started
        self.assertIn("restart-watcher · heartbeat missing, new watcher PID", w[0])
        self.run_("flock", "-w", "20", str(self.comp / ".lock"), "true")

    def test_keeper_daily_summary_and_owner_decision(self):
        self.keeper_comp()
        (self.comp / "experiments.csv").write_text("id,date,change,kind,folds,parent,mechanism,oof_mean,oof_hard,public,gpu_h,kept,note\n"
                                                   "e1,2026-01-01,base,floor,5,,m,0.950,0.7,0.860,1,Y,\n")
        (self.comp / ".goldcut").write_text("0.880\n")                            # public-LB cut; CV runs .09 above public
        (self.comp / "NOW.md").write_text("NOW: x\nNEXT: y\nBLOCKED: owner: join comp B?\n")
        log, notes = self.keeper(0.5, OWNER_TZ=self.tz(12))
        self.assertEqual([l.split(" · ", 1)[1] for l in log],
                         ["owner-decision · BLOCKED: owner: join comp B? · noted",
                          "summary · best CV 0.950 · gap to gold +0.0200 · 1 open alerts · 0 restarts today · noted"])
        self.assertEqual(len(notes), 2)
        self.assertEqual(self.keeper(0.5, OWNER_TZ=self.tz(12)), (log, notes))          # once a day, once per text

    def test_keeper_summary_without_public_and_uncapped_owner_decision(self):
        import json
        self.keeper_comp()
        (self.comp / "experiments.csv").write_text("id,date,change,kind,folds,parent,mechanism,oof_mean,oof_hard,public,gpu_h,kept,note\n"
                                                   "e1,2026-01-01,base,floor,5,,m,0.950,0.7,,1,Y,\n")
        (self.comp / ".goldcut").write_text("0.880\n")
        (self.comp / "NOW.md").write_text("BLOCKED: owner: join comp B?\n")
        day = self.run_("date", "+%Y-%m-%d", TZ=self.tz(12))[1].strip()
        (self.comp / ".keeper").write_text(json.dumps({"notes": {day: 3}}))            # today's 3 notes already spent
        log, notes = self.keeper(0.5, OWNER_TZ=self.tz(12))
        self.assertEqual([l.split(" · ", 1)[1] for l in log],
                         ["owner-decision · BLOCKED: owner: join comp B? · noted",
                          "summary · best CV 0.950 · LB cut 0.880 · 1 open alerts · 0 restarts today · noted"])
        self.assertEqual(len(notes), 2)

    def test_keeper_progress_counts_lead_actions_only(self):
        import time
        (self.comp / "STATE.md").write_text("# state\n")
        (self.comp / ".tokens_today").write_text("1000000\n")
        os.utime(self.comp / "experiments.csv", (0, time.time() - 2 * 86400))                 # no new row for 2 days
        now = lambda: time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime())
        def watcher_lines():
            with open(self.comp / "events.log", "a") as fh:
                fh.write(f"{now()} KERNEL me/k1 running\n{now()} agentmeter failed\n")
        (self.comp / "events.log").write_text("2026-01-01T00:00Z PUSH me/k1 v1\n")              # last lead action: long ago
        watcher_lines()                                                                         # the watcher's own lines are not progress
        log, _ = self.keeper(3)
        self.assertIn("restart-lead · idle 3.0 h, no new experiment or event in 24 h", log[0])
        for _ in range(2):
            watcher_lines()
            log, _ = self.keeper(3)
        self.assertIn("2 restarts made no progress", log[-1])

    def test_keeper_cut_ignores_nan_rows(self):
        self.keeper_comp()
        (self.comp / "experiments.csv").write_text("id,date,change,kind,folds,parent,mechanism,oof_mean,oof_hard,public,gpu_h,kept,note\n"
                                                   "e1,2026-01-01,base,floor,5,,m,0.950,0.7,0.860,1,Y,\n"
                                                   "e2,2026-01-02,x,lever,5,e1,m,nan,,0.870,1,,\n")   # NaN oof_mean: not a sub
        (self.comp / ".goldcut").write_text("0.880\n")
        log, _ = self.keeper(0.5, OWNER_TZ=self.tz(12))
        self.assertIn("summary · best CV 0.950 · gap to gold +0.0200 ·", log[-1])


def load_tests(loader, tests, pattern):   # also run the tests of optional add-on checks (kit/extras/test_*.py), if any
    import importlib, sys
    for p in sorted((KIT / "extras").glob("test_*.py")):
        sys.path.insert(0, str(p.parent))
        tests.addTests(loader.loadTestsFromModule(importlib.import_module(p.stem)))
    return tests


if __name__ == "__main__":
    unittest.main()
