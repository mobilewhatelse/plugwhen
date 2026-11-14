"""Tests for finding the entities of another integration."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

from links import pick  # noqa: E402

ENTRIES = [
    ("sensor.waechter_status", "sensor", "abc_status"),
    ("sensor.waechter_prognose", "sensor", "abc_forecast_peak"),
    ("switch.waechter_prognose", "switch", "abc_forecast_peak"),
    ("sensor.waechter_jetzt", "sensor", "abc_forecast_now"),
    ("sensor.ohne_id", "sensor", None),
]


class PickTest(unittest.TestCase):
    def test_finds_by_domain_and_suffix(self):
        self.assertEqual(pick(ENTRIES, "sensor", "_forecast_peak"), "sensor.waechter_prognose")
        self.assertEqual(pick(ENTRIES, "switch", "_forecast_peak"), "switch.waechter_prognose")

    def test_nothing_found(self):
        self.assertIsNone(pick(ENTRIES, "sensor", "_charge_plan"))
        self.assertIsNone(pick([], "sensor", "_forecast_peak"))

    def test_first_by_id_if_several(self):
        many = [("sensor.b_plan", "sensor", "x_charge_plan"), ("sensor.a_plan", "sensor", "y_charge_plan")]
        self.assertEqual(pick(many, "sensor", "_charge_plan"), "sensor.a_plan")

    def test_works_with_a_generator(self):
        self.assertEqual(pick((e for e in ENTRIES), "sensor", "_forecast_now"), "sensor.waechter_jetzt")


if __name__ == "__main__":
    unittest.main()
