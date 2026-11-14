"""Tests for the check "does the learning bring anything"."""

from __future__ import annotations

import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

from insight import learning_check  # noqa: E402
from learning import DayRecord  # noqa: E402

D0 = date(2027, 1, 4)    # Monday


def history(days, km_by_weekday, hour_by_weekday=None, hour_jitter=0.0):
    out = []
    for i in range(days):
        d = D0 + timedelta(days=i)
        km = km_by_weekday(d.weekday(), i)
        hour = (hour_by_weekday or {}).get(d.weekday(), 7.0)
        out.append(DayRecord(d, km=km, first_move_hour=(hour + (hour_jitter if i % 3 == 0 else 0.0)) if km >= 2 else None))
    return out


class LearningCheckTest(unittest.TestCase):
    def test_a_weekday_with_long_trips_shows_that_learning_helps(self):
        recs = history(120, lambda wd, i: 150.0 if wd == 2 else 30.0)          # every Wednesday 150 km
        r = learning_check(recs, reserve_km=100)
        self.assertEqual(r["verdict"], "learning_helps")
        self.assertGreater(r["coverage_learned_pct"], r["coverage_reserve_pct"] + 5)
        self.assertEqual(r["coverage_learned_pct"], 100)
        self.assertLess(r["coverage_reserve_pct"], 100)

    def test_an_even_car_needs_only_the_reserve(self):
        recs = history(120, lambda wd, i: 40.0)
        r = learning_check(recs, reserve_km=100)
        self.assertEqual(r["verdict"], "reserve_enough")
        self.assertEqual(r["coverage_reserve_pct"], 100)
        self.assertEqual(r["gain_points"], 0)

    def test_too_little_data(self):
        r = learning_check(history(40, lambda wd, i: 40.0), reserve_km=100)       # 28 warm-up days, 12 left
        self.assertEqual(r["verdict"], "too_little_data")
        self.assertEqual(r["days"], 12)

    def test_no_history_at_all(self):
        r = learning_check([], 100)
        self.assertEqual(r["verdict"], "too_little_data")
        self.assertIsNone(r["coverage_reserve_pct"])
        self.assertIsNone(r["departure_right_pct"])

    def test_departure_is_judged_within_one_hour(self):
        steady = learning_check(history(120, lambda wd, i: 40.0, hour_jitter=0.0), 100)
        self.assertEqual(steady["departure_right_pct"], 100)
        wild = learning_check(history(120, lambda wd, i: 40.0, hour_jitter=3.0), 100)
        self.assertLess(wild["departure_right_pct"], steady["departure_right_pct"])

    def test_departure_by_weekday_has_seven_entries(self):
        r = learning_check(history(120, lambda wd, i: 40.0 if wd < 5 else 0.0), 100)
        self.assertEqual([x["weekday"] for x in r["departure_by_weekday"]], list(range(7)))
        self.assertIsNone(r["departure_by_weekday"][6]["right_pct"])               # the car never leaves on Sundays
        self.assertEqual(r["departure_by_weekday"][0]["right_pct"], 100)

    def test_the_early_departure_makes_the_car_ready_more_often(self):
        # leaves at 6:30 on every third day, otherwise at 7:30: a plan at the median (7.5) is late on those days
        recs = [DayRecord(D0 + timedelta(days=i), km=40.0, first_move_hour=6.5 if i % 3 == 0 else 7.5) for i in range(120)]
        r = learning_check(recs, 100)
        self.assertLess(r["ready_median_pct"], 75)
        self.assertEqual(r["ready_early_pct"], 100)
        from learning import MobilityModel
        m = MobilityModel()
        for rec in recs:
            m.add_day(rec)
        p = m.plan(0)
        self.assertEqual(p.departure_early, 6.5)
        self.assertEqual(p.departure_hour, 7.5)

    def test_when_the_kilometres_hardly_help_but_the_early_plan_does_the_verdict_names_the_departure(self):
        # an even car (the reserve covers everything) that leaves earlier on every third day: the early plan is ready in time, the median plan is not
        recs = [DayRecord(D0 + timedelta(days=i), km=40.0, first_move_hour=6.5 if i % 3 == 0 else 7.5) for i in range(120)]
        r = learning_check(recs, 100)
        self.assertEqual(r["verdict"], "departure_helps")
        self.assertGreaterEqual(r["departure_gain_points"], 10)
        for d in r["departure_by_weekday"]:
            self.assertIsNotNone(d["ready_early_pct"])
            self.assertGreaterEqual(d["ready_early_pct"], d["ready_median_pct"])

    def test_a_steady_car_has_no_departure_verdict(self):
        r = learning_check(history(120, lambda wd, i: 40.0), reserve_km=100)           # same hour every day: both plans are in time
        self.assertEqual(r["verdict"], "reserve_enough")
        self.assertEqual(r["departure_gain_points"], 0)

    def test_kilometres_help_wins_over_departure(self):
        recs = [DayRecord(D0 + timedelta(days=i), km=150.0 if i % 7 == 2 else 30.0, first_move_hour=6.5 if i % 3 == 0 else 7.5) for i in range(120)]
        self.assertEqual(learning_check(recs, 100)["verdict"], "learning_helps")
    def test_days_without_kilometres_are_not_counted(self):
        recs = history(120, lambda wd, i: 40.0)
        recs = [DayRecord(r.day, km=None, first_move_hour=None) if i % 2 else r for i, r in enumerate(recs)]
        r = learning_check(recs, 100)
        self.assertLess(r["days"], 70)

    def test_the_learned_value_never_covers_less_than_the_reserve(self):
        recs = history(150, lambda wd, i: float((i * 37) % 160))
        r = learning_check(recs, 100)
        self.assertGreaterEqual(r["coverage_learned_pct"], r["coverage_reserve_pct"])


if __name__ == "__main__":
    unittest.main()
