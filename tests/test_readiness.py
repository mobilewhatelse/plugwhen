"""Tests for 'ready to switch?'."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

from readiness import switch_readiness  # noqa: E402

NOW = datetime(2026, 11, 10, 9, 0, tzinfo=timezone(timedelta(hours=1)))
WEEK = [{"weekday": d, "samples": 8, "used": d < 6} for d in range(7)]   # Sunday not driven


class ReadinessTest(unittest.TestCase):
    def test_today_in_one_house(self):
        r = switch_readiness(WEEK, 1, None, 0, NOW)
        self.assertFalse(r["ready"])
        ok = {c["key"]: c["ok"] for c in r["checks"]}
        self.assertEqual(ok, {"trips": True, "compare_days": False, "agree": False, "solar": False})
        self.assertEqual(r["estimate"], "2026-11-22")   # 6 more comparison days, about every second day

    def test_ready(self):
        r = switch_readiness(WEEK, 7, 85, 6, NOW)
        self.assertTrue(r["ready"])
        self.assertIsNone(r["estimate"])

    def test_agreement_too_low(self):
        r = switch_readiness(WEEK, 9, 70, 6, NOW)
        self.assertFalse(r["ready"])
        self.assertIsNone(r["estimate"])          # nothing to wait for: the decisions do not fit yet

    def test_without_solar_plant_no_solar_check(self):
        r = switch_readiness(WEEK, 7, 90, None, NOW)
        self.assertTrue(r["ready"])
        self.assertNotIn("solar", [c["key"] for c in r["checks"]])

    def test_trips_not_learned(self):
        week = [{"weekday": d, "samples": 2 if d == 2 else 8, "used": True} for d in range(7)]
        r = switch_readiness(week, 7, 90, None, NOW)
        self.assertFalse(r["ready"])
        self.assertEqual(r["checks"][0]["value"], 6)
        self.assertFalse(switch_readiness([], 7, 90, None, NOW)["ready"])   # nothing learned at all


if __name__ == "__main__":
    unittest.main()
