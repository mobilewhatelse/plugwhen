"""Tests for the plans Plugwhen would write into evcc (nothing is written)."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

from evcc_plan import current_plan, current_weekly, evcc_plan, hhmm, same, same_weekly, weekly_plans  # noqa: E402

CET = timezone(timedelta(hours=1))
NOW = datetime(2026, 11, 9, 22, 0, tzinfo=CET)          # Monday evening
FRI = datetime(2026, 11, 13, 7, 0, tzinfo=CET)
STATE = {"vehicles": {
    "db:3": {"title": "Mercedes", "plan": {"soc": 80, "time": "2026-11-10T07:00:00+01:00"},
             "repeatingPlans": [{"weekdays": [1, 2, 3, 4, 5], "time": "07:00", "tz": "Europe/Vienna", "soc": 50, "active": True},
                                {"weekdays": [0], "time": "13:00", "soc": 30, "active": False}]},
    "golf": {"title": "Golf"},
    "bike": {"title": "Bike", "plan": {"soc": 0, "time": "2026-11-10T07:00:00+01:00"}}}}
WEEK = [{"weekday": 0, "hour": 8.5, "target_soc": 48.6}, {"weekday": 1, "hour": 7.0, "target_soc": 32.1},
        {"weekday": 2, "hour": 7.0, "target_soc": 32.1}, {"weekday": 3, "hour": 7.0, "target_soc": 32.1},
        {"weekday": 4, "hour": 7.0, "target_soc": 32.1}, {"weekday": 5, "hour": 13.0, "target_soc": 30.0}]


class AheadTest(unittest.TestCase):
    def test_first_needed_departure_is_written_early(self):
        out = evcc_plan(STATE, "db:3", {"departure": FRI, "target_soc": 33.3}, WEEK, NOW)
        self.assertEqual(out["would_write"], {"soc": 34, "time": FRI.isoformat()})   # already on Monday, rounded up
        self.assertEqual(out["reason"], "planned")
        self.assertTrue(out["own_plan"])          # evcc has 80 % by Tuesday: the user's own plan, left alone
        self.assertFalse(out["written"])

    def test_charge_lasts_the_whole_look_ahead(self):
        out = evcc_plan(STATE, "golf", None, WEEK, NOW, lasts_until="2026-11-20T07:00:00+01:00")
        self.assertIsNone(out["would_write"])
        self.assertEqual(out["reason"], "covered")
        self.assertEqual(out["lasts_until"], "2026-11-20T07:00:00+01:00")
        self.assertFalse(out["own_plan"])

    def test_unknown_soc_and_past_departure(self):
        self.assertEqual(evcc_plan(STATE, "golf", None, [], NOW, reason="unknown_soc")["reason"], "unknown_soc")
        past = evcc_plan(STATE, "golf", {"departure": NOW - timedelta(hours=1), "target_soc": 40}, [], NOW)
        self.assertEqual((past["would_write"], past["reason"]), (None, "no_departure"))
        self.assertEqual(evcc_plan(STATE, "golf", {"departure": FRI, "target_soc": None}, [], NOW)["reason"], "no_target")

    def test_same_as_evcc(self):
        tue = datetime(2026, 11, 10, 7, 5, tzinfo=CET)
        out = evcc_plan(STATE, "db:3", {"departure": tue, "target_soc": 79.4}, [], NOW)
        self.assertTrue(out["same"])
        self.assertFalse(out["own_plan"])

    def test_without_evcc_car_nothing_and_unreachable_evcc_still_shows(self):
        self.assertIsNone(evcc_plan(STATE, None, {"departure": FRI, "target_soc": 34}, WEEK, NOW))
        out = evcc_plan(None, "db:3", {"departure": FRI, "target_soc": 34}, WEEK, NOW)
        self.assertFalse(out["evcc_known"])
        self.assertIsNone(out["current"])
        self.assertEqual(out["weekly_current"], [])
        self.assertEqual(out["would_write"]["soc"], 34)

    def test_two_cars_each_their_own(self):
        a = evcc_plan(STATE, "db:3", {"departure": FRI, "target_soc": 50}, WEEK, NOW)
        b = evcc_plan(STATE, "golf", {"departure": FRI + timedelta(days=1), "target_soc": 60}, [], NOW)
        self.assertEqual((a["would_write"]["soc"], b["would_write"]["soc"]), (50, 60))
        self.assertIsNone(b["current"])


class WeeklyTest(unittest.TestCase):
    def test_grouped_by_time_and_target(self):
        self.assertEqual(weekly_plans(WEEK), [
            {"weekdays": [0], "time": "08:30", "soc": 49},
            {"weekdays": [1, 2, 3, 4], "time": "07:00", "soc": 33},
            {"weekdays": [5], "time": "13:00", "soc": 30},
        ])

    def test_hhmm(self):
        self.assertEqual((hhmm(7.0), hhmm(13.5), hhmm(6.999)), ("07:00", "13:30", "07:00"))

    def test_skips_days_without_values(self):
        self.assertEqual(weekly_plans([{"weekday": 6, "hour": None, "target_soc": 30}, {"weekday": 2, "hour": 7, "target_soc": None}]), [])

    def test_evccs_weekdays_are_converted(self):
        cur = current_weekly(STATE, "db:3")
        self.assertEqual(cur[0], {"weekdays": [0, 1, 2, 3, 4], "time": "07:00", "soc": 50, "active": True})   # evcc Mon-Fri
        self.assertEqual(cur[1]["weekdays"], [6])                                                              # evcc 0 = Sunday
        self.assertEqual(current_weekly(STATE, "golf"), [])

    def test_same_weekly_ignores_inactive_evcc_plans(self):
        mine = [{"weekdays": [0, 1, 2, 3, 4], "time": "07:00", "soc": 50}]
        self.assertTrue(same_weekly(mine, current_weekly(STATE, "db:3")))
        self.assertFalse(same_weekly(weekly_plans(WEEK), current_weekly(STATE, "db:3")))
        self.assertFalse(same_weekly([], []))


class CurrentTest(unittest.TestCase):
    def test_reads_evccs_plan(self):
        self.assertEqual(current_plan(STATE, "db:3"), {"soc": 80, "time": "2026-11-10T07:00:00+01:00"})
        self.assertIsNone(current_plan(STATE, "golf"))
        self.assertIsNone(current_plan(STATE, "bike"))
        self.assertIsNone(current_plan(None, "db:3"))
        self.assertIsNone(current_plan({"vehicles": {"x": {"plan": {"soc": 50, "time": "kaputt"}}}}, "x"))

    def test_same_with_tolerance_and_zones(self):
        a = {"soc": 80, "time": "2026-11-10T07:00:00+01:00"}
        self.assertTrue(same(a, {"soc": 81, "time": "2026-11-10T06:10:00Z"}))
        self.assertFalse(same(a, {"soc": 80, "time": "2026-11-10T06:20:00Z"}))
        self.assertFalse(same(a, None))


if __name__ == "__main__":
    unittest.main()
