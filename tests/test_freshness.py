"""Tests for the age check of the state of charge."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

from freshness import soc_is_stale  # noqa: E402

H = 3600.0
MIN = 60.0


class StaleTest(unittest.TestCase):
    def test_fresh_value_is_fine(self):
        self.assertFalse(soc_is_stale(5 * MIN, 12, False))
        self.assertFalse(soc_is_stale(5 * MIN, 12, True))

    def test_a_parked_sleeping_car_is_fine_for_hours(self):
        self.assertFalse(soc_is_stale(8 * H, 12, False))       # asleep all night: still true

    def test_too_old_even_when_parked(self):
        self.assertTrue(soc_is_stale(13 * H, 12, False))

    def test_while_charging_ninety_minutes_without_news_is_stale(self):
        self.assertFalse(soc_is_stale(80 * MIN, 12, True))
        self.assertTrue(soc_is_stale(100 * MIN, 12, True))

    def test_limit_zero_means_no_general_limit_but_charging_rule_stays(self):
        self.assertFalse(soc_is_stale(100 * H, 0, False))
        self.assertTrue(soc_is_stale(100 * MIN, 0, True))

    def test_unknown_age_is_not_stale(self):
        self.assertFalse(soc_is_stale(None, 12, True))

    def test_custom_charging_limit(self):
        self.assertTrue(soc_is_stale(20 * MIN, 12, True, charging_max_min=15))
        self.assertFalse(soc_is_stale(10 * MIN, 12, True, charging_max_min=15))


if __name__ == "__main__":
    unittest.main()
