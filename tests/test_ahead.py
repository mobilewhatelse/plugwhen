"""Tests for the heads-up 'tomorrow charging is needed' (the look-ahead notice) and its texts."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

from horizon import Trip, horizon_plan, with_calendar, without_same_trip  # noqa: E402
from messages import ahead_text  # noqa: E402
from notice import ahead_key, check_ahead, tip_ahead  # noqa: E402

TZ = timezone(timedelta(hours=1))
SAT = datetime(2027, 1, 9, 9, 0, tzinfo=TZ)


def at(day, h, m=0):
    return SAT.replace(hour=0, minute=0) + timedelta(days=day, hours=h, minutes=m)


def week():
    return [Trip(at(0, 13), 22, 100), Trip(at(1, 13), 10, 100), Trip(at(2, 8), 78, 100), Trip(at(3, 7), 41, 100), Trip(at(4, 7), 67, 100)]


def sun():
    return {at(d, h) + timedelta(minutes=m): 4.0 for d in (0, 1) for h in range(10, 13) for m in (0, 15, 30, 45)}


def horizon(**kw):
    args = dict(now=SAT, soc_kwh=30.0, capacity_kwh=60.0, consumption=0.2, trips=week(), sun_kw=sun(), max_kw=11.0, pref_kw=4.0)
    args.update(kw)
    return horizon_plan(**args)


class AheadTest(unittest.TestCase):
    def test_on_friday_evening_it_recommends_charging_with_the_sun_on_saturday(self):
        friday = at(-1, 19, 30)
        h = horizon(now=friday, trips=[Trip(at(0, 13), 22, 100), *week()[1:]], sun_kw=sun())
        a = check_ahead(h, friday, 19)
        self.assertIsNotNone(a)
        self.assertEqual(a.kind, "sun")
        self.assertEqual(a.day, SAT.date())
        self.assertGreaterEqual(a.kwh, 2)
        self.assertEqual(ahead_key(a), f"ahead:{SAT.date().isoformat()}:sun")

    def test_without_sun_it_says_when_charging_is_needed_tomorrow_and_the_latest_start(self):
        monday_evening_before = at(1, 19, 30)                                       # Sunday evening
        h = horizon(now=monday_evening_before, sun_kw=None, soc_kwh=23.6, trips=week()[2:])
        a = check_ahead(h, monday_evening_before, 19)
        self.assertIsNotNone(a)
        self.assertEqual(a.kind, "charge")
        self.assertEqual(a.day, (monday_evening_before + timedelta(days=1)).date())
        self.assertGreater(a.latest_start, a.latest_start_pref)                     # at full power it can start later than at 4 kW
        self.assertLess(a.latest_start_pref, a.departure)

    def test_tip_for_the_dashboard_at_any_hour_and_still_on_the_day_itself(self):
        friday_noon = at(-1, 12)
        h = horizon(now=friday_noon, trips=[Trip(at(0, 13), 22, 100), *week()[1:]], sun_kw=sun())
        self.assertIsNone(check_ahead(h, friday_noon, 19))                         # no notification before the evening hour
        a = tip_ahead(h, friday_noon)                                              # but the dashboard shows it already
        self.assertIsNotNone(a)
        self.assertEqual((a.kind, a.day), ("sun", SAT.date()))
        self.assertTrue(ahead_text("de", a, "Auto", 4.0, today=friday_noon.date())[1].startswith("Morgen (Sa) lohnt Vorladen mit Sonne"))
        morning = at(0, 8)                                                         # Saturday morning: the window is still to come
        h = horizon(now=morning, trips=[Trip(at(0, 13), 22, 100), *week()[1:]], sun_kw=sun())
        a = tip_ahead(h, morning)
        self.assertEqual((a.kind, a.day), ("sun", SAT.date()))
        self.assertTrue(ahead_text("de", a, "Auto", 4.0, today=morning.date())[1].startswith("Heute lohnt Vorladen mit Sonne"))
        self.assertTrue(ahead_text("en", a, "Car", 4.0, today=morning.date())[1].startswith("Today it pays"))
        self.assertNotEqual(tip_ahead(h, at(0, 14)).day if tip_ahead(h, at(0, 14)) else None, SAT.date())  # window over: not today
        self.assertIsNone(tip_ahead(None, morning))
        self.assertIsNone(tip_ahead({"status": "no_data"}, morning))

    def test_not_before_the_evening_hour(self):
        early = at(-1, 12)
        h = horizon(now=early, trips=[Trip(at(0, 13), 22, 100), *week()[1:]])
        self.assertIsNone(check_ahead(h, early, 19))

    def test_nothing_to_announce_when_nothing_is_needed_or_it_is_unknown(self):
        self.assertIsNone(check_ahead(None, SAT, 0))
        self.assertIsNone(check_ahead({"status": "unknown_soc"}, SAT, 0))
        full = horizon(soc_kwh=60.0, trips=week()[:2])
        self.assertIsNone(check_ahead(full, at(-1, 20), 19))

    def test_charging_that_has_to_happen_today_is_not_a_heads_up(self):
        h = horizon(sun_kw=None, soc_kwh=5.0, trips=[Trip(at(0, 20), 20, 100)])     # the window begins now, today
        self.assertIsNone(check_ahead(h, SAT.replace(hour=19), 0))

    def test_texts_in_both_languages(self):
        friday = at(-1, 19, 30)
        h = horizon(now=friday, trips=[Trip(at(0, 13), 22, 100), *week()[1:]])
        sun_a = check_ahead(h, friday, 19)
        title, msg = ahead_text("de", sun_a, "Auto")
        self.assertIn("morgen laden", title)
        self.assertIn("Sa", msg)
        self.assertIn("Sonne", msg)
        title_en, msg_en = ahead_text("en", sun_a, "Car")
        self.assertIn("charge tomorrow", title_en)
        self.assertIn("Sat", msg_en)
        h2 = horizon(now=at(1, 19, 30), sun_kw=None, soc_kwh=23.6, trips=week()[2:])
        charge_a = check_ahead(h2, at(1, 19, 30), 19)
        _, m = ahead_text("de", charge_a, "Auto", pref_kw=4.0)
        self.assertIn("Spätestens ab", m)
        self.assertIn("4 kW", m)
        _, m2 = ahead_text("en", charge_a, "Car", pref_kw=4.0)
        self.assertIn("Latest start", m2)
        from notice import Ahead
        bare = Ahead("charge", SAT.date(), at(2, 7), 5.0, None, None)
        self.assertIn("Morgen", ahead_text("de", bare, "Auto")[1])


class SameTripTest(unittest.TestCase):
    def test_a_calendar_trip_close_to_the_learned_departure_is_the_same_trip(self):
        learned = [Trip(at(2, 7, 30), 40, 100)]
        self.assertEqual(without_same_trip(learned, at(2, 8, 45)), [])

    def test_a_trip_at_another_time_of_the_day_comes_on_top(self):
        learned = [Trip(at(2, 7, 30), 40, 100)]
        self.assertEqual(without_same_trip(learned, at(2, 17)), learned)

    def test_only_the_trip_of_the_same_time_goes(self):
        a, b = Trip(at(2, 7, 30), 40, 100), Trip(at(2, 17, 0), 20, 100)
        self.assertEqual(without_same_trip([a, b], at(2, 17, 30)), [a])

    def test_two_calendar_trips_close_together_both_stay(self):
        # 11.11.2026 live: "Testfahrt 330 km" 07:00 and "Büro 100 km" 07:30 - the office entry pushed the long trip out
        learned = [Trip(at(2, 7, 30), 40, 100)]
        long_trip, office = Trip(at(2, 7, 0), 330, 379.5), Trip(at(2, 7, 30), 100, 115)
        self.assertEqual(with_calendar(learned, [office, long_trip]), [long_trip, office])

    def test_the_learned_departure_goes_and_a_far_calendar_trip_comes_on_top(self):
        learned = [Trip(at(2, 7, 30), 40, 100), Trip(at(3, 7, 30), 40, 100)]
        evening = Trip(at(2, 17, 0), 60, 100)
        self.assertEqual(with_calendar(learned, [evening]), [learned[0], evening, learned[1]])
        late = Trip(at(2, 8, 0), 60, 100)
        self.assertEqual(with_calendar(learned, [late]), [late, learned[1]])


if __name__ == "__main__":
    unittest.main()
