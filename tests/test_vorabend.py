"""Charge the evening before: tomorrow's later trip is charged in the standing time (vorabend.py)."""

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

import messages  # noqa: E402
import vorabend as vb  # noqa: E402

TZ = timezone(timedelta(hours=1))
NOW = datetime(2026, 11, 18, 19, 10, tzinfo=TZ)


def hz(**over):
    h = {"lasts_until": "2026-11-19T07:00:00+01:00",
         "first_need": {"departure": "2026-11-19T20:00:00+01:00", "window_start": "2026-11-19T13:27:30+01:00",
                        "need_kwh": 2.3, "covered_by_sun": False}}
    h["first_need"].update(over)
    return h


class EveningBeforeTests(unittest.TestCase):
    def test_the_users_case(self):
        e = vb.evening_before(NOW, hz(), 81.0, 66.0, 0.9, True)
        self.assertIsNotNone(e)
        self.assertEqual(e.kwh, 2.3)
        self.assertAlmostEqual(e.target_soc, 81.0 + 2.3 * 0.9 / 66.0 * 100.0, delta=0.1)   # not cut by an everyday limit of 80 %
        self.assertEqual(e.by, datetime(2026, 11, 19, 7, 0, tzinfo=TZ))

    def test_no_charge_when_unplugged(self):
        self.assertIsNone(vb.evening_before(NOW, hz(), 81.0, 66.0, 0.9, False))

    def test_sun_covers_it(self):
        self.assertIsNone(vb.evening_before(NOW, hz(covered_by_sun=True), 81.0, 66.0, 0.9, True))

    def test_need_of_the_next_trip_is_the_normal_plan(self):
        h = hz()
        h["lasts_until"] = None
        self.assertIsNone(vb.evening_before(NOW, h, 81.0, 66.0, 0.9, True))

    def test_only_tomorrow(self):
        self.assertIsNone(vb.evening_before(NOW, hz(window_start="2026-11-20T13:00:00+01:00"), 81.0, 66.0, 0.9, True))

    def test_arising_today_is_not_evening_before(self):
        self.assertIsNone(vb.evening_before(NOW, hz(window_start="2026-11-18T21:00:00+01:00"), 81.0, 66.0, 0.9, True))

    def test_what_the_plan_charges_anyway_is_not_doubled(self):
        e = vb.evening_before(NOW, hz(), 81.0, 66.0, 0.9, True, have_kwh=2.0)
        self.assertIsNone(e)   # 0.3 kWh left: not worth a charge
        e = vb.evening_before(NOW, hz(need_kwh=5.0), 81.0, 66.0, 0.9, True, have_kwh=2.0)
        self.assertEqual(e.kwh, 3.0)

    def test_capped_at_100(self):
        e = vb.evening_before(NOW, hz(need_kwh=30.0), 95.0, 66.0, 0.9, True)
        self.assertEqual(e.target_soc, 100.0)

    def test_text_in_both_languages(self):
        e = vb.evening_before(NOW, hz(), 81.0, 66.0, 0.9, True)
        self.assertIn("Do 07:00", messages.evening_text("de", e.as_dict()))
        self.assertIn("Thu 20:00", messages.evening_text("en", e.as_dict()))


if __name__ == "__main__":
    unittest.main()
