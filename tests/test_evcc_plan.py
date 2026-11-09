"""Tests for the plan Plugwhen would write into evcc (nothing is written)."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

from evcc_plan import current_plan, evcc_plan, proposal, same  # noqa: E402

CET = timezone(timedelta(hours=1))
NOW = datetime(2026, 11, 9, 22, 0, tzinfo=CET)
DEP = datetime(2026, 11, 10, 6, 0, tzinfo=CET)
STATE = {"vehicles": {"db:3": {"title": "Mercedes", "plan": {"soc": 80, "time": "2026-11-10T07:00:00+01:00"}},
                      "golf": {"title": "Golf"}, "bike": {"title": "Bike", "plan": {"soc": 0, "time": "2026-11-10T07:00:00+01:00"}}}}


class ProposalTest(unittest.TestCase):
    def test_planned_rounds_up(self):
        self.assertEqual(proposal(33.3, 20.0, DEP, NOW), ({"soc": 34, "time": DEP.isoformat()}, "planned"))
        self.assertEqual(proposal(34.0, 20.0, DEP, NOW)[0]["soc"], 34)
        self.assertEqual(proposal(100.0, 20.0, DEP, NOW)[0]["soc"], 100)

    def test_nothing_to_write(self):
        self.assertEqual(proposal(33.3, 72.0, DEP, NOW), (None, "not_needed"))
        self.assertEqual(proposal(33.3, None, DEP, NOW), (None, "unknown_soc"))
        self.assertEqual(proposal(33.3, 20.0, None, NOW), (None, "no_departure"))
        self.assertEqual(proposal(33.3, 20.0, NOW - timedelta(hours=1), NOW), (None, "no_departure"))
        self.assertEqual(proposal(None, 20.0, DEP, NOW), (None, "no_target"))


class CurrentTest(unittest.TestCase):
    def test_reads_evccs_plan(self):
        self.assertEqual(current_plan(STATE, "db:3"), {"soc": 80, "time": "2026-11-10T07:00:00+01:00"})

    def test_no_plan(self):
        self.assertIsNone(current_plan(STATE, "golf"))
        self.assertIsNone(current_plan(STATE, "bike"))      # soc 0 = no plan
        self.assertIsNone(current_plan(STATE, "nope"))
        self.assertIsNone(current_plan(None, "db:3"))
        self.assertIsNone(current_plan({"vehicles": {"x": {"plan": {"soc": 50, "time": "kaputt"}}}}, "x"))

    def test_same_with_tolerance_and_zones(self):
        a = {"soc": 80, "time": "2026-11-10T07:00:00+01:00"}
        self.assertTrue(same(a, {"soc": 81, "time": "2026-11-10T06:10:00Z"}))      # 07:10 local, 1 % apart
        self.assertFalse(same(a, {"soc": 80, "time": "2026-11-10T06:20:00Z"}))     # 20 min apart
        self.assertFalse(same(a, {"soc": 75, "time": "2026-11-10T07:00:00+01:00"}))
        self.assertFalse(same(a, None))


class ComparisonTest(unittest.TestCase):
    def test_own_plan_in_evcc_is_left_alone(self):
        out = evcc_plan(STATE, "db:3", 33.3, 20.0, DEP, NOW)
        self.assertEqual(out["would_write"], {"soc": 34, "time": DEP.isoformat()})
        self.assertEqual(out["current"]["soc"], 80)
        self.assertFalse(out["same"])
        self.assertTrue(out["own_plan"])
        self.assertFalse(out["written"])

    def test_same_plan(self):
        dep = datetime(2026, 11, 10, 7, 5, tzinfo=CET)
        out = evcc_plan(STATE, "db:3", 79.4, 20.0, dep, NOW)
        self.assertTrue(out["same"])
        self.assertFalse(out["own_plan"])

    def test_without_evcc_car_nothing(self):
        self.assertIsNone(evcc_plan(STATE, None, 33.3, 20.0, DEP, NOW))
        self.assertIsNone(evcc_plan(None, "", 33.3, 20.0, DEP, NOW))

    def test_evcc_not_reachable_still_shows_the_proposal(self):
        out = evcc_plan(None, "db:3", 33.3, 20.0, DEP, NOW)
        self.assertFalse(out["evcc_known"])
        self.assertIsNone(out["current"])
        self.assertEqual(out["would_write"]["soc"], 34)

    def test_two_cars_each_their_own(self):
        a = evcc_plan(STATE, "db:3", 50.0, 20.0, DEP, NOW)
        b = evcc_plan(STATE, "golf", 60.0, 10.0, DEP + timedelta(hours=1), NOW)
        self.assertEqual((a["would_write"]["soc"], b["would_write"]["soc"]), (50, 60))
        self.assertTrue(a["own_plan"])
        self.assertFalse(b["own_plan"])
        self.assertIsNone(b["current"])


if __name__ == "__main__":
    unittest.main()
