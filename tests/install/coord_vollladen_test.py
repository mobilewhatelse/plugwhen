"""Coordinator: once a week full raises the target for a plan that includes the chosen day, and marks the week done.

Runs in the Home Assistant image (imports homeassistant):
MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W):/w" -w /w --entrypoint python \
  ghcr.io/home-assistant/home-assistant:2026.11.1 tests/install/coord_vollladen_test.py
"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from custom_components.plugwhen import coordinator as co, vollladen as vl  # noqa: E402
from custom_components.plugwhen.need import Need  # noqa: E402

TZ = timezone(timedelta(hours=1))
FRI_EVENING = datetime(2026, 11, 20, 18, 0, tzinfo=TZ)
MON_MORNING = datetime(2026, 11, 23, 7, 0, tzinfo=TZ)


def bare() -> co.Plugwhen:
    p = co.Plugwhen.__new__(co.Plugwhen)
    p.efficiency_of = lambda v: 0.9
    return p


def car(soc: float, departure=MON_MORNING) -> co.Vehicle:
    v = co.Vehicle("sub", "Auto", {"capacity_kwh": 60})
    v.weekly_full, v.weekly_days, v.weekly_target = True, vl.DEFAULT_DAY_SET, 100.0
    v.soc, v.departure = soc, departure
    v.need = Need(km=100, kwh=20, target_soc=45.0, charge_kwh=0.0, reachable=True, source="reserve")
    return v


class WeeklyFullTests(unittest.TestCase):
    def test_target_raised_for_a_plan_over_the_weekend(self):
        v = car(50.0)
        bare()._weekly_full(v, FRI_EVENING, None)
        self.assertTrue(v.weekly_active)
        self.assertEqual(v.weekly_day.weekday(), 5)
        self.assertEqual(v.need.target_soc, 100.0)
        self.assertEqual(v.need.source, "weekly_full")
        self.assertAlmostEqual(v.need.charge_kwh, round(30.0 / 0.9, 1))   # 50 % of 60 kWh, with the charging losses

    def test_off_changes_nothing(self):
        v = car(50.0)
        v.weekly_full = False
        bare()._weekly_full(v, FRI_EVENING, None)
        self.assertFalse(v.weekly_active)
        self.assertEqual(v.need.target_soc, 45.0)

    def test_full_marks_the_week_done(self):
        v = car(99.5)
        sat = FRI_EVENING + timedelta(hours=16)
        bare()._weekly_full(v, sat, None)
        self.assertEqual(v.weekly_done, vl.week_key(sat.date()))
        self.assertFalse(v.weekly_active)
        self.assertEqual(v.need.target_soc, 45.0)
        bare()._weekly_full(v, sat + timedelta(days=1), None)   # Sunday: not again this week
        self.assertIsNone(v.weekly_day)

    def test_departure_before_the_day_keeps_the_normal_target(self):
        v = car(50.0, departure=FRI_EVENING + timedelta(hours=4))
        bare()._weekly_full(v, FRI_EVENING, None)
        self.assertFalse(v.weekly_active)
        self.assertEqual(v.need.target_soc, 45.0)

    def test_a_higher_normal_target_stays(self):
        v = car(50.0)
        v.weekly_target = 80.0
        v.need = Need(km=400, kwh=90, target_soc=95.0, charge_kwh=30.0, reachable=True, source="learned")
        bare()._weekly_full(v, FRI_EVENING, None)
        self.assertEqual(v.need.target_soc, 95.0)

    def test_look_ahead_plans_the_range_of_the_full_target(self):
        v = car(50.0)
        v.departure_source, v.trips, v.consumption = "entity", [], 0.2
        bare()._weekly_full(v, FRI_EVENING, None)
        trips = bare()._trips(v, FRI_EVENING, 60.0)
        mon = [t for t in trips if t.departure == MON_MORNING]
        self.assertEqual(len(mon), 1)
        self.assertAlmostEqual(mon[0].km_target, 300.0)   # 100 % of 60 kWh at 0.2 kWh/km

    def test_look_ahead_full_target_also_for_a_calendar_trip(self):
        # field test 16.11.2026: the departure came from the calendar (Buero, 59 km); the look-ahead kept its 100 km range
        v = car(50.0)
        v.departure_source, v.consumption = "calendar", 0.2
        v.trips = [{"departure": MON_MORNING.isoformat(), "km": 59.0, "range_km": 100.0}]
        bare()._weekly_full(v, FRI_EVENING, None)
        mon = [t for t in bare()._trips(v, FRI_EVENING, 60.0) if t.departure == MON_MORNING]
        self.assertEqual(len(mon), 1)
        self.assertAlmostEqual(mon[0].km_target, 300.0)
        v.weekly_full = False
        mon = [t for t in bare()._trips(v, FRI_EVENING, 60.0) if t.departure == MON_MORNING]
        self.assertLess(mon[0].km_target, 300.0)

    def test_the_card_shows_the_range_of_the_full_target(self):
        # field test 16.11.2026: '100 % (100.0 km)' - the reserve range stood next to the full target
        v = car(50.0)
        v.consumption = 0.2
        bare()._weekly_full(v, FRI_EVENING, None)
        self.assertEqual(v.need.source, "weekly_full")
        self.assertEqual(v.need.target_soc, 100.0)
        self.assertGreater(v.need.km, 100.0)
        self.assertAlmostEqual(v.need.kwh, 100.0 / 100.0 * float(v.cfg.get("capacity_kwh") or 60.0), places=1)

    def test_only_the_first_departure_gets_the_full_target(self):
        # 18.11.2026: full by Thu 07:00 (learned) and a calendar trip at 20:00 the same day; the full target was kept for both,
        # so after the morning trip the evening one "needed" the battery full again: "charging needed tomorrow, 11 kWh"
        v = car(82.0, departure=MON_MORNING)
        v.departure_source, v.consumption = "entity", 0.2   # the morning departure (learned live; the test car has no model)
        evening = MON_MORNING + timedelta(hours=13)
        v.trips = [{"departure": evening.isoformat(), "km": 65.0, "range_km": 100.0}]
        p = bare()
        p._weekly_full(v, FRI_EVENING, None)
        v.weekly_hold = evening   # kept for the later departure (as live: the hold came from before the departure moved)
        trips = {t.departure: t for t in p._trips(v, FRI_EVENING, 60.0)}
        self.assertAlmostEqual(trips[MON_MORNING].km_target, 300.0)
        self.assertLess(trips[evening].km_target, 300.0)

    def test_the_full_target_goes_to_the_calendar_trip_when_it_comes_first(self):
        v = car(50.0)
        v.departure_source, v.consumption = "calendar", 0.2
        early = MON_MORNING - timedelta(hours=1)
        v.trips = [{"departure": early.isoformat(), "km": 59.0, "range_km": 100.0}]
        bare()._weekly_full(v, FRI_EVENING, None)
        trips = {t.departure: t for t in bare()._trips(v, FRI_EVENING, 60.0)}
        self.assertAlmostEqual(trips[early].km_target, 300.0)
        later = [t for d, t in trips.items() if d > early]
        self.assertTrue(all(t.km_target < 300.0 for t in later))

    def test_look_ahead_unchanged_when_off(self):
        v = car(50.0)
        v.weekly_full = False
        v.departure_source, v.trips, v.consumption = "entity", [], 0.2
        trips = bare()._trips(v, FRI_EVENING, 60.0)
        self.assertLess(max(t.km_target for t in trips), 300.0)

    def test_evcc_plan_gets_the_full_target(self):
        v = car(50.0)
        v.departure_source, v.trips, v.consumption = "entity", [], 0.2
        bare()._weekly_full(v, FRI_EVENING, None)
        v.horizon = {"status": "ok", "first_need": {"departure": MON_MORNING.isoformat()}}
        ahead, _week, reason, _ = bare().evcc_plan_inputs(v, FRI_EVENING)
        self.assertEqual(reason, "planned")
        self.assertEqual(ahead["target_soc"], 100.0)

    def test_evcc_plan_normal_when_off(self):
        v = car(50.0)
        v.weekly_full = False
        v.departure_source, v.trips, v.consumption = "entity", [], 0.2
        v.horizon = {"status": "ok", "first_need": {"departure": MON_MORNING.isoformat()}}
        ahead, _week, _reason, _ = bare().evcc_plan_inputs(v, FRI_EVENING)
        self.assertLess(ahead["target_soc"], 100.0)


class EveningBeforeCoordinatorTests(unittest.TestCase):
    """Field test 18.11.2026: 81 %, everyday limit 80 %, second trip tomorrow evening needs 2.3 kWh -> charged tonight."""

    def _car(self):
        v = car(81.0, departure=datetime(2026, 11, 19, 20, 0, tzinfo=TZ))
        v.weekly_full, v.plugged = False, True
        v.cfg["capacity_kwh"] = 66
        v.need = Need(km=165, kwh=0, target_soc=67.3, charge_kwh=0.0, reachable=True, source="calendar")
        v.horizon = {"lasts_until": "2026-11-19T07:00:00+01:00",
                     "first_need": {"departure": "2026-11-19T20:00:00+01:00", "window_start": "2026-11-19T13:27:30+01:00",
                                    "need_kwh": 2.3, "covered_by_sun": False}}
        return v

    def test_need_raised_tonight_not_cut_by_the_limit(self):
        v = self._car()
        bare()._evening_before(v, datetime(2026, 11, 18, 19, 10, tzinfo=TZ))
        self.assertEqual(v.need.source, "evening_before")
        self.assertGreater(v.need.target_soc, 83.0)
        self.assertAlmostEqual(v.need.charge_kwh, 2.3)
        self.assertEqual(v.pre_evening["by"], "2026-11-19T07:00:00+01:00")

    def test_nothing_when_unplugged(self):
        v = self._car()
        v.plugged = False
        bare()._evening_before(v, datetime(2026, 11, 18, 19, 10, tzinfo=TZ))
        self.assertIsNone(v.pre_evening)
        self.assertEqual(v.need.source, "calendar")

    def test_earlier_learned_departure_moves_the_deadline(self):
        v = self._car()
        v.need = Need(km=300, kwh=0, target_soc=100.0, charge_kwh=13.1, reachable=True, source="weekly_full")
        v.horizon = {"first_need": {"departure": "2026-11-19T07:00:00+01:00", "window_start": "2026-11-18T19:48:00+01:00",
                                    "need_kwh": 13.1, "covered_by_sun": False}}
        bare()._evening_before(v, datetime(2026, 11, 18, 19, 50, tzinfo=TZ))
        self.assertEqual(v.pre_evening["by"], "2026-11-19T07:00:00+01:00")
        self.assertAlmostEqual(v.need.charge_kwh, 13.1)   # not doubled
        self.assertEqual(v.need.source, "weekly_full")


class WeeklyReopenTests(unittest.TestCase):
    """Field test 18.11.2026: 'done this week' could not be opened again; ticking a day (or the main switch) does."""

    def _switch(self, cls, *args):
        from custom_components.plugwhen import switch as sw

        recomputed = []

        class Plug:
            async def async_recompute(self, vehicle):
                recomputed.append(vehicle)

        s = getattr(sw, cls).__new__(getattr(sw, cls))
        s.vehicle, s.plug = car(99.0), Plug()
        for k, val in zip(("weekday",), args):
            s.weekday = val
        s.async_write_ha_state = lambda: None
        s.vehicle.weekly_done = "2026-W47"
        return s, recomputed

    def test_ticking_a_day_reopens_the_week(self):
        import asyncio

        s, recomputed = self._switch("WeeklyDaySwitch", 2)
        asyncio.run(s.async_turn_on())
        self.assertIsNone(s.vehicle.weekly_done)
        self.assertEqual(len(recomputed), 1)

    def test_unticking_a_day_keeps_it_done(self):
        import asyncio

        s, _ = self._switch("WeeklyDaySwitch", 2)
        asyncio.run(s.async_turn_off())
        self.assertEqual(s.vehicle.weekly_done, "2026-W47")

    def test_main_switch_on_reopens_the_week(self):
        import asyncio

        s, _ = self._switch("WeeklyFullSwitch")
        asyncio.run(s.async_turn_on())
        self.assertIsNone(s.vehicle.weekly_done)


SUN_EVENING = datetime(2026, 11, 22, 18, 50, tzinfo=TZ)
AFTER_MIDNIGHT = datetime(2026, 11, 23, 0, 2, tzinfo=TZ)


def fresh_need(v: co.Vehicle) -> None:
    """The coordinator computes the normal need again every run before the full charge raises it."""
    v.need = Need(km=100, kwh=20, target_soc=45.0, charge_kwh=0.0, reachable=True, source="reserve")


class KeptOverMidnightTests(unittest.TestCase):
    """Bug 16.11.2026: chosen Sunday, plugged in Sunday evening, departure Monday 07:00. The planner charges in the night; at
    midnight the full target was gone and the wallbox got only the normal amount."""

    def sunday_plan(self, soc: float = 28.0) -> co.Vehicle:
        v = car(soc)
        bare()._weekly_full(v, SUN_EVENING, None)
        self.assertTrue(v.weekly_active)
        self.assertEqual(v.weekly_hold, MON_MORNING)
        return v

    def test_full_target_kept_after_midnight(self):
        v = self.sunday_plan()
        fresh_need(v)
        bare()._weekly_full(v, AFTER_MIDNIGHT, None)
        self.assertTrue(v.weekly_active)
        self.assertEqual(v.need.target_soc, 100.0)
        self.assertEqual(v.weekly_day, SUN_EVENING.date())

    def test_kept_when_the_departure_moves_an_hour_later(self):
        v = self.sunday_plan()
        fresh_need(v)
        v.departure = MON_MORNING + timedelta(hours=1)
        bare()._weekly_full(v, AFTER_MIDNIGHT + timedelta(hours=1), None)
        self.assertEqual(v.need.target_soc, 100.0)

    def test_reached_on_monday_books_the_week_of_sunday(self):
        v = self.sunday_plan()
        v.soc = 99.5
        fresh_need(v)
        bare()._weekly_full(v, AFTER_MIDNIGHT + timedelta(hours=5), None)
        self.assertEqual(v.weekly_done, vl.week_key(SUN_EVENING.date()))
        self.assertIsNone(v.weekly_hold)
        self.assertEqual(v.need.target_soc, 45.0)
        # the new week chooses its own day again
        bare()._weekly_full(v, AFTER_MIDNIGHT + timedelta(hours=6), None)
        self.assertIsNotNone(v.weekly_day)
        self.assertGreater(v.weekly_day, SUN_EVENING.date())

    def test_released_after_the_departure(self):
        v = self.sunday_plan()
        fresh_need(v)
        v.departure = MON_MORNING + timedelta(days=1)   # the next departure: Tuesday
        bare()._weekly_full(v, MON_MORNING + timedelta(hours=vl.HOLD_SLACK_H, minutes=1), None)
        self.assertIsNone(v.weekly_hold)
        self.assertFalse(v.weekly_active)
        self.assertEqual(v.need.target_soc, 45.0)

    def test_a_later_departure_does_not_get_the_kept_target(self):
        v = self.sunday_plan()
        fresh_need(v)
        v.departure = MON_MORNING + timedelta(days=1)   # the car was not used Monday, the plan now goes to Tuesday
        bare()._weekly_full(v, AFTER_MIDNIGHT, None)
        self.assertFalse(v.weekly_active)

    def test_kept_departure_deleted_on_the_chosen_day_counts_for_the_next(self):
        # field test 16.11.2026: Monday ticked at 20:00 while a calendar trip at 22:00 was the departure, then the trip was
        # deleted and the next departure was Tuesday 08:00. The hold stayed on 22:00 and the full charge did not count
        mon_20 = datetime(2026, 11, 16, 20, 0, tzinfo=TZ)
        v = car(30.0, departure=mon_20 + timedelta(hours=2))
        v.weekly_days = frozenset({0})
        bare()._weekly_full(v, mon_20, None)
        self.assertTrue(v.weekly_active)
        self.assertEqual(v.weekly_hold, mon_20 + timedelta(hours=2))
        fresh_need(v)
        v.departure = mon_20 + timedelta(hours=12)      # the trip deleted: Tuesday 08:00
        bare()._weekly_full(v, mon_20 + timedelta(minutes=7), None)
        self.assertTrue(v.weekly_active)
        self.assertEqual(v.need.target_soc, 100.0)
        self.assertEqual(v.weekly_hold, mon_20 + timedelta(hours=12))
        fresh_need(v)
        bare()._weekly_full(v, mon_20 + timedelta(hours=5), None)   # after midnight: still kept for Tuesday 08:00
        self.assertTrue(v.weekly_active)
        self.assertEqual(v.need.target_soc, 100.0)

    def test_switched_off_drops_the_kept_target(self):
        v = self.sunday_plan()
        fresh_need(v)
        v.weekly_full = False
        bare()._weekly_full(v, AFTER_MIDNIGHT, None)
        self.assertIsNone(v.weekly_hold)
        self.assertFalse(v.weekly_active)

    def test_unticking_the_day_drops_the_kept_target(self):
        # review 16.11.: only the main switch ended a kept full charge, unticking its day in the day bar did not
        v = self.sunday_plan()
        fresh_need(v)
        v.weekly_days = frozenset({5})   # Sunday unticked, Saturday (past) stays
        bare()._weekly_full(v, AFTER_MIDNIGHT - timedelta(hours=2), None)
        self.assertIsNone(v.weekly_hold)
        self.assertFalse(v.weekly_active)
        self.assertEqual(v.need.target_soc, 45.0)

    def test_evcc_and_look_ahead_keep_it_after_midnight(self):
        v = self.sunday_plan()
        v.departure_source, v.trips, v.consumption = "entity", [], 0.2
        fresh_need(v)
        bare()._weekly_full(v, AFTER_MIDNIGHT, None)
        mon = [t for t in bare()._trips(v, AFTER_MIDNIGHT, 60.0) if t.departure == MON_MORNING]
        self.assertAlmostEqual(mon[0].km_target, 300.0)
        v.horizon = {"status": "ok", "first_need": {"departure": MON_MORNING.isoformat()}}
        ahead, _week, _reason, _ = bare().evcc_plan_inputs(v, AFTER_MIDNIGHT)
        self.assertEqual(ahead["target_soc"], 100.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
