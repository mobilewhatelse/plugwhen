"""Tests for the charging habit."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

from habit import charging_habit  # noqa: E402

TZ = timezone(timedelta(hours=1))
START = datetime(2026, 9, 7, 0, 0, tzinfo=TZ)        # a Monday
NOW = START + timedelta(days=70)


def series(rule):
    """`rule(weekday, hour)` -> kWh of that hour, for 70 days of hourly values."""
    out = {}
    for d in range(70):
        for h in range(24):
            t = START + timedelta(days=d, hours=h)
            out[t] = rule(t.weekday(), h)
    return out


class HabitTest(unittest.TestCase):
    def test_night_charging_on_wednesday_and_thursday_and_sun_on_the_weekend(self):
        def rule(wd, h):
            if wd in (2, 3) and h in (22, 23, 0, 1):
                return 3.0                       # 12 kWh at night
            if wd in (5, 6) and 10 <= h < 14:
                return 3.0                       # 12 kWh at noon
            return 0.0
        r = charging_habit(series(rule), NOW)
        self.assertEqual(r["status"], "ok")
        by = {d["weekday"]: d for d in r["weekday"]}
        self.assertEqual(by[2]["night_kwh_per_day"], 12.0)
        self.assertEqual(by[2]["day_kwh_per_day"], 0.0)
        self.assertEqual(by[5]["day_kwh_per_day"], 12.0)
        self.assertEqual(by[0]["kwh_per_day"], 0.0)
        self.assertEqual(r["night_share_pct"], 50)
        self.assertEqual(r["day_share_pct"], 50)
        self.assertEqual(r["weekend_share_pct"], 50)
        self.assertEqual(r["weekdays_night_share_pct"], 100)
        self.assertEqual(by[2]["charge_days"], 10)

    def test_the_energy_adds_up(self):
        r = charging_habit(series(lambda wd, h: 1.0 if h in (6, 18) else 0.5 if h == 3 else 0.0), NOW)
        per_day = sum(d["kwh_per_day"] * d["days"] for d in r["weekday"])
        self.assertAlmostEqual(per_day, r["total_kwh"], delta=1.0)
        by = {d["weekday"]: d for d in r["weekday"]}
        self.assertEqual(by[0]["night_kwh_per_day"], 1.5)          # 3 h and 6 h are both at night, 18 h is neither day nor night
        self.assertEqual(by[0]["rest_kwh_per_day"], 1.0)

    def test_too_little_data(self):
        few = {START + timedelta(hours=h): 1.0 for h in range(24 * 10)}
        self.assertEqual(charging_habit(few, NOW)["status"], "too_little_data")
        self.assertEqual(charging_habit({}, NOW)["status"], "too_little_data")
        tiny = series(lambda wd, h: 0.01 if h == 5 else 0.0)
        self.assertEqual(charging_habit(tiny, NOW)["status"], "too_little_data")        # hardly any energy

    def test_missing_values_and_old_hours_are_ignored(self):
        s = series(lambda wd, h: 2.0 if h == 23 else 0.0)
        s[START + timedelta(hours=5)] = None
        r = charging_habit(s, NOW, days=40)
        self.assertEqual(r["status"], "ok")
        self.assertLessEqual(r["days"], 41)


if __name__ == "__main__":
    unittest.main()
