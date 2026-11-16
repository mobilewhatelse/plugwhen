"""Charging for several days at once: must and comfort, start below must and fill to comfort, the sun first."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

import voraus as vo  # noqa: E402
from horizon import Trip  # noqa: E402

TZ = timezone(timedelta(hours=1))
MON_EVENING = datetime(2026, 11, 16, 19, 0, tzinfo=TZ)
TUE_7 = datetime(2026, 11, 17, 7, 0, tzinfo=TZ)
CAP, CONS, EFF, RESERVE = 66.0, 0.21, 0.9, 100.0


def week(*highs: float, reserve: float = RESERVE) -> list[Trip]:
    """One trip a day from Tuesday 07:00: typical = 80 % of the high value, target = high + reserve (reserve left after the trip)."""
    return [Trip(TUE_7 + timedelta(days=i), h * 0.8, h + reserve, h) for i, h in enumerate(highs)]


def soc_for(km: float) -> float:
    return km * CONS / CAP * 100.0


def ahead(trips, soc, must, days=3, cap=80.0, filling=False, plugged=True, sun=None, held=None, share=None):
    return vo.look_ahead(MON_EVENING, trips, TUE_7, soc, must, days=days, cap_soc=cap, capacity_kwh=CAP, consumption=CONS,
                         efficiency=EFF, filling=filling, plugged=plugged, sun_kw=sun, max_kw=11.0, held_soc=held,
                         plug_share=share)


class ComfortTests(unittest.TestCase):
    def test_three_days_are_the_trips_before_plus_the_last_ones_target(self):
        trips = week(60, 136, 46, 80)
        self.assertEqual(len(vo.trips_ahead(trips, TUE_7, 3)), 3)
        self.assertAlmostEqual(vo.comfort_km(vo.trips_ahead(trips, TUE_7, 3)), 60 + 136 + 46 + RESERVE)

    def test_a_long_trip_in_the_middle_decides_itself(self):
        # Wednesday needs a full battery (target 400 km) but is expected to use little; Thursday is a normal day
        trips = [Trip(TUE_7, 48.0, 160.0, 60.0), Trip(TUE_7 + timedelta(days=1), 40.0, 400.0, 46.0),
                 Trip(TUE_7 + timedelta(days=2), 37.0, 146.0, 46.0)]
        self.assertAlmostEqual(vo.comfort_km(trips), 60 + 400)       # not 60 + 46 + 146: Wednesday would start too low
        self.assertAlmostEqual(vo.comfort_km(trips[:1]), 160.0)
        self.assertEqual(vo.comfort_km([]), 0.0)

    def test_one_day_is_the_next_trip_alone(self):
        a = ahead(week(60, 136, 46), 30.0, soc_for(160), days=1)
        self.assertEqual((a.target_soc, a.filling), (round(soc_for(160), 1), False))

    def test_a_second_trip_on_the_same_day_counts(self):
        trips = week(60, 136) + [Trip(TUE_7 + timedelta(hours=13), 20.0, 120.0, 25.0)]
        self.assertEqual(len(vo.trips_ahead(trips, TUE_7, 1)), 2)

    def test_the_everyday_limit_caps_it_but_never_below_must(self):
        a = ahead(week(60, 136, 146, 80), 30.0, soc_for(160))
        self.assertEqual(a.comfort_soc, 80.0)
        a = ahead(week(250, 60), 30.0, 100.0)           # a long trip: must is above the limit
        self.assertEqual((a.target_soc, a.comfort_soc), (100.0, 100.0))


class StartAndFillTests(unittest.TestCase):
    def setUp(self):
        self.trips = week(60, 46, 59)                    # comfort: 60 + 46 + 59 + 100 = 265 km
        self.must = soc_for(160)                         # 50.9 %
        self.comfort = round(soc_for(265), 1)            # 84.3 % -> capped at 80

    def test_below_must_a_fill_to_comfort_starts(self):
        a = ahead(self.trips, 40.0, self.must)
        self.assertTrue(a.filling)
        self.assertEqual(a.target_soc, 80.0)

    def test_between_must_and_comfort_nothing_starts(self):
        # a car that is always plugged in must not top up a few kWh every night
        a = ahead(self.trips, 60.0, self.must)
        self.assertFalse(a.filling)
        self.assertEqual(a.target_soc, round(self.must, 1))

    def test_a_running_fill_goes_on_until_comfort(self):
        a = ahead(self.trips, 60.0, self.must, filling=True)
        self.assertTrue(a.filling)
        self.assertEqual(a.target_soc, 80.0)
        a = ahead(self.trips, 79.2, self.must, filling=True)
        self.assertFalse(a.filling)

    def test_unplugged_ends_the_fill_unless_below_must(self):
        self.assertFalse(ahead(self.trips, 60.0, self.must, filling=True, plugged=False).filling)
        a = ahead(self.trips, 40.0, self.must, plugged=False)   # what will be charged once plugged in
        self.assertTrue(a.filling)

    def test_unknown_state_of_charge_only_must(self):
        a = ahead(self.trips, None, self.must, filling=True)
        self.assertEqual((a.target_soc, a.filling), (round(self.must, 1), False))


class HeldTargetTests(unittest.TestCase):
    """Review of 0.10: the forecast, the weather and the learning move the target a little all the time; every new value makes
    a wallbox with a "next trip" mode stop and plan again."""

    def setUp(self):
        self.trips = week(60, 46, 40)                    # comfort 60 + 46 + 140 = 246 km = 78.3 %
        self.must = soc_for(160)

    def test_a_running_fill_keeps_its_target_against_small_changes(self):
        a = ahead(self.trips, 60.0, self.must, filling=True, held=76.0)
        self.assertEqual((a.target_soc, a.filling), (76.0, True))

    def test_a_real_change_is_taken(self):
        a = ahead(self.trips, 60.0, self.must, filling=True, held=60.0)   # e.g. a trip was added to the calendar
        self.assertEqual(a.target_soc, 78.3)

    def test_never_below_must_and_only_while_filling(self):
        a = ahead(self.trips, 40.0, 77.0, filling=True, held=74.0)
        self.assertGreaterEqual(a.target_soc, 77.0)
        a = ahead(self.trips, 40.0, self.must, filling=False, held=76.0)   # a new fill computes its own target
        self.assertEqual(a.target_soc, 78.3)


class NeverBelowMustTests(unittest.TestCase):
    def test_whatever_the_inputs_the_target_is_at_least_must(self):
        """The next trip is what must never be lost: comfort, the limit and the sun only ever add to it."""
        import random

        rnd = random.Random(1611)
        for _ in range(3000):
            n = rnd.randint(0, 6)
            trips = [Trip(TUE_7 + timedelta(days=i, hours=rnd.choice((0, 0, 5, 13))), rnd.uniform(0, 250),
                          rnd.uniform(50, 450), rnd.choice((None, rnd.uniform(0, 300)))) for i in range(n)]
            must = rnd.uniform(20, 100)
            soc = rnd.choice((None, rnd.uniform(0, 100)))
            sun = {TUE_7.replace(hour=0) + timedelta(days=d, hours=h, minutes=m): rnd.uniform(0, 12)
                   for d in range(3) for h in range(8, 17) for m in (0, 15, 30, 45)} if rnd.random() < 0.5 else None
            a = vo.look_ahead(MON_EVENING, trips, TUE_7, soc, must, days=rnd.randint(1, 7), cap_soc=rnd.uniform(50, 100),
                              capacity_kwh=CAP, consumption=rnd.uniform(0.12, 0.3), efficiency=rnd.uniform(0.7, 0.95),
                              filling=rnd.random() < 0.5, plugged=rnd.choice((True, False, None)), sun_kw=sun,
                              held_soc=rnd.choice((None, rnd.uniform(20, 100))))
            self.assertGreaterEqual(a.target_soc, round(must, 1) - 0.05, (trips, must, soc))
            self.assertLessEqual(a.target_soc, 100.0)


class SunTests(unittest.TestCase):
    def sun(self, day: int, kw: float, hours=range(10, 16)) -> dict:
        d = TUE_7.replace(hour=0) + timedelta(days=day)
        return {d + timedelta(hours=h, minutes=m): kw for h in hours for m in (0, 15, 30, 45)}

    def test_what_the_sun_brings_at_home_between_the_trips_is_left_to_the_sun(self):
        # Saturday-like: the car comes home early (short trip), six hours of 5 kW sun before the next departure
        trips = [Trip(TUE_7, 10.0, 160.0, 12.0), Trip(TUE_7 + timedelta(days=1), 40.0, 150.0, 50.0),
                 Trip(TUE_7 + timedelta(days=2), 40.0, 150.0, 50.0)]
        no_sun = ahead(trips, 30.0, soc_for(160))
        with_sun = ahead(trips, 30.0, soc_for(160), sun=self.sun(0, 5.0, range(11, 17)))
        self.assertEqual(no_sun.sun_kwh, 0.0)
        self.assertGreater(with_sun.sun_kwh, 15.0)
        self.assertLess(with_sun.target_soc, no_sun.target_soc)
        self.assertGreaterEqual(with_sun.target_soc, round(soc_for(160), 1))   # must is always charged

    def home_early(self):
        return [Trip(TUE_7, 10.0, 160.0, 12.0), Trip(TUE_7 + timedelta(days=1), 40.0, 150.0, 50.0),
                Trip(TUE_7 + timedelta(days=2), 40.0, 150.0, 50.0)]

    def test_only_the_hours_the_car_is_usually_plugged_in_count(self):
        # home from eleven, sun from eleven to five - but the car is plugged in from three on (learned)
        sun = self.sun(0, 5.0, range(11, 17))
        wd = TUE_7.weekday()
        home = ahead(self.home_early(), 30.0, soc_for(160), sun=sun)
        from_three = ahead(self.home_early(), 30.0, soc_for(160), sun=sun, share={(wd, h): 1.0 for h in (15, 16)})
        never = ahead(self.home_early(), 30.0, soc_for(160), sun=sun, share={})
        self.assertEqual((home.sun_basis, from_three.sun_basis), ("home", "plug_times"))
        self.assertAlmostEqual(from_three.sun_kwh, round(home.sun_kwh / 3, 1), delta=0.2)   # two of the six hours
        self.assertEqual(never.sun_kwh, 0.0)
        self.assertGreater(never.target_soc, home.target_soc)    # nothing is left to a sun that would not reach the car

    def test_plugged_in_on_half_of_the_days_counts_half(self):
        sun = self.sun(0, 5.0, range(11, 17))
        wd = TUE_7.weekday()
        full = ahead(self.home_early(), 30.0, soc_for(160), sun=sun, share={(wd, h): 1.0 for h in range(24)})
        half = ahead(self.home_early(), 30.0, soc_for(160), sun=sun, share={(wd, h): 0.5 for h in range(24)})
        self.assertAlmostEqual(half.sun_kwh, full.sun_kwh / 2, delta=0.1)

    def test_without_a_forecast_nothing_is_said_about_the_sun(self):
        self.assertIsNone(ahead(self.home_early(), 30.0, soc_for(160)).sun_basis)

    def test_sun_while_the_car_is_away_does_not_count(self):
        trips = week(60, 46, 59)                         # away from 07:00 for 3 h + 48/12 h = 7 h: home at 14:00
        a = ahead(trips, 30.0, soc_for(160), sun=self.sun(0, 5.0, range(8, 13)))
        self.assertEqual(a.sun_kwh, 0.0)

    def test_sun_before_the_first_departure_is_the_plans_business(self):
        trips = week(60, 46, 59)
        early = {MON_EVENING + timedelta(minutes=15 * k): 6.0 for k in range(8)}
        self.assertEqual(ahead(trips, 30.0, soc_for(160), sun=early).sun_kwh, 0.0)

    def test_weak_sun_cannot_be_charged(self):
        trips = [Trip(TUE_7, 10.0, 160.0, 12.0), Trip(TUE_7 + timedelta(days=1), 40.0, 150.0, 50.0)]
        self.assertEqual(ahead(trips, 30.0, soc_for(160), days=2, sun=self.sun(0, 0.6, range(11, 17))).sun_kwh, 0.0)


if __name__ == "__main__":
    unittest.main()
