"""Once a week full: day choice (sun, no PV, once per week), when it counts, done."""

from __future__ import annotations

import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

import vollladen as vl  # noqa: E402

TZ = timezone(timedelta(hours=1))
FRI = date(2026, 11, 20)   # a Friday
SAT, SUN, MON = FRI + timedelta(days=1), FRI + timedelta(days=2), FRI + timedelta(days=3)


def sun(day: date, kw: float, hours=range(10, 15)) -> dict[datetime, float]:
    return {datetime(day.year, day.month, day.day, h, m, tzinfo=TZ): kw for h in hours for m in (0, 15, 30, 45)}


class DayBarTests(unittest.TestCase):
    """Since the day bar the allowed days are the ticked weekdays (0=Monday)."""

    MON0 = FRI - timedelta(days=4)   # Monday of that week

    def test_a_single_weekday(self):
        self.assertEqual(vl.choose_day(self.MON0, frozenset({2}), None, None), self.MON0 + timedelta(days=2))   # Wednesday

    def test_several_days_the_sunniest(self):
        wed, thu = self.MON0 + timedelta(days=2), self.MON0 + timedelta(days=3)
        self.assertEqual(vl.choose_day(self.MON0, frozenset({2, 3}), {**sun(wed, 1.0), **sun(thu, 3.0)}, None), thu)

    def test_no_day_ticked_means_no_full_charge(self):
        self.assertIsNone(vl.choose_day(self.MON0, frozenset(), None, None))

    def test_a_day_already_past_this_week_waits_for_next_week(self):
        self.assertIsNone(vl.choose_day(FRI, frozenset({0}), None, None))   # Monday ticked, it is Friday

    def test_the_former_selection_is_carried_over(self):
        self.assertEqual(vl.days_of("weekend"), frozenset({5, 6}))
        self.assertEqual(vl.days_of("friday_sunday"), frozenset({4, 5, 6}))
        self.assertEqual(vl.days_of("any_day"), frozenset(range(7)))
        self.assertIsNone(vl.days_of(None))
        self.assertIsNone(vl.days_of("unavailable"))

    def test_default_is_the_weekend(self):
        self.assertEqual(vl.DEFAULT_DAY_SET, frozenset({5, 6}))
        self.assertEqual(vl.days_text(frozenset({6, 5})), "Sa,So")


class ChooseDayTests(unittest.TestCase):
    def test_no_pv_first_allowed_day(self):
        self.assertEqual(vl.choose_day(FRI, "weekend", None, None), SAT)
        self.assertEqual(vl.choose_day(FRI, "weekend", {}, None), SAT)

    def test_sunnier_day_wins(self):
        self.assertEqual(vl.choose_day(FRI, "weekend", {**sun(SAT, 1.0), **sun(SUN, 4.0)}, None), SUN)
        self.assertEqual(vl.choose_day(FRI, "weekend", {**sun(SAT, 4.0), **sun(SUN, 1.0)}, None), SAT)

    def test_equal_sun_earlier_day(self):
        self.assertEqual(vl.choose_day(FRI, "weekend", {**sun(SAT, 2.0), **sun(SUN, 2.0)}, None), SAT)

    def test_only_this_week(self):
        self.assertEqual(vl.choose_day(SUN, "weekend", None, None), SUN)
        self.assertEqual(vl.choose_day(SUN, "saturday", None, None), None)   # Saturday is over, next week again
        self.assertEqual(vl.choose_day(MON, "saturday", None, None), SAT + timedelta(days=7))

    def test_once_a_week(self):
        self.assertIsNone(vl.choose_day(SUN, "weekend", None, vl.week_key(SAT)))
        self.assertEqual(vl.choose_day(MON + timedelta(days=4), "weekend", None, vl.week_key(SAT)), SAT + timedelta(days=7))

    def test_any_day_with_sun(self):
        wed = MON + timedelta(days=2)
        self.assertEqual(vl.choose_day(MON, "any_day", {**sun(MON, 0.5), **sun(wed, 3.0)}, None), wed)

    def test_unknown_setting_falls_back(self):
        self.assertEqual(vl.choose_day(FRI, "nonsense", None, None), SAT)


class AppliesTests(unittest.TestCase):
    def test_departure_after_the_day(self):
        now = datetime(2026, 11, 20, 18, 0, tzinfo=TZ)
        self.assertTrue(vl.applies(now, datetime(2026, 11, 23, 7, 0, tzinfo=TZ), SAT))   # Friday evening to Monday: includes Saturday
        self.assertFalse(vl.applies(now, datetime(2026, 11, 20, 22, 0, tzinfo=TZ), SAT))  # back before Saturday
        self.assertTrue(vl.applies(datetime(2026, 11, 21, 9, 0, tzinfo=TZ), datetime(2026, 11, 21, 17, 0, tzinfo=TZ), SAT))

    def test_without_departure_by_the_evening(self):
        self.assertTrue(vl.applies(datetime(2026, 11, 21, 9, 0, tzinfo=TZ), None, SAT))
        self.assertFalse(vl.applies(datetime(2026, 11, 21, 21, 0, tzinfo=TZ), None, SAT))
        self.assertFalse(vl.applies(datetime(2026, 11, 20, 9, 0, tzinfo=TZ), None, SAT))
        self.assertEqual(vl.evening(SAT, TZ).hour, vl.EVENING_H)

    def test_no_day(self):
        self.assertFalse(vl.applies(datetime(2026, 11, 21, 9, 0, tzinfo=TZ), None, None))


class ReachedTests(unittest.TestCase):
    def test_margin(self):
        self.assertTrue(vl.reached(99.0, 100.0))
        self.assertFalse(vl.reached(97.0, 100.0))
        self.assertFalse(vl.reached(None, 100.0))
        self.assertEqual(vl.week_key(SAT), vl.week_key(SUN))
        self.assertNotEqual(vl.week_key(SUN), vl.week_key(MON))


if __name__ == "__main__":
    unittest.main()
