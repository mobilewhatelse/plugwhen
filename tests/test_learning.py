"""Tests for the mobility learning (pure Python)."""

from __future__ import annotations

import random
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "ready_by"))

from learning import (  # noqa: E402
    DEFAULT_CONSUMPTION, MAX_DAYS, DayRecord, MobilityModel, backtest, quantile_high,
)

MON = date(2027, 1, 4)  # a Monday


def mondays(n: int, **kw):
    return [DayRecord(MON + timedelta(weeks=i), **kw) for i in range(n)]


class QuantileTest(unittest.TestCase):
    def test_few_values_take_the_largest(self):
        self.assertEqual(quantile_high([10, 40, 20]), 40)

    def test_nearest_rank(self):
        self.assertEqual(quantile_high([10, 20, 30, 40, 50, 60, 70, 80]), 70)  # ceil(0.8*8)=7 -> 7th value
        self.assertEqual(quantile_high([1, 2, 3, 4, 5]), 4)


class PlanTest(unittest.TestCase):
    def test_typical_and_high(self):
        m = MobilityModel()
        for rec, km in zip(mondays(8), [30, 40, 35, 45, 120, 38, 42, 36]):
            m.add_day(DayRecord(rec.day, km=km))
        p = m.plan(0)
        self.assertEqual(p.samples, 8)
        self.assertEqual(p.km_typical, 39.0)       # median of the eight
        self.assertEqual(p.km_high, 45.0)          # 7th of 8 sorted values: the 120 km outlier stays out
        self.assertEqual(p.drive_share, 1.0)

    def test_unknown_weekday_has_no_numbers(self):
        p = MobilityModel().plan(3)
        self.assertEqual((p.samples, p.km_typical, p.km_high, p.departure_hour), (0, None, None, None))

    def test_days_without_a_trip_count_as_zero(self):
        m = MobilityModel()
        for rec, km in zip(mondays(6), [0, 0, 50, 0, 60, 0]):
            m.add_day(DayRecord(rec.day, km=km))
        p = m.plan(0)
        self.assertEqual(p.km_typical, 0.0)
        self.assertEqual(p.drive_share, 0.33)

    def test_glitches_and_unknown_days_are_ignored(self):
        m = MobilityModel()
        for rec, km in zip(mondays(5), [40, None, -5, 99999, 44]):
            m.add_day(DayRecord(rec.day, km=km))
        p = m.plan(0)
        self.assertEqual(p.samples, 2)
        self.assertEqual(p.km_typical, 42.0)

    def test_same_date_replaces(self):
        m = MobilityModel()
        m.add_day(DayRecord(MON, km=10))
        m.add_day(DayRecord(MON, km=55))
        self.assertEqual(m.plan(0).samples, 1)
        self.assertEqual(m.plan(0).km_typical, 55.0)

    def test_keeps_only_the_last_days(self):
        m = MobilityModel()
        for i, rec in enumerate(mondays(12)):
            m.add_day(DayRecord(rec.day, km=100 + i))
        self.assertEqual(m.plan(0).samples, MAX_DAYS)
        self.assertEqual(m.plan(0).km_typical, 107.5)  # days 104..111 -> median of 104..111 is 107.5

    def test_departure_needs_two_trips(self):
        m = MobilityModel()
        m.add_day(DayRecord(MON, km=40, first_move_hour=7.0))
        self.assertIsNone(m.plan(0).departure_hour)
        m.add_day(DayRecord(MON + timedelta(weeks=1), km=40, first_move_hour=8.0))
        self.assertEqual(m.plan(0).departure_hour, 7.5)

    def test_departure_ignores_days_without_trip(self):
        m = MobilityModel()
        for rec, (km, h) in zip(mondays(4), [(0, None), (40, 7.0), (0, 13.0), (45, 7.0)]):
            m.add_day(DayRecord(rec.day, km=km, first_move_hour=h))
        self.assertEqual(m.plan(0).departure_hour, 7.0)

    def test_home_charge_share(self):
        m = MobilityModel()
        for rec, (home, away) in zip(mondays(4), [(20.0, 0.0), (0.0, 25.0), (10.0, 10.0), (0.2, 0.3)]):
            m.add_day(DayRecord(rec.day, km=40, home_kwh=home, away_kwh=away))
        # the last day charged under 1 kWh: no statement; the others: 1.0, 0.0, 0.5
        self.assertEqual(m.plan(0).home_charge_share, 0.5)

    def test_unknown_charging_place_is_no_statement(self):
        m = MobilityModel()
        for rec in mondays(5):
            m.add_day(DayRecord(rec.day, km=40, home_kwh=20.0, away_kwh=None))
        self.assertIsNone(m.plan(0).home_charge_share)


class ConsumptionTest(unittest.TestCase):
    def test_default_until_known(self):
        m = MobilityModel()
        self.assertEqual(m.consumption_kwh_per_km(), DEFAULT_CONSUMPTION)
        self.assertFalse(m.consumption_known)

    def test_median_of_known_values(self):
        m = MobilityModel()
        for rec, c in zip(mondays(5), [0.19, 0.21, 0.20, 0.30, 0.18]):
            m.add_day(DayRecord(rec.day, km=40, consumption=c))
        self.assertTrue(m.consumption_known)
        self.assertEqual(m.consumption_kwh_per_km(), 0.2)

    def test_implausible_values_are_dropped(self):
        m = MobilityModel()
        for rec, c in zip(mondays(5), [0.01, 5.0, 0.2, 0.2, 0.2]):
            m.add_day(DayRecord(rec.day, km=40, consumption=c))
        self.assertEqual(m.consumption, [0.2, 0.2, 0.2])


class StoreTest(unittest.TestCase):
    def test_roundtrip(self):
        m = MobilityModel()
        for i, rec in enumerate(mondays(5)):
            m.add_day(DayRecord(rec.day, km=30 + i, first_move_hour=7.0, home_kwh=10.0, away_kwh=0.0, consumption=0.2))
        m.add_day(DayRecord(MON + timedelta(days=2), km=None))
        back = MobilityModel.from_dict(m.to_dict())
        self.assertEqual(back.week(), m.week())
        self.assertEqual(back.consumption, m.consumption)

    def test_broken_rows_are_skipped(self):
        back = MobilityModel.from_dict({"days": {"0": [["not-a-date", 1, 2, 3, 4, 5], ["2027-01-04", 40, None, None, None, None]]}})
        self.assertEqual(back.plan(0).samples, 1)


def synthetic_history(days: int = 240, seed: int = 7) -> list[DayRecord]:
    """A year-like history: weekday medians as in the author's data, a heavy tail, some days without a trip."""
    medians = [45, 45, 78, 46, 41, 39, 24]
    rnd = random.Random(seed)
    out = []
    for i in range(days):
        d = date(2026, 3, 2) + timedelta(days=i)
        km = 0.0 if rnd.random() < 0.04 else medians[d.weekday()] * rnd.lognormvariate(0.0, 0.6)
        out.append(DayRecord(d, km=round(km, 1), first_move_hour=7.0 if d.weekday() < 5 and km > 0 else None))
    return out


class BacktestTest(unittest.TestCase):
    def setUp(self):
        self.h = synthetic_history()
        self.r = backtest(self.h, reserve_km=100)

    def test_median_alone_covers_about_half(self):
        self.assertGreater(self.r["typical"], 0.40)
        self.assertLess(self.r["typical"], 0.62)

    def test_high_value_covers_clearly_more(self):
        self.assertGreater(self.r["high"], self.r["typical"] + 0.2)
        self.assertGreater(self.r["high"], 0.70)

    def test_reserve_floor_with_learned_high_is_best(self):
        self.assertGreaterEqual(self.r["reserve_or_high"], self.r["reserve"])
        self.assertGreaterEqual(self.r["reserve_or_high"], self.r["high"])
        self.assertGreater(self.r["reserve_or_high"], 0.88)

    def test_counts_only_days_after_warmup(self):
        self.assertEqual(self.r["days"], float(len(self.h) - 28))

    def test_the_model_only_knows_the_past(self):
        # a one-off huge day after the warm-up must not be 'covered' by the day itself
        h = self.h + [DayRecord(self.h[-1].day + timedelta(days=1), km=900)]
        self.assertLess(backtest(h, reserve_km=100)["reserve_or_high"], self.r["reserve_or_high"])


if __name__ == "__main__":
    unittest.main()
