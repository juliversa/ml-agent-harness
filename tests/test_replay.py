"""Replay of two past competitions' records (examples/) through today's watcher, point in time: the key alerts fire on the recorded day.
python3 -m unittest tests.test_replay  (about 5 s; examples/replay.py prints the full replay)"""
import datetime as dt, importlib.util, unittest
from pathlib import Path

EX = Path(__file__).resolve().parent.parent / "examples"
spec = importlib.util.spec_from_file_location("replay", EX / "replay.py")
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


def days(comp):
    alerts, screens = replay.replay(EX / comp)
    d, msg = {}, {}
    for day, a in alerts:
        d.setdefault(replay.KEY(a), []).append(day)
        msg.setdefault(replay.KEY(a), a)
    return d, msg, screens


class Replay(unittest.TestCase):
    def test_rsna_knee(self):
        d, msg, screens = days("rsna-knee")
        self.assertEqual(d["ruler"][0], "2026-10-16")       # not before the rescored CVs and the first LB-noise measure exist
        self.assertEqual(d["plateau"][0], "2026-10-14")     # log's best 5-fold CV flat since e042 (10-07)
        self.assertIn("not improved for 7 d", msg["plateau"])
        self.assertEqual(screens, "e001 e003 e005 e007 e009 e011 e012 e013 e025 e028".split())   # kept on 1 fold

    def test_rsna_rate_rule_after_rescore(self):
        alerts, _ = replay.replay(EX / "rsna-knee")
        rate = [day for day, a in alerts if "14-d gain" in a]
        self.assertEqual(rate[0], "2026-10-18")             # 14-d CV gain too slow for the gold cut, day -4

    def test_rogii(self):
        d, msg, screens = days("rogii-wellbore")
        self.assertEqual((d["plateau"][0], d["plateau"][-1]), ("2026-07-31", "2026-08-03"))   # 7 d flat; pscont (08-04) clears it
        self.assertEqual(d["ruler"], ["2026-08-05"])        # LB noise first recorded 08-07: not measured during the competition
        self.assertFalse([k for k in d if k.startswith("loop")])   # blend, ens-deploy, ens2: kept=N but each beat its parent's CV (superseded)
        self.assertFalse({"noerr", "stepback"} & set(d))   # not in the records: left out
        self.assertIn("LB noise not measured", msg["ruler"])
        self.assertEqual(screens, [])

    def test_known_by_is_point_in_time(self):
        day = dt.date.fromisoformat
        known = [{"date": "2026-10-16", "id": "e010", "column": "oof_mean", "value": ".8992"},
                 {"date": "2026-10-07", "id": ".goldcut", "column": "", "value": ".959"}]
        self.assertEqual(replay.known_by(known, day("2026-10-06"), day), {})
        self.assertEqual(replay.known_by(known, day("2026-10-15"), day), {(".goldcut", ""): ".959"})
        self.assertEqual(len(replay.known_by(known, day("2026-10-16"), day)), 2)


if __name__ == "__main__":
    unittest.main()
