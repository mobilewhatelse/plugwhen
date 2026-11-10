"""Tests for the mode 'direct' (Plugwhen controls the wallbox)."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

from direct import detect, in_grid_window, next_action, trip_settings  # noqa: E402

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


if __name__ == "__main__":
    unittest.main()
