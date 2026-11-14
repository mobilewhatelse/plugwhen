"""Tests for the 'car will not be ready' notice."""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

from need import Need  # noqa: E402
from notice import check_ready, dedupe_key, remember_sent, should_check  # noqa: E402


def need(charge=10.0, reachable=True, target=60.0, km=136.0):
    return Need(km=km, kwh=27.0, target_soc=target, charge_kwh=charge, reachable=reachable, source="learned")


def check(n=None, **kw):
    base = dict(plugged=False, charging=False, hours_to_departure=10.0, charge_kw_max=11.0, planned_kwh=None)
    base.update(kw)
    return check_ready(n or need(), 30.0, **base)


class NoticeTest(unittest.TestCase):
    def test_ready_car_needs_no_notice(self):
        self.assertIsNone(check(need(charge=0.0)))
        self.assertIsNone(check(need(charge=0.3)))

    def test_not_plugged_in_asks_to_plug_in(self):
        n = check()
        self.assertEqual(n.kind, "plug_in")
        self.assertEqual((n.shortfall_kwh, n.target_soc, n.km), (10.0, 60.0, 136.0))

    def test_charging_is_fine(self):
        self.assertIsNone(check(plugged=True, charging=True))

    def test_a_plan_that_covers_it_is_fine(self):
        self.assertIsNone(check(plugged=True, planned_kwh=10.0))
        self.assertIsNone(check(plugged=True, planned_kwh=9.6))      # 96 % of the shortfall
        self.assertIsNone(check(plugged=None, planned_kwh=10.0))
        self.assertEqual(check(plugged=None, planned_kwh=5.0).kind, "low")

    def test_a_plan_does_not_help_an_unplugged_car(self):
        self.assertEqual(check(plugged=False, planned_kwh=10.0).kind, "plug_in")

    def test_too_late_even_at_full_power(self):
        n = check(need(charge=30.0), hours_to_departure=2.0)   # 11 kW * 2 h = 22 kWh
        self.assertEqual((n.kind, n.max_possible_kwh), ("too_late", 22.0))

    def test_too_late_wins_over_plug_in(self):
        self.assertEqual(check(need(charge=30.0), hours_to_departure=2.0, plugged=False).kind, "too_late")

    def test_not_reachable_wins_over_everything(self):
        self.assertEqual(check(need(reachable=False), hours_to_departure=1.0).kind, "not_reachable")

    def test_unknown_plug_state(self):
        self.assertEqual(check(plugged=None).kind, "low")
        self.assertIsNone(check(plugged=None, planned_kwh=12.0))  # unknown plug state, covered by a plan

    def test_plugged_in_but_idle_without_plan_is_no_warning(self):
        self.assertIsNone(check(plugged=True))

    def test_unknown_time_or_power_skips_the_too_late_test(self):
        self.assertEqual(check(need(charge=500.0), hours_to_departure=None).kind, "plug_in")
        self.assertEqual(check(need(charge=500.0), charge_kw_max=None).kind, "plug_in")


class TimingTest(unittest.TestCase):
    def test_dedupe_once_per_day_and_kind(self):
        a, b = check(), check(need(charge=30.0), hours_to_departure=2.0)
        d = date(2026, 11, 6)
        self.assertEqual(dedupe_key(a, d), "2026-11-06:plug_in")
        self.assertNotEqual(dedupe_key(a, d), dedupe_key(b, d))
        self.assertNotEqual(dedupe_key(a, d), dedupe_key(a, date(2026, 11, 7)))

    def test_checks_from_the_evening_until_departure(self):
        self.assertFalse(should_check(15.0, 19.0, 16.0))
        self.assertTrue(should_check(19.5, 19.0, 11.5))
        self.assertTrue(should_check(5.0, 19.0, 2.0))      # early morning, shortly before leaving
        self.assertFalse(should_check(7.5, 19.0, -0.5))    # departure is past


class RememberSentTest(unittest.TestCase):
    def test_once_only_message_is_kept_for_good(self):
        """"The learn mode is through" fell out after eight other messages and came again every week or two."""
        sent: list[str] = []
        remember_sent(sent, "switch_ready", 8)
        for d in range(1, 30):
            remember_sent(sent, f"ahead:2026-11-{d:02d}:sun", 8)
        self.assertIn("switch_ready", sent)
        self.assertEqual(len([k for k in sent if k != "switch_ready"]), 8)
        self.assertEqual(sent[-1], "ahead:2026-11-29:sun")

    def test_dated_messages_keep_the_last_ones(self):
        sent: list[str] = []
        for d in range(1, 12):
            remember_sent(sent, f"2026-11-{d:02d}:low", 8)
        self.assertEqual(sent, [f"2026-11-{d:02d}:low" for d in range(4, 12)])
        remember_sent(sent, "2026-11-11:low", 8)   # the same key twice is noted once
        self.assertEqual(len(sent), 8)


if __name__ == "__main__":
    unittest.main()
