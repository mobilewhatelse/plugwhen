"""Tests for trips from a calendar."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

from trips import one_way, parse_km, range_for_trip, trip_km, trips_from_events, waze_region  # noqa: E402

CET = timezone(timedelta(hours=1))
NOW = datetime(2026, 11, 10, 9, 0, tzinfo=CET)


class ParseTest(unittest.TestCase):
    def test_km_in_text(self):
        self.assertEqual(parse_km("Linz 200 km"), 200.0)
        self.assertEqual(parse_km("Graz", "hin und zurück 120km"), 120.0)
        self.assertEqual(parse_km("Wien 85,5 Kilometer"), 85.5)
        self.assertIsNone(parse_km("Termin um 14 Uhr", None))
        self.assertIsNone(parse_km("0 km"))

    def test_one_way(self):
        self.assertTrue(one_way("Flughafen einfach"))
        self.assertTrue(one_way("", "one way"))
        self.assertFalse(one_way("Linz"))


class EventsTest(unittest.TestCase):
    def test_events_to_trips(self):
        ev = [{"start": "2026-11-12T14:00:00+01:00", "summary": "Linz 200 km", "location": "Linz, Hauptplatz"},
              {"start": "2026-11-11T07:30:00+01:00", "summary": "Kunde", "location": "Graz"},
              {"start": "2026-11-13", "summary": "Urlaub (ganztägig)"},                       # all day: left out
              {"start": "2026-11-09T07:00:00+01:00", "summary": "vorbei"},                    # past
              {"start": "2026-12-30T07:00:00+01:00", "summary": "zu weit"},                   # beyond 14 days
              "kaputt"]
        trips = trips_from_events(ev, NOW)
        self.assertEqual([t["title"] for t in trips], ["Kunde", "Linz 200 km"])
        self.assertEqual(trips[0]["location"], "Graz")
        self.assertIsNone(trips[0]["km_given"])
        self.assertEqual(trips[1]["km_given"], 200.0)

    def test_naive_time_is_local(self):
        trips = trips_from_events([{"start": "2026-11-11T07:30:00", "summary": "x"}], NOW)
        self.assertEqual(trips[0]["departure"].utcoffset(), timedelta(hours=1))


class KmTest(unittest.TestCase):
    def test_written_km_win(self):
        self.assertEqual(trip_km({"km_given": 200.0, "one_way": False}, 95.0), (200.0, "event"))

    def test_route_there_and_back(self):
        self.assertEqual(trip_km({"km_given": None, "one_way": False}, 95.3), (190.6, "route"))
        self.assertEqual(trip_km({"km_given": None, "one_way": True}, 95.3), (95.3, "route"))

    def test_nothing_known(self):
        self.assertEqual(trip_km({"km_given": None}, None), (None, None))

    def test_range(self):
        self.assertEqual(range_for_trip(200.0, 100.0), 230.0)
        self.assertEqual(range_for_trip(30.0, 100.0), 100.0)

    def test_region(self):
        self.assertEqual((waze_region("AT"), waze_region("us"), waze_region(None)), ("eu", "us", "eu"))


if __name__ == "__main__":
    unittest.main()
