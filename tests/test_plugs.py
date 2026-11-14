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


if __name__ == "__main__":
    unittest.main()
