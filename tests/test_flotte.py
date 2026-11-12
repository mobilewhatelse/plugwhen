"""Fleet values (flotte.py): which days are sent and how, the car model's name, and how the fetched models are used."""

from __future__ import annotations

import json
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components" / "plugwhen"))

import flotte  # noqa: E402
from learning import DayRecord  # noqa: E402

D0 = date(2026, 11, 1)


def rec(i, km=50.0, c=0.18, t=5.0):
    return DayRecord(D0 + timedelta(days=i), km=km, consumption=c, temp_c=t)


class ModelNameTest(unittest.TestCase):
    def test_name(self):
        self.assertEqual(flotte.model_name("Mercedes-Benz", "EQA 250+"), "mercedes-benz eqa 250+")
        self.assertEqual(flotte.model_name("  Tesla ", "Model  3 (LR)"), "tesla model 3 lr")
        self.assertEqual(flotte.model_name(None, "e-Golf"), "e-golf")

    def test_nothing_usable(self):
        self.assertIsNone(flotte.model_name(None, None))
        self.assertIsNone(flotte.model_name("", "  "))
        self.assertIsNone(flotte.model_name(None, "12"))     # only digits say nothing about the car


class TripDaysTest(unittest.TestCase):
    def test_only_usable_complete_days(self):
        records = [rec(0), rec(1, km=10.0), rec(2, c=None), rec(3, t=None), rec(4, c=0.9), rec(5, km=2000.0), rec(6)]
        days, last = flotte.trip_days(records, "vw e-golf", 35.8, None, D0 + timedelta(days=6))   # day 6 is today
        self.assertEqual(len(days), 1)
        self.assertEqual(days[0], {"modell": "vw e-golf", "akku_kwh": 36, "km": 50, "kwh_km": 0.18, "temp_c": 5})
        self.assertEqual(last, D0 + timedelta(days=5))

    def test_no_date_no_place_no_id(self):
        days, _ = flotte.trip_days([rec(i) for i in range(5)], "m", 60, None, D0 + timedelta(days=10))
        self.assertTrue(all(set(d) == {"modell", "akku_kwh", "km", "kwh_km", "temp_c"} for d in days))
        sent = json.dumps(flotte.payload(days, True))
        self.assertNotIn("2026", sent)

    def test_only_new_days(self):
        records = [rec(i) for i in range(10)]
        days, last = flotte.trip_days(records, "m", 60, D0 + timedelta(days=6), D0 + timedelta(days=10))
        self.assertEqual(len(days), 3)
        self.assertEqual(last, D0 + timedelta(days=9))
        again, last2 = flotte.trip_days(records, "m", 60, last, D0 + timedelta(days=10))
        self.assertEqual((again, last2), ([], last))

    def test_at_most_400(self):
        records = [rec(i) for i in range(500)]
        days, _ = flotte.trip_days(records, "m", 60, None, D0 + timedelta(days=600))
        self.assertEqual(len(days), 400)

    def test_payload(self):
        p = flotte.payload([], False)
        self.assertEqual((p["schema"], p["integration"], p["erstes_mal"]), (1, "plugwhen", False))


MODELS = {
    "schema": 1, "autos": 40,
    "modelle": {"vw e-golf": {"tage": 120, "median_kwh_km": 0.16, "mittel_kwh_km": 0.165, "mittel_temp_c": 10.0,
                              "steigung_kwh_km_je_k": -0.004, "temp_min_c": -5, "temp_max_c": 25, "akku_kwh": 36, "autos": 6}},
    "alle": {"tage": 900, "median_kwh_km": 0.19, "mittel_kwh_km": 0.2, "mittel_temp_c": 12.0, "steigung_kwh_km_je_k": None,
             "temp_min_c": -10, "temp_max_c": 30},
}


class UseModelsTest(unittest.TestCase):
    def test_own_model_first_then_all(self):
        self.assertEqual(flotte.entry_for(MODELS, "vw e-golf")[1], "fleet_model")
        self.assertEqual(flotte.entry_for(MODELS, "tesla model 3")[1], "fleet_all")
        self.assertEqual(flotte.entry_for(MODELS, None)[1], "fleet_all")
        self.assertEqual(flotte.entry_for(None, "vw e-golf"), (None, None))
        self.assertEqual(flotte.entry_for({"schema": 2}, "vw e-golf"), (None, None))
        self.assertEqual(flotte.entry_for({"schema": 1, "modelle": {}, "alle": None}, "x"), (None, None))

    def test_curve(self):
        e = MODELS["modelle"]["vw e-golf"]
        self.assertAlmostEqual(flotte.consumption(e, 10.0), 0.165)
        self.assertAlmostEqual(flotte.consumption(e, 0.0), 0.205)            # 0.165 + 0.004 * 10
        self.assertAlmostEqual(flotte.consumption(e, -30.0), 0.205 + 0.004 * 10)   # cut 5 K below the coldest day (-10)
        self.assertAlmostEqual(flotte.consumption(e, 35.0), 0.165 - 0.004 * 20)    # warmer: less, up to 30 deg C

    def test_without_slope_the_start_curve(self):
        e = MODELS["alle"]
        self.assertGreater(flotte.consumption(e, -10.0), flotte.consumption(e, 12.0))
        self.assertAlmostEqual(flotte.consumption(e, 12.0), 0.2)
        self.assertAlmostEqual(flotte.consumption(e, None), 0.19)           # no temperature: the median

    def test_rising_slope_never_used(self):
        e = dict(MODELS["modelle"]["vw e-golf"], steigung_kwh_km_je_k=0.01)
        self.assertAlmostEqual(flotte.consumption(e, 0.0), 0.165)

    def test_broken_entry(self):
        self.assertIsNone(flotte.consumption({}, 5.0))
        self.assertIsNone(flotte.consumption({"mittel_kwh_km": "x"}, 5.0))


class DueTest(unittest.TestCase):
    def test_due(self):
        now = datetime(2026, 11, 13, 9, 0, tzinfo=timezone.utc)
        self.assertTrue(flotte.due(None, now))
        self.assertTrue(flotte.due("kaputt", now))
        self.assertFalse(flotte.due((now - timedelta(hours=5)).isoformat(), now))
        self.assertTrue(flotte.due((now - timedelta(hours=21)).isoformat(), now))


class SameRulesAsServerTest(unittest.TestCase):
    """The limits must match the service (autodaten/v1/gemeinsam.php), if that repository is next to this one."""

    def test_limits(self):
        php = ROOT.parent / "energie-cloud" / "autodaten" / "v1" / "gemeinsam.php"
        if not php.exists():
            self.skipTest("energie-cloud not next to this repository")
        t = php.read_text(encoding="utf-8")
        self.assertIn("zahl($t['km'] ?? null, 30, 1500)", t)
        self.assertIn("zahl($t['kwh_km'] ?? null, 0.08, 0.6)", t)
        self.assertIn("MAX_TAGE_JE_SENDUNG = 400", t)


if __name__ == "__main__":
    unittest.main()
