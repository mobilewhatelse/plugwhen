"""Tests for the recorded plug-in times and the solar surplus."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

from inputs import merge_available, surplus_from_solar  # noqa: E402
from plugs import PlugLog  # noqa: E402

TZ = timezone(timedelta(hours=1))
D = datetime(2027, 1, 4, tzinfo=TZ)   # Monday


def at(day, h, m=0):
    return D + timedelta(days=day, hours=h, minutes=m)


class PlugLogTest(unittest.TestCase):
    def test_in_and_out(self):
        log = PlugLog()
        self.assertTrue(log.change(True, at(0, 19, 15)))
        self.assertTrue(log.open)
        self.assertFalse(log.change(True, at(0, 20)))         # already plugged in
        self.assertTrue(log.change(False, at(1, 7, 43)))
        self.assertEqual(log.intervals(), [(at(0, 19, 15), at(1, 7, 43))])

    def test_unknown_changes_nothing(self):
        log = PlugLog()
        log.change(True, at(0, 18))
        self.assertFalse(log.change(None, at(0, 22)))          # sensor unavailable for a moment
        self.assertTrue(log.open)

    def test_flicker_is_dropped(self):
        log = PlugLog()
        log.change(True, at(0, 18))
        log.change(False, at(0, 18, 1))
        self.assertEqual(log.items, [])

    def test_seed_only_when_empty(self):
        log = PlugLog()
        self.assertTrue(log.seed([(at(0, 18), True), (at(1, 7), False)]))
        self.assertFalse(log.seed([(at(2, 18), True)]))
        self.assertEqual(len(log.items), 1)

    def test_survives_saving(self):
        log = PlugLog()
        log.change(True, at(0, 18))
        again = PlugLog(log.items)
        self.assertTrue(again.open)
        self.assertEqual(again.intervals()[0][0], at(0, 18))

    def test_summary_counts_nights_not_days(self):
        log = PlugLog()
        for d in (0, 2, 4):                                      # every second night, like most people
            log.change(True, at(d, 19))
            log.change(False, at(d + 1, 7, 30))
        log.change(True, at(5, 14))                               # daytime with the sun
        log.change(False, at(5, 16))
        s = log.summary(at(6, 12), days=7)
        self.assertEqual(s["nights_plugged"], 3)
        self.assertEqual(s["plug_ins"], 4)
        self.assertEqual(s["typical_plug_in"], "19:00")
        self.assertFalse(s["plugged_now"])

    def test_trim(self):
        log = PlugLog([[at(-500, 18).isoformat(), at(-499, 7).isoformat()], [at(0, 18).isoformat(), None]])
        log.trim(at(1, 0))
        self.assertEqual(len(log.items), 1)


class SolarTest(unittest.TestCase):
    def test_surplus_is_forecast_minus_deduction(self):
        now = at(0, 11, 7)
        solar = {at(0, 10, 45): 5.0, at(0, 11): 4.0, at(0, 11, 15): 0.3}
        s = surplus_from_solar(solar, 0.5, now)
        self.assertEqual(s, {at(0, 11): 3.5})                     # the past and below-deduction quarters are gone

    def test_no_forecast_no_surplus(self):
        self.assertIsNone(surplus_from_solar(None, 0.5, at(0, 12)))
        self.assertIsNone(surplus_from_solar({at(0, 12): 0.4}, 0.5, at(0, 12)))

    def test_merge_takes_the_larger(self):
        self.assertEqual(merge_available({at(0, 12): 2.0}, None, {at(0, 12): 3.0, at(0, 13): 1.0}),
                         {at(0, 12): 3.0, at(0, 13): 1.0})
        self.assertIsNone(merge_available(None, None))



class ShareByHourTests(unittest.TestCase):
    """In which hours of the week the car is usually plugged in: the sun can only be planned for those."""

    def log(self, weeks: int = 4) -> PlugLog:
        log = PlugLog()
        for w in range(weeks):
            for d in range(5):                                   # Monday to Friday 18:00 until 07:00 the next morning
                log.change(True, at(7 * w + d, 18))
                log.change(False, at(7 * w + d + 1, 7))
            log.change(True, at(7 * w + 5, 10))                  # Saturday 10:00 until 16:30, every second week
            log.change(False, at(7 * w + 5, 16, 30) if w % 2 == 0 else at(7 * w + 5, 10, 30))
        return log

    def test_nights_are_plugged_weekday_afternoons_are_not(self):
        s = self.log().share_by_hour(at(28, 0))
        self.assertEqual(s[(0, 20)], 1.0)                        # Monday evening
        self.assertEqual(s[(2, 3)], 1.0)                         # Wednesday night
        self.assertEqual(s[(1, 15)], 0.0)                        # Tuesday afternoon: home, but not plugged in
        self.assertEqual(s[(0, 7)], 0.0)

    def test_a_habit_of_every_second_week_is_half(self):
        s = self.log().share_by_hour(at(28, 0))
        self.assertAlmostEqual(s[(5, 12)], 0.5)
        self.assertAlmostEqual(s[(5, 16)], 0.25)                 # half of the hour, every second week
        self.assertAlmostEqual(s[(5, 10)], 0.75)                 # the whole hour every second week, half of it in the others

    def test_too_little_recorded_says_nothing(self):
        self.assertIsNone(PlugLog().share_by_hour(at(28, 0)))
        self.assertIsNone(self.log(1).share_by_hour(at(8, 0)))

    def test_only_the_last_weeks_count_and_still_plugged_in_counts(self):
        log = PlugLog()
        log.change(True, at(0, 0))                               # plugged in for ten weeks without a break ...
        log.change(False, at(70, 0))
        s = log.share_by_hour(at(140, 0), weeks=8)                # ... but that was more than eight weeks ago
        self.assertEqual(max(s.values()), 0.0)
        log.change(True, at(139, 12))
        self.assertGreater(log.share_by_hour(at(140, 0), weeks=8)[(at(139, 13).weekday(), 13)], 0.0)


if __name__ == "__main__":
    unittest.main()
