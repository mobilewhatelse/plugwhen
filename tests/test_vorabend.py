"""Charge the evening before: tomorrow's later trip is charged in the standing time (vorabend.py)."""

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

import horizon  # noqa: E402
import messages  # noqa: E402
import vorabend as vb  # noqa: E402

TZ = timezone(timedelta(hours=1))
NOW = datetime(2026, 11, 18, 19, 10, tzinfo=TZ)


def hz(**over):
    h = {"lasts_until": "2026-11-19T07:00:00+01:00",
         "first_need": {"departure": "2026-11-19T20:00:00+01:00", "window_start": "2026-11-19T13:27:30+01:00",
                        "need_kwh": 2.3, "covered_by_sun": False}}
    h["first_need"].update(over)
    return h


class EveningBeforeTests(unittest.TestCase):
    def test_the_users_case(self):
        e = vb.evening_before(NOW, hz(), 81.0, 66.0, 0.9, True)
        self.assertIsNotNone(e)
        self.assertEqual(e.kwh, 2.3)
        self.assertAlmostEqual(e.target_soc, 81.0 + 2.3 * 0.9 / 66.0 * 100.0, delta=0.1)   # not cut by an everyday limit of 80 %
        self.assertEqual(e.by, datetime(2026, 11, 19, 7, 0, tzinfo=TZ))

    def test_no_charge_when_unplugged(self):
        self.assertIsNone(vb.evening_before(NOW, hz(), 81.0, 66.0, 0.9, False))

    def test_sun_covers_it(self):
        self.assertIsNone(vb.evening_before(NOW, hz(covered_by_sun=True), 81.0, 66.0, 0.9, True))

    def test_need_of_the_next_trip_is_the_normal_plan(self):
        h = hz()
        h["lasts_until"] = None
        self.assertIsNone(vb.evening_before(NOW, h, 81.0, 66.0, 0.9, True))

    def test_only_tomorrow(self):
        self.assertIsNone(vb.evening_before(NOW, hz(window_start="2026-11-20T13:00:00+01:00"), 81.0, 66.0, 0.9, True))

    def test_a_later_trip_today_is_charged_before_the_first_one_too(self):
        # 10:00, trips today at 14:00 and 21:00: the energy for the evening is charged before 14:00, not "at the latest" at 20:00
        now = datetime(2026, 11, 18, 10, 0, tzinfo=TZ)
        h = {"lasts_until": "2026-11-18T14:00:00+01:00",
             "first_need": {"departure": "2026-11-18T21:00:00+01:00", "window_start": "2026-11-18T18:00:00+01:00",
                            "need_kwh": 4.0, "covered_by_sun": False}}
        e = vb.evening_before(now, h, 60.0, 66.0, 0.9, True)
        self.assertEqual(e.by, datetime(2026, 11, 18, 14, 0, tzinfo=TZ))

    def test_gone_when_the_first_trip_is_past(self):
        self.assertIsNone(vb.evening_before(datetime(2026, 11, 19, 7, 0, tzinfo=TZ), hz(), 81.0, 66.0, 0.9, True))

    def test_what_the_plan_charges_anyway_is_not_doubled(self):
        e = vb.evening_before(NOW, hz(), 81.0, 66.0, 0.9, True, have_kwh=2.0)
        self.assertIsNone(e)   # 0.3 kWh left: not worth a charge
        e = vb.evening_before(NOW, hz(need_kwh=5.0), 81.0, 66.0, 0.9, True, have_kwh=2.0)
        self.assertEqual(e.kwh, 3.0)

    def test_capped_at_100(self):
        e = vb.evening_before(NOW, hz(need_kwh=30.0), 95.0, 66.0, 0.9, True)
        self.assertEqual(e.target_soc, 100.0)

    def test_earlier_learned_departure_decides_the_plan(self):
        # 18.11.2026 weekly full: horizon needs 13.1 kWh by Thu 07:00, the plan was made for the calendar trip Thu 20:00
        h = {"first_need": {"departure": "2026-11-19T07:00:00+01:00", "window_start": "2026-11-18T19:48:00+01:00",
                            "need_kwh": 13.1, "covered_by_sun": False}}
        cal = datetime(2026, 11, 19, 20, 0, tzinfo=TZ)
        e = vb.earlier_departure(NOW, h, cal, 81.0, 66.0, 0.9, True)
        self.assertEqual(e.by, datetime(2026, 11, 19, 7, 0, tzinfo=TZ))
        self.assertEqual(e.kwh, 13.1)
        self.assertIsNone(vb.earlier_departure(NOW, h, datetime(2026, 11, 19, 8, 0, tzinfo=TZ), 81.0, 66.0, 0.9, True))
        self.assertIsNone(vb.earlier_departure(NOW, h, cal, 81.0, 66.0, 0.9, False))

    def test_earlier_departure_kept_until_it_is_past(self):
        h = {"first_need": {"departure": "2026-11-19T07:00:00+01:00", "window_start": "2026-11-18T19:48:00+01:00",
                            "need_kwh": 13.1, "covered_by_sun": False}}
        cal = datetime(2026, 11, 19, 20, 0, tzinfo=TZ)
        for now in (datetime(2026, 11, 19, 5, 10, tzinfo=TZ), datetime(2026, 11, 19, 6, 55, tzinfo=TZ)):
            self.assertIsNotNone(vb.earlier_departure(now, h, cal, 81.0, 66.0, 0.9, True), now)
        self.assertIsNone(vb.earlier_departure(datetime(2026, 11, 19, 7, 0, tzinfo=TZ), h, cal, 81.0, 66.0, 0.9, True))

    def test_text_in_both_languages(self):
        e = vb.evening_before(NOW, hz(), 81.0, 66.0, 0.9, True)
        self.assertIn("Do 07:00", messages.evening_text("de", e.as_dict()))
        self.assertIn("Thu 20:00", messages.evening_text("en", e.as_dict()))


class WholeNightTests(unittest.TestCase):
    """Review 19.11.2026: every test above looks at 19:10 only. The charge must hold in every quarter hour from the evening to
    the first departure - after midnight the need arose "today" and was dropped, two hours before the first trip the deadline
    jumped back to the later one. The look-ahead is the real one (horizon.horizon_plan), nothing is made up."""

    CAP, CONS, EFF = 66.0, 0.2, 0.9
    MORNING, EVENING = datetime(2026, 11, 19, 7, 0, tzinfo=TZ), datetime(2026, 11, 19, 20, 0, tzinfo=TZ)

    def _night(self):
        t = datetime(2026, 11, 18, 17, 0, tzinfo=TZ)
        while t < self.MORNING:
            yield t
            t += timedelta(minutes=15)

    def _decide(self, now, soc, trips, departure, have):
        h = horizon.horizon_plan(now, soc / 100.0 * self.CAP, self.CAP, self.CONS, trips, None, 11.0, efficiency=self.EFF, pref_kw=4.0)
        e = vb.evening_before(now, h, soc, self.CAP, self.EFF, True, have)
        if e is not None:
            return e, have + e.kwh
        e = vb.earlier_departure(now, h, departure, soc, self.CAP, self.EFF, True)
        return e, (max(have, e.kwh) if e else have)

    def test_later_trip_tomorrow_holds_all_night(self):
        # the morning trip is covered, the evening trip (60 km, 160 km range wanted) is not: charged by 07:00, all night
        trips = [horizon.Trip(self.MORNING, 40, 100), horizon.Trip(self.EVENING, 60, 160, 60)]
        seen = set()
        for now in self._night():
            e, total = self._decide(now, 45.0, trips, self.MORNING, 0.0)
            self.assertIsNotNone(e, f"dropped at {now:%a %H:%M}")
            self.assertEqual(e.by, self.MORNING, now)
            self.assertEqual(e.for_departure, self.EVENING, now)
            seen.add(round(total, 1))
        self.assertEqual(len(seen), 1, f"the need changed during the night: {sorted(seen)}")

    def test_need_shrinks_only_by_what_was_charged(self):
        # the car charges through the night: the rest falls with the state of charge and ends at nothing, never jumps up or away
        trips = [horizon.Trip(self.MORNING, 40, 100), horizon.Trip(self.EVENING, 60, 160, 60)]
        soc, last = 45.0, None
        for now in self._night():
            e, total = self._decide(now, soc, trips, self.MORNING, 0.0)
            if e is None:
                self.assertLess(total, vb.MIN_KWH + 0.01)
                self.assertLess((last or 0.0), 2.0, f"dropped at {now:%a %H:%M} with {last} kWh open")
                break
            self.assertEqual(e.by, self.MORNING)
            if last is not None:
                self.assertLessEqual(total, last + 0.11, now)
            last = total
            soc = min(100.0, soc + 1.0 * self.EFF / self.CAP * 100.0)   # 4 kW for a quarter hour
        else:
            self.fail("the charge never ended")

    def test_full_charge_before_an_earlier_expected_departure_holds_all_night(self):
        # the plan's departure is the evening one, the look-ahead expects the car to leave at 07:00 and wants it full by then
        trips = [horizon.Trip(self.MORNING, 40, 330), horizon.Trip(self.EVENING, 60, 330, 60)]
        have = (100.0 - 81.0) / 100.0 * self.CAP / self.EFF
        for now in self._night():
            e, total = self._decide(now, 81.0, trips, self.EVENING, have)
            self.assertIsNotNone(e, f"deadline back to the evening at {now:%a %H:%M}")
            self.assertEqual(e.by, self.MORNING, now)
            self.assertAlmostEqual(total, have, delta=0.2)

    def test_nothing_two_days_ahead(self):
        # Tuesday evening, both trips on Thursday: that is the job of charging for several days, not of tonight
        trips = [horizon.Trip(self.MORNING, 40, 100), horizon.Trip(self.EVENING, 60, 160, 60)]
        e, _ = self._decide(datetime(2026, 11, 17, 19, 0, tzinfo=TZ), 45.0, trips, self.MORNING, 0.0)
        self.assertIsNone(e)


class SameDayTests(unittest.TestCase):
    """Week replay 18.11.2026, with the real look-ahead: only a later trip of the SAME day as the first one is charged ahead, all
    of them count, and the deadline is the first departure."""

    CAP, CONS, EFF = 66.0, 0.25, 0.9
    THU7, THU20 = datetime(2026, 11, 19, 7, 0, tzinfo=TZ), datetime(2026, 11, 19, 20, 0, tzinfo=TZ)
    FRI7 = datetime(2026, 11, 20, 7, 0, tzinfo=TZ)

    def _e(self, now, soc, trips, have=0.0):
        h = horizon.horizon_plan(now, soc / 100.0 * self.CAP, self.CAP, self.CONS, trips, None, 11.0, efficiency=self.EFF, pref_kw=4.0)
        return vb.evening_before(now, h, soc, self.CAP, self.EFF, True, have)

    def test_a_trip_of_the_next_day_is_not_charged_ahead(self):
        # Thursday afternoon, evening trip covered, Friday morning needs more: that is the night at home, not now
        now = datetime(2026, 11, 19, 16, 0, tzinfo=TZ)
        self.assertIsNone(self._e(now, 70.0, [horizon.Trip(self.THU20, 65, 165), horizon.Trip(self.FRI7, 27, 200)]))

    def test_no_rolling_night_after_night(self):
        # after midnight, first trip Saturday 13:00 covered, Sunday needs more: not now
        now = datetime(2026, 11, 21, 0, 0, tzinfo=TZ)
        sat13, sat20 = datetime(2026, 11, 21, 13, 0, tzinfo=TZ), datetime(2026, 11, 21, 20, 0, tzinfo=TZ)
        sun14 = datetime(2026, 11, 22, 14, 0, tzinfo=TZ)
        e = self._e(now, 75.0, [horizon.Trip(sat13, 33.5, 133), horizon.Trip(sat20, 52.8, 152.8), horizon.Trip(sun14, 13, 200)])
        self.assertTrue(e is None or e.for_departure.date() == sat13.date(), e)

    def test_a_small_need_of_the_first_trip_does_not_hide_the_evening(self):
        # 55 %: the morning trip needs 0.2 kWh, the evening trip much more - before, nothing was charged for the evening
        now = datetime(2026, 11, 18, 17, 0, tzinfo=TZ)
        e = self._e(now, 55.0, [horizon.Trip(self.THU7, 41.5, 141.5), horizon.Trip(self.THU20, 65, 165, 65)])
        self.assertIsNotNone(e)
        self.assertEqual(e.by, self.THU7)
        self.assertEqual(e.for_departure, self.THU20)
        after_morning = e.target_soc - 41.5 * self.CONS / self.CAP * 100.0
        self.assertGreaterEqual(after_morning, 165 * self.CONS / self.CAP * 100.0 - 1.0)

    def test_deadline_is_the_first_departure_also_when_two_are_covered(self):
        now = datetime(2026, 11, 18, 22, 0, tzinfo=TZ)
        noon = datetime(2026, 11, 19, 12, 0, tzinfo=TZ)
        e = self._e(now, 60.0, [horizon.Trip(self.THU7, 10, 110), horizon.Trip(noon, 10, 110), horizon.Trip(self.THU20, 80, 180)])
        self.assertIsNotNone(e)
        self.assertEqual(e.by, self.THU7)

    def test_never_more_than_the_battery_takes(self):
        now = datetime(2026, 11, 18, 22, 0, tzinfo=TZ)
        e = self._e(now, 90.0, [horizon.Trip(self.THU7, 40, 264), horizon.Trip(self.THU20, 60, 264)])
        self.assertTrue(e is None or e.target_soc <= 100.0)
        if e is not None:
            self.assertLessEqual(e.kwh, 10.0 / 100.0 * self.CAP / self.EFF + 0.1)


class SunShareTests(unittest.TestCase):
    """Review 20.11.2026: the gate looked at the grid share of the later trips, the amount at their whole need. A later trip covered
    mostly by the sun at home was charged in full from the grid the evening before."""

    @staticmethod
    def _h(first_need: float, later: dict) -> dict:
        return {"days": [{"departure": "2026-11-19T07:00:00+01:00", "need_kwh": first_need, "grid_kwh": first_need, "sun_direct_kwh": 0.0},
                         {"departure": "2026-11-19T20:00:00+01:00", **later}]}

    SUNNY = {"need_kwh": 6.0, "grid_kwh": 0.6, "sun_direct_kwh": 5.4}

    def test_only_the_grid_share_of_a_later_trip_is_charged_ahead(self):
        e = vb.evening_before(NOW, self._h(0.0, self.SUNNY), 60.0, 66.0, 0.9, True)
        self.assertIsNotNone(e)
        self.assertLessEqual(e.kwh, 0.6)
        self.assertEqual(e.for_departure, datetime(2026, 11, 19, 20, 0, tzinfo=TZ))

    def test_the_first_trips_own_need_still_counts_in_full(self):
        e = vb.evening_before(NOW, self._h(1.5, self.SUNNY), 60.0, 66.0, 0.9, True)
        self.assertLessEqual(e.kwh, 1.5 + 0.6)
        self.assertEqual(e.kwh, 2.1)

    def test_an_older_look_ahead_without_the_grid_share_charges_the_whole_need(self):
        e = vb.evening_before(NOW, self._h(0.0, {"need_kwh": 6.0}), 60.0, 66.0, 0.9, True)
        self.assertEqual(e.kwh, 6.0)

    def test_the_sun_alone_brings_it(self):
        self.assertIsNone(vb.evening_before(NOW, self._h(0.0, {**self.SUNNY, "grid_kwh": 0.4, "sun_direct_kwh": 5.6}),
                                            60.0, 66.0, 0.9, True))


class SameTripWindowTests(unittest.TestCase):
    def test_one_rule_with_the_look_ahead(self):
        """What is one trip and what are two: the window of the look-ahead, not a copy of it."""
        self.assertIs(vb.SAME_TRIP_WINDOW, horizon.SAME_TRIP_WINDOW)
        self.assertFalse(hasattr(vb, "SAME_TRIP"))


if __name__ == "__main__":
    unittest.main()
