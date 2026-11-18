"""Coordinator: which departure is the next one, and the charge before the first trip in every mode (review 19.11.2026).

Runs in the Home Assistant image (imports homeassistant):
MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W):/w" -w /w --entrypoint python \
  ghcr.io/home-assistant/home-assistant:2026.11.1 tests/install/coord_vorabend_test.py
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from custom_components.plugwhen import coordinator as co, horizon as hz, vollladen as vl  # noqa: E402
from custom_components.plugwhen.need import Need  # noqa: E402

TZ = timezone(timedelta(hours=1))
EVENING_BEFORE = datetime(2026, 11, 18, 19, 0, tzinfo=TZ)
MORNING = datetime(2026, 11, 19, 7, 0, tzinfo=TZ)
EVENING = datetime(2026, 11, 19, 20, 0, tzinfo=TZ)
CAP, CONS = 66.0, 0.2


def bare(learned: datetime | None = MORNING) -> co.Plugwhen:
    p = co.Plugwhen.__new__(co.Plugwhen)
    p.efficiency_of = lambda v: 0.9
    p._learned_departure = lambda v, now: learned
    return p


def car(soc: float = 45.0, departure: datetime = MORNING) -> co.Vehicle:
    v = co.Vehicle("sub", "Auto", {"capacity_kwh": CAP})
    v.weekly_full, v.weekly_days = False, vl.DEFAULT_DAY_SET
    v.soc, v.departure, v.plugged, v.consumption, v.trips = soc, departure, True, CONS, []
    v.need = Need(km=100, kwh=20, target_soc=30.3, charge_kwh=0.0, reachable=True, source="reserve")
    v.need_must = v.need
    return v


def calendar(*departures: datetime) -> list[dict]:
    return [{"departure": d.isoformat(), "km": 60.0, "range_km": 160.0} for d in departures]


class NextDepartureTests(unittest.TestCase):
    """The learned departure in the morning stays the next one when the calendar has a trip in the evening of the same day:
    need, warning, promise and safety check must count for the trip the car really leaves for first."""

    def _departure(self, *cal: datetime, learned: datetime | None = MORNING):
        v = car()
        v.trips = calendar(*cal)
        return bare(learned)._departure(v, EVENING_BEFORE)

    def test_calendar_trip_in_the_evening_does_not_replace_the_morning(self):
        self.assertEqual(self._departure(EVENING), (MORNING, "learned"))

    def test_calendar_trip_before_the_learned_one_comes_first(self):
        early = MORNING - timedelta(hours=1)
        self.assertEqual(self._departure(early), (early, "calendar"))

    def test_calendar_trip_shortly_after_is_the_same_trip(self):
        same = MORNING + timedelta(minutes=90)
        self.assertEqual(self._departure(same), (same, "calendar"))

    def test_calendar_trip_just_outside_the_window_is_its_own_trip(self):
        self.assertEqual(self._departure(MORNING + timedelta(hours=2, minutes=1)), (MORNING, "learned"))

    def test_calendar_alone(self):
        self.assertEqual(self._departure(EVENING, learned=None), (EVENING, "calendar"))

    def test_nothing_known(self):
        self.assertEqual(self._departure(learned=None), (None, None))

    def test_same_rule_as_the_look_ahead(self):
        # the look-ahead (horizon.with_calendar) and the next departure must agree on what is one trip and what are two
        for minutes in (-120, -1, 0, 1, 90, 120, 121, 300, 780):
            cal = MORNING + timedelta(minutes=minutes)
            dep, _ = self._departure(cal)
            trips = hz.with_calendar([hz.Trip(MORNING, 40, 100)], [hz.Trip(cal, 60, 160, 60)])
            self.assertEqual(dep, trips[0].departure, f"calendar trip {minutes} min from the learned one")


class WholeNightCoordinatorTests(unittest.TestCase):
    """The need and the deadline through the whole night, as the coordinator computes them (real look-ahead)."""

    def _run(self, now: datetime, soc: float, trips: list[hz.Trip], departure: datetime, need: Need) -> co.Vehicle:
        v = car(soc, departure)
        v.need = v.need_must = need
        v.horizon = hz.horizon_plan(now, soc / 100.0 * CAP, CAP, CONS, trips, None, 11.0, efficiency=0.9, pref_kw=4.0)
        bare()._evening_before(v, now)
        return v

    def _night(self):
        t = datetime(2026, 11, 18, 17, 0, tzinfo=TZ)
        while t < MORNING:
            yield t
            t += timedelta(minutes=15)

    def test_charge_for_the_evening_trip_holds_until_the_morning_departure(self):
        trips = [hz.Trip(MORNING, 40, 100), hz.Trip(EVENING, 60, 160, 60)]
        need = Need(km=100, kwh=20, target_soc=30.3, charge_kwh=0.0, reachable=True, source="reserve")
        wanted = set()
        for now in self._night():
            v = self._run(now, 45.0, trips, MORNING, need)
            self.assertIsNotNone(v.pre_evening, f"dropped at {now:%a %H:%M}")
            self.assertEqual(v.pre_evening["by"], MORNING.isoformat(), now)
            self.assertEqual(v.need.source, "evening_before", now)
            wanted.add((v.need.charge_kwh, v.need.target_soc))
        self.assertEqual(len(wanted), 1, f"need or target changed during the night: {sorted(wanted)}")

    def test_weekly_full_before_an_earlier_expected_departure_holds_until_it(self):
        trips = [hz.Trip(MORNING, 40, 330), hz.Trip(EVENING, 60, 330, 60)]
        have = round((100.0 - 81.0) / 100.0 * CAP / 0.9, 1)
        need = Need(km=330, kwh=66, target_soc=100.0, charge_kwh=have, reachable=True, source="weekly_full")
        for now in self._night():
            v = self._run(now, 81.0, trips, EVENING, need)
            self.assertIsNotNone(v.pre_evening, f"deadline back to the evening at {now:%a %H:%M}")
            self.assertEqual(v.pre_evening["by"], MORNING.isoformat(), now)
            self.assertAlmostEqual(v.need.charge_kwh, have, delta=0.2)   # not doubled
            self.assertEqual(v.need.target_soc, 100.0)

    def test_nothing_added_when_everything_is_covered(self):
        trips = [hz.Trip(MORNING, 40, 100), hz.Trip(EVENING, 60, 160, 60)]
        need = Need(km=100, kwh=20, target_soc=30.3, charge_kwh=0.0, reachable=True, source="reserve")
        v = self._run(EVENING_BEFORE, 90.0, trips, MORNING, need)
        self.assertIsNone(v.pre_evening)
        self.assertEqual(v.need, need)


class CutToWhatFitsTests(unittest.TestCase):
    """A charge for tomorrow's later trip that does not fit before the first one never makes the plan "cannot be reached"."""

    @staticmethod
    def _plan_for(fits: float):
        def plan_for(kwh: float) -> dict:
            ok = kwh <= fits + 1e-9
            return {"status": "planned" if ok else "infeasible", "planned_kwh": min(kwh, fits), "windows": []}
        return plan_for

    def _car(self, must_kwh: float, total_kwh: float) -> co.Vehicle:
        v = car(45.0)
        v.need_must = Need(km=100, kwh=20, target_soc=50.0, charge_kwh=must_kwh, reachable=True, source="reserve")
        v.need = Need(km=100, kwh=20, target_soc=75.0, charge_kwh=total_kwh, reachable=True, source="evening_before")
        return v

    def test_cut_to_what_fits_before_the_first_trip(self):
        v = self._car(3.0, 20.0)
        plan = bare()._fit_ahead(v, self._plan_for(9.0))
        self.assertEqual(plan["status"], "planned")
        self.assertAlmostEqual(v.need.charge_kwh, 9.0)
        self.assertGreaterEqual(v.need.target_soc, 50.0)
        self.assertLess(v.need.target_soc, 75.0)

    def test_next_trip_alone_when_nothing_more_fits(self):
        v = self._car(3.0, 20.0)
        plan = bare()._fit_ahead(v, self._plan_for(3.2))
        self.assertEqual(plan["status"], "planned")
        self.assertEqual(v.need, v.need_must)

    def test_not_even_the_next_trip_fits_is_still_said(self):
        v = self._car(8.0, 20.0)
        plan = bare()._fit_ahead(v, self._plan_for(2.0))
        self.assertEqual(plan["status"], "infeasible")   # the truth about the next trip is never hidden
        self.assertEqual(v.need, v.need_must)

    def test_untouched_when_it_fits(self):
        v = self._car(3.0, 20.0)
        before = v.need
        plan = bare()._fit_ahead(v, self._plan_for(30.0))
        self.assertEqual(plan["status"], "planned")
        self.assertEqual(v.need, before)


class EvccTests(unittest.TestCase):
    """Mode evcc: evcc gets the deadline before the first trip and the raised target, not the later departure."""

    def _car(self) -> co.Vehicle:
        v = car(45.0)
        v.departure_source = "learned"
        v.need = Need(km=100, kwh=20, target_soc=60.5, charge_kwh=11.4, reachable=True, source="evening_before")
        v.pre_evening = {"kwh": 11.4, "target_soc": 60.5, "by": MORNING.isoformat(), "for_departure": EVENING.isoformat()}
        v.horizon = {"status": "ok", "lasts_until": MORNING.isoformat(), "first_need": {"departure": EVENING.isoformat()}}
        return v

    def test_evcc_plans_to_the_first_departure(self):
        ahead, _week, reason, _ = bare().evcc_plan_inputs(self._car(), EVENING_BEFORE)
        self.assertEqual(reason, "planned")
        self.assertEqual(ahead["departure"], MORNING)
        self.assertEqual(ahead["target_soc"], 60.5)

    def test_still_so_after_midnight_and_shortly_before_the_departure(self):
        for now in (datetime(2026, 11, 19, 0, 10, tzinfo=TZ), datetime(2026, 11, 19, 6, 30, tzinfo=TZ)):
            ahead, _week, _reason, _ = bare().evcc_plan_inputs(self._car(), now)
            self.assertEqual(ahead["departure"], MORNING, now)

    def test_without_it_the_look_ahead_decides_as_before(self):
        v = self._car()
        v.pre_evening = None
        ahead, _week, _reason, _ = bare().evcc_plan_inputs(v, EVENING_BEFORE)
        self.assertEqual(ahead["departure"], EVENING)


class WeeklyDayTickTests(unittest.TestCase):
    """Ticking a day opens a done week again only when the day was off before."""

    def _switch(self, weekday: int):
        from custom_components.plugwhen import switch as sw

        class Plug:
            async def async_recompute(self, vehicle):
                pass

        s = sw.WeeklyDaySwitch.__new__(sw.WeeklyDaySwitch)
        s.vehicle, s.plug, s.weekday = car(), Plug(), weekday
        s.async_write_ha_state = lambda: None
        s.vehicle.weekly_done = "2026-W47"
        return s

    def test_a_day_that_is_on_already_does_not_reopen(self):
        s = self._switch(5)   # Saturday is ticked by default
        asyncio.run(s.async_turn_on())
        self.assertEqual(s.vehicle.weekly_done, "2026-W47")

    def test_a_day_ticked_from_off_reopens(self):
        s = self._switch(2)
        asyncio.run(s.async_turn_on())
        self.assertIsNone(s.vehicle.weekly_done)
        self.assertIn(2, s.vehicle.weekly_days)


if __name__ == "__main__":
    unittest.main()
