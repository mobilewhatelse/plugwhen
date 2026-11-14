"""Start values from open data (startwerte.py): shape, limits, and the same numbers as the server's startwerte.json."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "custom_components" / "plugwhen"))

import startwerte as sw  # noqa: E402

SERVER = ROOT.parent / "energie-cloud" / "startwerte" / "v1" / "startwerte.json"


class StartValuesTest(unittest.TestCase):
    def test_temperature_curve(self):
        self.assertEqual(sw.temperature_factor(20.0), 1.0)
        self.assertEqual(sw.temperature_factor(22.0), 1.0)
        self.assertAlmostEqual(sw.temperature_factor(0.0), 1.22)
        self.assertAlmostEqual(sw.temperature_factor(-15.0), 1.60)
        self.assertAlmostEqual(sw.temperature_factor(-2.5), (1.22 + 1.32) / 2)
        self.assertEqual(sw.temperature_factor(-40.0), 1.75)   # never more than the coldest point
        self.assertGreater(sw.temperature_factor(32.0), 1.0)   # a little air conditioning
        xs = [x for x, _ in sw.TEMPERATURE]
        self.assertEqual(xs, sorted(xs))
        cold = [y for x, y in sw.TEMPERATURE if x <= 20]
        self.assertEqual(cold, sorted(cold, reverse=True))     # colder never costs less

    def test_charge_loss_matches_the_measured_ranges(self):
        self.assertTrue(0.127 <= sw.charge_loss(2.3) <= 0.242)   # ADAC 2026, household socket
        self.assertTrue(0.080 <= sw.charge_loss(4.1) <= 0.128)   # solar surplus
        self.assertLess(sw.charge_loss(11.0), 0.07)
        self.assertLess(sw.charge_loss(22.0), 0.07)
        self.assertEqual(sw.charge_loss(0.1), sw.LOSS_MAX)
        self.assertEqual(sw.charge_loss(1000.0), sw.LOSS_MIN)
        self.assertAlmostEqual(sw.charge_efficiency(4.0), 0.89, places=2)

    @unittest.skipUnless(SERVER.is_file(), "server repository not next to this one")
    def test_same_as_on_the_server(self):
        d = json.loads(SERVER.read_text(encoding="utf-8"))["auto"]
        self.assertEqual([list(p) for p in sw.TEMPERATURE], [[float(x), float(y)] for x, y in d["temperatur"]["faktor"]])
        lv = d["ladeverlust"]
        self.assertEqual((sw.LOSS_BASE_KW, sw.LOSS_SHARE, sw.LOSS_MIN, sw.LOSS_MAX), (lv["grund_kw"], lv["anteil"], lv["min"], lv["max"]))
        for kw, loss in lv["beispiele"]:
            self.assertAlmostEqual(sw.charge_loss(kw), loss, places=3)


if __name__ == "__main__":
    unittest.main()
