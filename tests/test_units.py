"""Tests for the unit check of the chosen sensors (template sensors without a device class must be usable)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

from units import DISTANCE_UNITS, ENERGY_UNITS, PERCENT_UNITS, unit_errors  # noqa: E402

SPECS = {"odometer_entity": (DISTANCE_UNITS, "not_distance"), "soc_entity": (PERCENT_UNITS, "not_percent"),
         "wallbox_energy_entity": (ENERGY_UNITS, "not_energy")}


def states(**units):
    """A fake `hass.states.get`: entity id (sensor__x) -> state with that unit (None = a sensor without a unit)."""
    table = {k.replace("__", "."): SimpleNamespace(attributes={"unit_of_measurement": u} if u is not None else {}) for k, u in units.items()}
    return table.get


class UnitErrorsTest(unittest.TestCase):
    def test_sensors_without_a_device_class_are_fine_when_the_unit_fits(self):
        s = states(sensor__km="km", sensor__soc="%", sensor__wb="kWh")
        self.assertEqual(unit_errors(s, {"odometer_entity": "sensor.km", "soc_entity": "sensor.soc", "wallbox_energy_entity": "sensor.wb"}, SPECS), {})

    def test_miles_and_wh_are_fine(self):
        s = states(sensor__mi="mi", sensor__wb="Wh")
        self.assertEqual(unit_errors(s, {"odometer_entity": "sensor.mi", "wallbox_energy_entity": "sensor.wb"}, SPECS), {})

    def test_a_wrong_unit_is_refused_with_the_matching_error(self):
        s = states(sensor__a="kWh", sensor__b="km", sensor__c="W")
        r = unit_errors(s, {"odometer_entity": "sensor.a", "soc_entity": "sensor.b", "wallbox_energy_entity": "sensor.c"}, SPECS)
        self.assertEqual(r, {"odometer_entity": "not_distance", "soc_entity": "not_percent", "wallbox_energy_entity": "not_energy"})

    def test_meters_are_refused_because_they_would_be_read_as_kilometres(self):
        self.assertEqual(unit_errors(states(sensor__m="m"), {"odometer_entity": "sensor.m"}, SPECS), {"odometer_entity": "not_distance"})

    def test_a_sensor_without_a_unit_is_accepted_where_a_unit_is_assumed(self):
        s = states(sensor__km=None, sensor__soc=None, sensor__wb=None)
        self.assertEqual(unit_errors(s, {"odometer_entity": "sensor.km", "soc_entity": "sensor.soc", "wallbox_energy_entity": "sensor.wb"}, SPECS), {})

    def test_a_sensor_that_is_not_loaded_yet_is_not_blocked(self):
        self.assertEqual(unit_errors(states(), {"odometer_entity": "sensor.later"}, SPECS), {})

    def test_empty_fields_are_not_checked(self):
        self.assertEqual(unit_errors(states(), {"odometer_entity": "sensor.x", "wallbox_energy_entity": ""}, SPECS), {})
        self.assertEqual(unit_errors(states(), {}, SPECS), {})

    def test_the_case_of_the_unit_does_not_matter(self):
        self.assertEqual(unit_errors(states(sensor__x="KM", sensor__y="KWH"), {"odometer_entity": "sensor.x", "wallbox_energy_entity": "sensor.y"}, SPECS), {})


if __name__ == "__main__":
    unittest.main()
