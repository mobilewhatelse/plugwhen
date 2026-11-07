"""Tests for the learned house-specific numbers."""

from __future__ import annotations

import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

from calibrate import SolarAccuracy, base_load_from_hourly, efficiency_from_records, quarter_add_from_5min  # noqa: E402
from learning import DayRecord  # noqa: E402

TZ = timezone(timedelta(hours=1))
T0 = datetime(2027, 1, 4, 0, 0, tzinfo=TZ)


class QuarterAddTest(unittest.TestCase):
    def test_flat_load_has_no_add(self):
        series = [(T0 + timedelta(minutes=5 * i), 0.5) for i in range(12 * 60)]
        self.assertEqual(quarter_add_from_5min(series), 0.0)

    def test_a_spike_in_one_quarter_shows_up(self):
        series = []
        for h in range(60):
            for i in range(12):
                kw = 0.5 + (2.4 if i < 3 else 0.0)          # the first quarter of every hour is 2.4 kW above the rest
                series.append((T0 + timedelta(hours=h, minutes=5 * i), kw))
        add = quarter_add_from_5min(series)
        self.assertAlmostEqual(add, 2.4 - 0.6, places=1)   # quarter 2.9 minus hour mean 1.1
        series_none = [(t, None) for t, _ in series]
        self.assertIsNone(quarter_add_from_5min(series_none))

    def test_too_few_hours(self):
        series = [(T0 + timedelta(minutes=5 * i), 1.0) for i in range(12 * 10)]
        self.assertIsNone(quarter_add_from_5min(series))


class BaseLoadTest(unittest.TestCase):
    def test_median_of_the_night_hours(self):
        hourly = {}
        for d in range(7):
            for h in range(24):
                hourly[T0 + timedelta(days=d, hours=h)] = 0.35 if h in (1, 2, 3, 4, 5) else 1.5
        self.assertEqual(base_load_from_hourly(hourly), 0.35)

    def test_too_few_days(self):
        hourly = {T0 + timedelta(hours=h): 0.3 for h in range(24)}
        self.assertIsNone(base_load_from_hourly(hourly))


class EfficiencyTest(unittest.TestCase):
    def test_median_ratio_on_home_only_days(self):
        recs = [DayRecord(date(2027, 1, 4) + timedelta(days=i), km=30.0, home_kwh=10.0, away_kwh=0.0, charged_kwh=8.9) for i in range(6)]
        recs.append(DayRecord(date(2027, 2, 1), km=30.0, home_kwh=10.0, charged_kwh=25.0))      # charged elsewhere too: ignored
        recs.append(DayRecord(date(2027, 2, 2), km=30.0, home_kwh=1.0, charged_kwh=0.9))        # too little: ignored
        self.assertEqual(efficiency_from_records(recs), 0.89)

    def test_too_few_days_or_no_data(self):
        self.assertIsNone(efficiency_from_records([DayRecord(date(2027, 1, 4), home_kwh=10.0, charged_kwh=9.0)]))
        self.assertIsNone(efficiency_from_records([DayRecord(date(2027, 1, 4), km=10.0)] * 10))


class SolarAccuracyTest(unittest.TestCase):
    def test_factor_from_pairs(self):
        s = SolarAccuracy()
        for i in range(6):
            d = date(2027, 3, 1) + timedelta(days=i)
            s.predict(d, 20.0)
            s.predict(d, 18.0)                                   # the last prediction before the day counts
            self.assertTrue(s.measured(d, 14.4))                 # 0.8 of the prediction
        self.assertEqual(s.factor(), 0.8)
        self.assertEqual(s.summary()["days"], 6)

    def test_too_few_days_and_restore(self):
        s = SolarAccuracy()
        s.predict(date(2027, 3, 1), 10.0)
        self.assertFalse(s.measured(date(2027, 3, 2), 5.0))      # no prediction for that day
        self.assertIsNone(s.factor())
        again = SolarAccuracy(s.to_dict())
        self.assertEqual(again.pending, {"2027-03-01": 10.0})
        SolarAccuracy({"days": {"x": "kaputt"}, "pending": "nein"})   # damaged data must not break the start

    def test_factor_is_clamped(self):
        s = SolarAccuracy()
        for i in range(5):
            d = date(2027, 3, 1) + timedelta(days=i)
            s.predict(d, 1.0)
            s.measured(d, 9.0)
        self.assertEqual(s.factor(), 1.5)


if __name__ == "__main__":
    unittest.main()
