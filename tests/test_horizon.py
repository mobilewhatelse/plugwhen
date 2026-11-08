"""Tests for the look-ahead: pre-charging with the sun."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

from horizon import Trip, away_hours, horizon_plan  # noqa: E402

TZ = timezone(timedelta(hours=1))
SAT = datetime(2027, 1, 9, 9, 0, tzinfo=TZ)           # Saturday 09:00


def at(day, h, m=0):
    return SAT.replace(hour=0, minute=0) + timedelta(days=day, hours=h, minutes=m)


def week():
    # Sat 13:00, Sun 13:00, Mon 08:00, Tue 07:00, Wed 07:00; range to have 100 km (20 kWh at 0.2 kWh/km)
    return [Trip(at(0, 13), 22, 100), Trip(at(1, 13), 10, 100), Trip(at(2, 8), 78, 100), Trip(at(3, 7), 41, 100), Trip(at(4, 7), 67, 100)]


def sun(days=(0, 1), kw=4.0, hours=range(10, 13)):
    return {at(d, h) + timedelta(minutes=m): kw for d in days for h in hours for m in (0, 15, 30, 45)}


def plan(**kw):
    args = dict(now=SAT, soc_kwh=30.0, capacity_kwh=60.0, consumption=0.2, trips=week(), sun_kw=sun(), max_kw=11.0)
    args.update(kw)
    return horizon_plan(**args)


class HorizonTest(unittest.TestCase):
    def test_deficits_come_in_order(self):
        r = plan(sun_kw=None)
        by = {d["departure"]: d for d in r["days"]}
        self.assertEqual(by[at(0, 13).isoformat()]["need_kwh"], 0.0)                 # 30 kWh, 20 needed
        self.assertEqual(by[at(2, 8).isoformat()]["need_kwh"], 0.0)
        self.assertAlmostEqual(by[at(3, 7).isoformat()]["need_kwh"], (20 - (30 - 4.4 - 2.0 - 15.6)) / 0.9, places=1)     # Tuesday
        self.assertGreater(by[at(4, 7).isoformat()]["need_kwh"], 0)                  # and Wednesday

    def test_the_sunny_weekend_replaces_the_grid_nights_of_tuesday_and_wednesday(self):
        r = plan()
        self.assertGreater(r["grid_without_precharge_kwh"], 20)
        self.assertLess(r["grid_with_precharge_kwh"], 1.0)
        self.assertAlmostEqual(r["saved_grid_kwh"], r["grid_without_precharge_kwh"] - r["grid_with_precharge_kwh"], places=1)
        self.assertGreaterEqual(len(r["precharge"]), 2)
        for p in r["precharge"]:
            self.assertLess(p["window_end"], at(2, 0).isoformat())                  # charged at the weekend
            self.assertGreater(p["for_departure"], p["window_end"])
        total = sum(p["kwh"] for p in r["precharge"])
        self.assertAlmostEqual(total, r["saved_grid_kwh"], places=1)

    def test_without_sun_nothing_is_pre_charged(self):
        for s in (None, {}):
            r = plan(sun_kw=s)
            self.assertEqual(r["precharge"], [])
            self.assertEqual(r["saved_grid_kwh"], 0.0)
            self.assertEqual(r["grid_with_precharge_kwh"], r["grid_without_precharge_kwh"])
            self.assertFalse(r["sun_used"])
            self.assertEqual(r["status"], "ok")

    def test_the_battery_cap_limits_the_pre_charging(self):
        loose = plan()
        tight = plan(cap_share=0.55)                                                # 33 kWh: 3 kWh above the 30 now
        self.assertLess(tight["saved_grid_kwh"], loose["saved_grid_kwh"])
        # Saturday may add 3 kWh to the battery, Sunday (25.6 kWh without it, 3 kWh from Saturday still in) 4.4 kWh: 7.4 kWh = 8.2 from the wallbox
        self.assertLessEqual(sum(p["kwh"] for p in tight["precharge"]), 8.3)
        self.assertGreaterEqual(sum(p["kwh"] for p in tight["precharge"]), 7.0)
        none = plan(cap_share=0.4)                                                  # 24 kWh: below the state of charge, no room
        self.assertEqual(none["precharge"], [])

    def test_sun_on_the_same_day_covers_that_days_deficit(self):
        trips = [Trip(at(0, 20), 20, 100)]
        r = plan(soc_kwh=10.0, trips=trips, sun_kw=sun(days=(0,), hours=range(10, 16)))
        d = r["days"][0]
        self.assertGreater(d["sun_direct_kwh"], 0)
        self.assertAlmostEqual(d["sun_direct_kwh"] + d["grid_kwh"], d["need_kwh"], places=1)
        self.assertEqual(r["precharge"], [])

    def test_latest_start_is_the_departure_minus_the_time_at_full_power(self):
        r = plan(sun_kw=None)
        by = {d["departure"]: d for d in r["days"]}
        tue = by[at(3, 7).isoformat()]
        expected = at(3, 7) - timedelta(hours=tue["need_kwh"] / 11.0)
        self.assertLess(abs((datetime.fromisoformat(tue["latest_start"]) - expected).total_seconds()), 120)       # need_kwh is rounded to 0.1 kWh
        self.assertIsNone(by[at(0, 13).isoformat()]["latest_start"])                  # nothing needed: no latest start

    def test_with_normal_behaviour_it_says_until_when_the_charge_lasts_and_the_first_charging_needed(self):
        r = plan(sun_kw=None)
        self.assertEqual(r["trips_looked_at"], 5)
        fn = r["first_need"]
        self.assertEqual(fn["departure"], at(3, 7).isoformat())                       # Tuesday is the first deficit
        self.assertEqual(r["lasts_until"], at(2, 8).isoformat())                      # the charge lasts until Monday morning's departure
        self.assertLess(fn["latest_start_pref"], fn["latest_start"]) if fn["latest_start_pref"] else None
        self.assertFalse(fn["covered_by_sun"])

    def test_the_sun_can_cover_the_first_need_but_it_is_still_the_first_need(self):
        r = plan(trips=[Trip(at(0, 20), 20, 100)], soc_kwh=10.0, sun_kw=sun(days=(0,), hours=range(10, 16)))
        self.assertTrue(r["first_need"]["covered_by_sun"])

    def test_no_need_within_the_whole_look_ahead(self):
        r = plan(soc_kwh=60.0, trips=week()[:3])
        self.assertIsNone(r["first_need"])
        self.assertEqual(r["lasts_until"], at(2, 8).isoformat())

    def test_a_look_ahead_of_two_weeks_works(self):
        trips = [Trip(at(d, 7), 40, 100) for d in range(2, 16)]
        r = plan(soc_kwh=45.0, trips=trips, sun_kw=None)
        self.assertEqual(r["trips_looked_at"], 14)
        self.assertIsNotNone(r["first_need"])
        self.assertEqual(r["status"], "ok")
    def test_nothing_needed(self):
        r = plan(soc_kwh=60.0, trips=week()[:2])
        self.assertEqual(r["status"], "no_need")
        self.assertEqual(r["precharge"], [])

    def test_unknown_state_of_charge_and_no_trips(self):
        self.assertEqual(plan(soc_kwh=None)["status"], "unknown_soc")
        self.assertEqual(plan(trips=[])["status"], "no_trips")
        self.assertEqual(plan(trips=[Trip(SAT - timedelta(hours=1), 20, 100)])["status"], "no_trips")     # in the past

    def test_windows_are_in_order_and_never_overlap(self):
        r = plan()
        starts = [d["window_start"] for d in r["days"]]
        deps = [d["departure"] for d in r["days"]]
        self.assertEqual(starts, sorted(starts))
        for a, b, dep in zip(starts[1:], starts, deps):
            self.assertGreaterEqual(a, dep if False else b)
        for i in range(1, len(starts)):
            self.assertGreaterEqual(starts[i], deps[i - 1])

    def test_the_time_away_follows_the_length_of_the_trip(self):
        self.assertEqual(away_hours(0), 3.0)
        self.assertAlmostEqual(away_hours(78), 9.5)
        self.assertEqual(away_hours(500), 10.0)

    def test_sun_spare_without_a_later_deficit_is_not_pre_charged(self):
        r = plan(trips=week()[:3])                                                  # no later deficit within the horizon
        self.assertEqual(r["precharge"], [])


if __name__ == "__main__":
    unittest.main()
