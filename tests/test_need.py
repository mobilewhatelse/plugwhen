"""Tests for the energy need of the next day."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

from learning import WeekdayPlan  # noqa: E402
from need import MODE_PLUS, compute_need  # noqa: E402


def plan(high=80.0, samples=8, home=0.9):
    return WeekdayPlan(weekday=2, samples=samples, km_typical=50.0, km_high=high, drive_share=1.0,
                       departure_hour=7.0, home_charge_share=home)


CAR = dict(capacity_kwh=60.0, consumption_kwh_per_km=0.2)


class NeedTest(unittest.TestCase):
    def test_reserve_is_the_floor(self):
        n = compute_need(plan(high=60), 100, 50, **CAR)
        self.assertEqual((n.km, n.source), (100.0, "reserve"))
        self.assertEqual(n.kwh, 20.0)
        self.assertAlmostEqual(n.target_soc, 33.3, places=1)

    def test_learned_value_lifts_a_long_day(self):
        n = compute_need(plan(high=136), 100, 50, **CAR)
        self.assertEqual((n.km, n.source), (136.0, "learned"))
        self.assertEqual(n.kwh, 27.2)

    def test_plus_mode_adds_the_reserve(self):
        n = compute_need(plan(high=60), 100, 50, mode=MODE_PLUS, **CAR)
        self.assertEqual((n.km, n.source), (160.0, "plus"))

    def test_too_few_days_reserve_only(self):
        n = compute_need(plan(high=300, samples=2), 100, 50, **CAR)
        self.assertEqual((n.km, n.source), (100.0, "reserve"))

    def test_away_day_gets_only_the_reserve(self):
        n = compute_need(plan(high=200, home=0.1), 100, 50, **CAR)
        self.assertEqual((n.km, n.source), (100.0, "away"))

    def test_unknown_charging_place_is_not_an_away_day(self):
        n = compute_need(plan(high=200, home=None), 100, 50, **CAR)
        self.assertEqual(n.source, "learned")

    def test_charge_energy_includes_losses(self):
        n = compute_need(plan(high=60), 100, 10, **CAR)  # target 33.3 % from 10 %
        self.assertAlmostEqual(n.charge_kwh, (33.333 - 10) / 100 * 60 / 0.9, places=1)

    def test_nothing_to_charge_if_full_enough(self):
        self.assertEqual(compute_need(plan(high=60), 100, 80, **CAR).charge_kwh, 0.0)

    def test_unknown_soc_charges_the_whole_target(self):
        n = compute_need(plan(high=60), 100, None, **CAR)
        self.assertAlmostEqual(n.charge_kwh, 33.333 / 100 * 60 / 0.9, places=1)

    def test_min_soc_floor(self):
        n = compute_need(plan(high=10), 20, 10, **CAR)  # 20 km = 4 kWh = 6.7 % but never leave below 20 %
        self.assertEqual(n.target_soc, 20.0)

    def test_capped_by_max_soc_and_not_reachable(self):
        n = compute_need(plan(high=400), 100, 50, max_soc=80, **CAR)  # 400 km = 80 kWh > capacity
        self.assertEqual(n.target_soc, 80.0)
        self.assertFalse(n.reachable)

    def test_winter_factor(self):
        n = compute_need(plan(high=60), 100, 50, winter_factor=1.25, **CAR)
        self.assertEqual(n.kwh, 25.0)


if __name__ == "__main__":
    unittest.main()
