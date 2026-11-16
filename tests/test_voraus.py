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


def ahead(trips, soc, must, days=3, cap=80.0, filling=False, plugged=True, sun=None):
    return vo.look_ahead(MON_EVENING, trips, TUE_7, soc, must, days=days, cap_soc=cap, capacity_kwh=CAP, consumption=CONS,
                         efficiency=EFF, filling=filling, plugged=plugged, sun_kw=sun, max_kw=11.0)


class ComfortTests(unittest.TestCase):
    def test_three_days_are_the_trips_before_plus_the_last_ones_target(self):
        trips = week(60, 136, 46, 80)
        self.assertEqual(len(vo.trips_ahead(trips, TUE_7, 3)), 3)
        self.assertAlmostEqual(vo.comfort_km(vo.trips_ahead(trips, TUE_7, 3)), 60 + 136 + 46 + RESERVE)

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
