"""Tests for the optional inputs and the warning texts."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

from inputs import availability_from_attributes, departure_from_state, floor_quarter, load_from_hours  # noqa: E402
from messages import notice_text  # noqa: E402
from notice import Notice  # noqa: E402

TZ = timezone(timedelta(hours=1))
NOW = datetime(2027, 1, 12, 20, 10, tzinfo=TZ)


class LoadTest(unittest.TestCase):
    def test_every_hour_becomes_four_quarters(self):
        q = load_from_hours([{"t": "2027-01-12T21:00:00+01:00", "typical": 1.0, "high": 2.5}], TZ)
        self.assertEqual(len(q), 4)
        self.assertEqual([x["t"].minute for x in q], [0, 15, 30, 45])
        self.assertTrue(all(x["high"] == 2.5 and x["typical"] == 1.0 for x in q))

    def test_other_time_zone_is_the_same_instant(self):
        q = load_from_hours([{"t": "2027-01-12T20:00:00+00:00", "typical": 1.0, "high": 2.0}], TZ)
        self.assertEqual(q[0]["t"], datetime(2027, 1, 12, 21, 0, tzinfo=TZ))

    def test_broken_entries_are_skipped(self):
        q = load_from_hours([{"t": "kaputt", "high": 1}, {"t": "2027-01-12T21:00:00+01:00"}, "x", {"t": "2027-01-12T22:00:00+01:00", "high": 3}], TZ)
        self.assertEqual(len(q), 4)
        self.assertEqual(q[0]["typical"], 1.5)       # typical missing: half of high
        self.assertEqual(load_from_hours(None, TZ), [])


class AvailabilityTest(unittest.TestCase):
    def attrs(self, **kw):
        base = {"schema": 1, "valid_until": (NOW + timedelta(hours=6)).isoformat(),
                "forecast": [{"start": "2027-01-12T23:00:00+01:00", "end": "2027-01-13T01:00:00+01:00", "kw": 4.0}]}
        base.update(kw)
        return base

    def test_expands_to_quarters(self):
        a = availability_from_attributes(self.attrs(), NOW)
        self.assertEqual(len(a), 8)
        self.assertEqual(a[datetime(2027, 1, 12, 23, 0, tzinfo=TZ)], 4.0)
        self.assertNotIn(datetime(2027, 1, 13, 1, 0, tzinfo=TZ), a)

    def test_expired_data_is_ignored(self):
        self.assertIsNone(availability_from_attributes(self.attrs(valid_until=(NOW - timedelta(minutes=1)).isoformat()), NOW))

    def test_wrong_schema_and_garbage_are_ignored(self):
        self.assertIsNone(availability_from_attributes(self.attrs(schema=2), NOW))
        self.assertIsNone(availability_from_attributes(self.attrs(forecast="x"), NOW))
        self.assertIsNone(availability_from_attributes(None, NOW))
        self.assertIsNone(availability_from_attributes(self.attrs(forecast=[{"start": "x", "end": "y", "kw": 1}]), NOW))

    def test_no_valid_until_means_always_valid(self):
        a = self.attrs()
        del a["valid_until"]
        self.assertIsNotNone(availability_from_attributes(a, NOW))

    def test_zero_or_negative_power_is_dropped(self):
        a = self.attrs(forecast=[{"start": "2027-01-12T23:00:00+01:00", "end": "2027-01-13T00:00:00+01:00", "kw": 0}])
        self.assertIsNone(availability_from_attributes(a, NOW))

    def test_overlaps_keep_the_larger_value(self):
        a = self.attrs(forecast=[{"start": "2027-01-12T23:00:00+01:00", "end": "2027-01-13T00:00:00+01:00", "kw": 2.0},
                                 {"start": "2027-01-12T23:30:00+01:00", "end": "2027-01-13T00:30:00+01:00", "kw": 5.0}])
        r = availability_from_attributes(a, NOW)
        self.assertEqual(r[datetime(2027, 1, 12, 23, 15, tzinfo=TZ)], 2.0)
        self.assertEqual(r[datetime(2027, 1, 12, 23, 30, tzinfo=TZ)], 5.0)

    def test_floor_quarter(self):
        self.assertEqual(floor_quarter(datetime(2027, 1, 12, 23, 59, 30, tzinfo=TZ)), datetime(2027, 1, 12, 23, 45, tzinfo=TZ))


class DepartureTest(unittest.TestCase):
    def test_time_later_today(self):
        self.assertEqual(departure_from_state("22:00:00", NOW), datetime(2027, 1, 12, 22, 0, tzinfo=TZ))

    def test_time_already_gone_means_tomorrow(self):
        self.assertEqual(departure_from_state("07:00", NOW), datetime(2027, 1, 13, 7, 0, tzinfo=TZ))

    def test_date_time(self):
        self.assertEqual(departure_from_state("2027-01-14 07:30:00", NOW), datetime(2027, 1, 14, 7, 30, tzinfo=TZ))
        self.assertEqual(departure_from_state("2027-01-14T07:30:00+01:00", NOW), datetime(2027, 1, 14, 7, 30, tzinfo=TZ))

    def test_past_and_garbage(self):
        self.assertIsNone(departure_from_state("2027-01-10 07:30:00", NOW))
        for bad in ("unknown", "unavailable", "", None, "abc", "25:99"):
            self.assertIsNone(departure_from_state(bad, NOW), bad)


class MessageTest(unittest.TestCase):
    def n(self, kind, **kw):
        base = dict(kind=kind, shortfall_kwh=5.4, soc=38.0, target_soc=45.3, km=136.0, hours_left=11.0, max_possible_kwh=None)
        base.update(kw)
        return Notice(**base)

    DEP = datetime(2027, 1, 13, 7, 0, tzinfo=TZ)

    def test_german_plug_in(self):
        title, msg = notice_text("de", self.n("plug_in"), "Mercedes", self.DEP)
        self.assertEqual(title, "Mercedes: morgen nicht bereit")
        self.assertIn("Bitte anstecken", msg)
        self.assertIn("38 %", msg)
        self.assertIn("07:00", msg)
        self.assertIn("5.4 kWh", msg)

    def test_english_fallback_for_other_languages(self):
        title, msg = notice_text("fr", self.n("plug_in"), "Car", self.DEP)
        self.assertEqual(title, "Car: not ready for tomorrow")
        self.assertIn("Please plug in", msg)

    def test_title_today_tomorrow_or_weekday(self):
        dep = datetime(2026, 11, 16, 22, 0, tzinfo=TZ)
        self.assertEqual(notice_text("de", self.n("plug_in"), "Mercedes", dep, dep - timedelta(hours=10))[0],
                         "Mercedes: heute nicht bereit")
        self.assertEqual(notice_text("de", self.n("plug_in"), "Mercedes", dep, dep - timedelta(days=1))[0],
                         "Mercedes: morgen nicht bereit")
        self.assertEqual(notice_text("en", self.n("plug_in"), "Car", dep, dep - timedelta(days=2))[0], "Car: not ready for Mon")
        self.assertEqual(notice_text("de", self.n("plug_in"), "Mercedes", dep, dep - timedelta(days=3))[0],
                         "Mercedes: nicht bereit für Mo")

    def test_not_reachable_and_unplugged_still_asks_to_plug_in(self):
        _, msg = notice_text("de", self.n("not_reachable", plugged_out=True), "Mercedes", self.DEP)
        self.assertIn("nicht erreichbar", msg)
        self.assertIn("trotzdem anstecken", msg)
        _, msg = notice_text("de", self.n("not_reachable"), "Mercedes", self.DEP)
        self.assertNotIn("anstecken", msg)

    def test_evening_reminder_text(self):
        for lang, word in (("de", "Erinnerung"), ("en", "Reminder")):
            for kind in ("plug_in", "not_reachable", "too_late"):
                _, msg = notice_text(lang, self.n(kind, plugged_out=True, max_possible_kwh=3.0), "Car", self.DEP, reminder=True)
                self.assertIn(word, msg)
                self.assertNotIn("{", msg)
        _, msg = notice_text("de", self.n("not_reachable", plugged_out=True), "Car", self.DEP, reminder=True)
        self.assertIn("trotzdem anstecken", msg)

    def test_every_kind_has_a_text_in_both_languages(self):
        for lang in ("de", "en"):
            for kind in ("plug_in", "low", "too_late", "not_reachable"):
                _, msg = notice_text(lang, self.n(kind, max_possible_kwh=3.0), "Car", None)
                self.assertTrue(msg and "{" not in msg, (lang, kind, msg))

    def test_too_late_names_the_possible_energy(self):
        _, msg = notice_text("en", self.n("too_late", max_possible_kwh=3.04), "Car", self.DEP)
        self.assertIn("3.0 kWh", msg)

    def test_unknown_soc_and_departure(self):
        _, msg = notice_text("de", self.n("low", soc=None), "Car", None)
        self.assertIn("?", msg)
        self.assertIn("nächsten Abfahrt", msg)


if __name__ == "__main__":
    unittest.main()
