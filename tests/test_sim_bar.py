"""The PLAYBOOK law-4 numbers (bar power, ruler false alarms) reproduced by kit/sim_bar.py, wide tolerances."""
import importlib.util, unittest

from base import KIT

spec = importlib.util.spec_from_file_location("sim_bar", KIT / "sim_bar.py")
sim = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sim)


class SimBar(unittest.TestCase):
    def test_power_one_fold_sd_about_one_in_three(self):
        self.assertTrue(0.25 <= sim.power(1, 4000) <= 0.40)

    def test_ruler_false_alarm_rates(self):
        for n in (5, 6, 8):
            self.assertTrue(1 / 10 <= sim.ruler_alarm(n, 1.0, 4000) <= 1 / 4.5, n)          # about 1 in 5–9
            self.assertTrue(1 / 45 <= sim.ruler_alarm(n, 2 ** -.5, 4000) <= 1 / 17, n)      # about 1 in 20–40
