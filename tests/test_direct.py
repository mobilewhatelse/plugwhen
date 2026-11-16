"""Tests for the mode 'direct' (Plugwhen controls the wallbox)."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

from direct import detect, in_grid_window, next_action, trip_energy_due, trip_settings  # noqa: E402

CET = timezone(timedelta(hours=1))
NOW = datetime(2026, 11, 12, 18, 0, tzinfo=CET)

WATTPILOT = [
    {"entity_id": "select.wattpilot_lademodus", "domain": "select", "options": ["Default", "Eco", "Next Trip"]},
    {"entity_id": "select.wattpilot_phasenumschaltung", "domain": "select", "options": ["Auto", "1 Phase", "3 Phases"]},
    {"entity_id": "time.wattpilot_nachste_abfahrtszeit", "domain": "time"},
    {"entity_id": "number.wattpilot_nachste_fahrt_laden", "domain": "number", "unit": "Wh"},
    {"entity_id": "number.wattpilot_max_ladestrom", "domain": "number", "unit": "A"},
    {"entity_id": "button.wattpilot_laden_starten", "domain": "button"},
    {"entity_id": "button.wattpilot_laden_stoppen", "domain": "button"},
    {"entity_id": "button.wattpilot_neustart", "domain": "button"},
]


class DetectTest(unittest.TestCase):
    def test_wattpilot_has_a_trip_mode(self):
        c = detect(WATTPILOT)
        self.assertEqual(c["variant"], "trip")
        self.assertEqual((c["mode"], c["mode_trip"], c["mode_sun"], c["mode_grid"]),
                         ("select.wattpilot_lademodus", "Next Trip", "Eco", "Default"))
        self.assertEqual((c["trip_time"], c["trip_energy"], c["trip_energy_unit"]),
                         ("time.wattpilot_nachste_abfahrtszeit", "number.wattpilot_nachste_fahrt_laden", "Wh"))
        self.assertEqual((c["start"], c["stop"]), ("button.wattpilot_laden_starten", "button.wattpilot_laden_stoppen"))

    def test_mode_without_trip_settings(self):
        c = detect([{"entity_id": "select.box_mode", "domain": "select", "options": ["Standard", "PV-Überschuss"]}])
        self.assertEqual((c["variant"], c["mode_grid"], c["mode_sun"]), ("mode", "Standard", "PV-Überschuss"))

    def test_only_buttons(self):
        c = detect([{"entity_id": "button.box_start", "domain": "button"}, {"entity_id": "button.box_stop", "domain": "button"}])
        self.assertEqual(c["variant"], "buttons")

    def test_nothing_to_control(self):
        self.assertIsNone(detect([{"entity_id": "number.box_current", "domain": "number", "unit": "A"}])["variant"])
        self.assertIsNone(detect([])["variant"])


class TripTest(unittest.TestCase):
    def test_departure_within_24_hours(self):
        dep = datetime(2026, 11, 13, 7, 0, tzinfo=CET)
        self.assertEqual(trip_settings(8.1, dep, NOW, "Wh"), {"time": "07:00:00", "energy": 8100})
        self.assertEqual(trip_settings(8.14, dep, NOW, "kWh"), {"time": "07:00:00", "energy": 8.1})

    def test_nothing_needed_or_too_far(self):
        self.assertIsNone(trip_settings(0.2, NOW + timedelta(hours=5), NOW, "Wh"))
        self.assertIsNone(trip_settings(8.0, NOW + timedelta(hours=30), NOW, "Wh"))
        self.assertIsNone(trip_settings(8.0, None, NOW, "Wh"))
        self.assertIsNone(trip_settings(8.0, NOW - timedelta(hours=1), NOW, "Wh"))


class WindowTest(unittest.TestCase):
    def test_grid_window(self):
        w = [{"start": NOW - timedelta(hours=1), "end": NOW + timedelta(hours=1), "energy_kwh": 6.0, "available_kwh": 0.0}]
        self.assertTrue(in_grid_window(w, NOW))
        self.assertFalse(in_grid_window(w, NOW + timedelta(hours=2)))

    def test_sun_window_is_not_a_grid_window(self):
        w = [{"start": NOW - timedelta(hours=1), "end": NOW + timedelta(hours=1), "energy_kwh": 6.0, "available_kwh": 6.0}]
        self.assertFalse(in_grid_window(w, NOW))
        self.assertFalse(in_grid_window(None, NOW))


class OwnershipTest(unittest.TestCase):
    def test_first_set_and_update(self):
        self.assertEqual(next_action("Eco", "Next Trip", None, None), ("set", "Next Trip"))
        self.assertEqual(next_action("Next Trip", "Next Trip", "Next Trip", "Eco"), (None, "same"))

    def test_user_changed_it(self):
        self.assertEqual(next_action("Default", "Next Trip", "Next Trip", "Eco"), (None, "user_changed"))

    def test_restore_only_what_we_set(self):
        self.assertEqual(next_action("Next Trip", None, "Next Trip", "Eco"), ("restore", "Eco"))
        self.assertEqual(next_action("Default", None, "Next Trip", "Eco"), (None, "nothing"))   # the user changed it: leave it
        self.assertEqual(next_action("Eco", None, None, None), (None, "nothing"))


class TripEnergyResendTest(unittest.TestCase):
    """Field test 16.11.2026: every new next-trip energy made the Wattpilot stop and plan again (ten stops in 80 minutes)."""

    CAP, EFF = 60.0, 0.9

    def due(self, new, written, soc):
        return trip_energy_due(new, written, soc, self.CAP, self.EFF)

    def test_first_write(self):
        self.assertTrue(self.due(12.6, None, 28.0))

    def test_falling_need_while_charging_is_not_written(self):
        w = {"kwh": 12.6, "soc": 28.0}
        # every percent of the 60 kWh battery is 0.67 kWh with the losses; values like the night from the field test
        for soc, need in ((29, 11.9), (30, 11.3), (31, 10.6), (32, 9.9), (33, 9.3), (36, 7.3), (38, 5.9)):
            self.assertFalse(self.due(need, w, float(soc)), (soc, need))

    def test_a_real_change_of_the_need_is_written(self):
        w = {"kwh": 12.6, "soc": 28.0}
        self.assertTrue(self.due(52.9, w, 28.0))   # the weekly full charge starts
        self.assertTrue(self.due(4.0, w, 28.0))    # the departure moved, much less needed
        self.assertTrue(self.due(14.5, w, 25.0))   # the car was driven: the need rose

    def test_small_drift_is_not_written(self):
        self.assertFalse(self.due(13.3, {"kwh": 12.6, "soc": 28.0}, 27.0))

    def test_without_soc_only_the_written_value_counts(self):
        self.assertFalse(self.due(12.0, {"kwh": 12.6, "soc": None}, None))
        self.assertTrue(self.due(8.0, {"kwh": 12.6, "soc": None}, None))


if __name__ == "__main__":
    unittest.main()
