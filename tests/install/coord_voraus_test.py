"""Coordinator: the reserve as chosen (left after the trip / least range at the departure) and charging for several days.

Runs in the Home Assistant image (imports homeassistant), found by tests/install/run_coordinator_tests.py.
"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from custom_components.plugwhen import coordinator as co  # noqa: E402
from custom_components.plugwhen.const import RESERVE_AT, V_DAILY_CAP, V_DAYS_AHEAD, V_RESERVE_MODE  # noqa: E402
from custom_components.plugwhen.horizon import Trip  # noqa: E402
from custom_components.plugwhen.learning import WeekdayPlan  # noqa: E402
from custom_components.plugwhen.need import MODE_FLOOR, MODE_PLUS, Need, compute_need  # noqa: E402

TZ = timezone(timedelta(hours=1))
MON_EVENING = datetime(2026, 11, 16, 19, 0, tzinfo=TZ)
TUE_7 = datetime(2026, 11, 17, 7, 0, tzinfo=TZ)
CAP, CONS = 66.0, 0.21


def plan(wd: int, high: float = 46.0) -> WeekdayPlan:
    return WeekdayPlan(wd, 8, high * 0.8, high, 1.0, 7.0, 0.9)


def bare(trips: list[Trip] | None = None) -> co.Plugwhen:
    p = co.Plugwhen.__new__(co.Plugwhen)
    p.efficiency_of = lambda v: 0.9
    p._direct, p._evcc_data = {}, {}
    p.saved: list = []
    p._evcc_store = SimpleNamespace(async_delay_save=lambda *a, **k: p.saved.append(a))
    if trips is not None:
        p._trips = lambda v, now, capacity: trips
    return p


def car(soc: float, **cfg) -> co.Vehicle:
    v = co.Vehicle("sub", "Auto", {co.V_CAPACITY: CAP, **cfg})
    v.soc, v.plugged, v.departure, v.consumption, v.reserve_km = soc, True, TUE_7, CONS, 100.0
    v.model = SimpleNamespace(plan=lambda wd: plan(wd))
    return v


def must_need(v: co.Vehicle, mode: str) -> Need:
    return compute_need(plan(1), v.reserve_km, v.soc, CAP, CONS, mode=mode)


def three_days() -> list[Trip]:
    return [Trip(TUE_7 + timedelta(days=i), 37.0, 146.0, 46.0) for i in range(3)]   # 46 km a day, reserve 100 km


class ReserveModeTests(unittest.TestCase):
    def test_default_is_left_after_the_trip(self):
        v = car(30.0)
        self.assertEqual(co.Plugwhen._need_mode(v), MODE_PLUS)
        n = must_need(v, co.Plugwhen._need_mode(v))
        self.assertEqual((n.km, n.source), (146.0, "plus"))     # 46 km of the day and 100 km left after it

    def test_least_range_at_the_departure_is_as_before(self):
        v = car(30.0, **{V_RESERVE_MODE: RESERVE_AT})
        self.assertEqual(co.Plugwhen._need_mode(v), MODE_FLOOR)
        self.assertEqual(must_need(v, MODE_FLOOR).km, 100.0)

    def test_a_calendar_trip_gets_the_reserve_on_top(self):
        p = bare()
        for cfg, high in (({}, 200.0), ({V_RESERVE_MODE: RESERVE_AT}, 230.0)):
            v = car(30.0, **cfg)
            v.trips = [{"departure": TUE_7.isoformat(), "km": 200.0, "range_km": 230.0}]
            self.assertEqual(p._plan_for(v, TUE_7, 1).km_high, high)
        v = car(30.0)
        v.trips = [{"departure": TUE_7.isoformat(), "km": 200.0, "range_km": 230.0}]
        n = compute_need(p._plan_for(v, TUE_7, 1), v.reserve_km, v.soc, CAP, CONS, mode=MODE_PLUS)
        self.assertEqual(n.km, 300.0)                           # 200 km there and back, 100 km left

    def test_the_coming_trips_carry_the_high_value_and_the_reserve(self):
        p = co.Plugwhen.__new__(co.Plugwhen)
        v = car(30.0)
        v.learn_km, v.weekly_full, v.trips, v.departure_source = True, False, [], "learned"
        first = p._trips(v, MON_EVENING, CAP)[0]
        self.assertEqual((first.km_target, first.km_high), (146.0, 46.0))


class LookAheadTests(unittest.TestCase):
    def step(self, p, v, mode=MODE_PLUS):
        v.need = must_need(v, mode)
        v.need_must = v.need
        p._look_ahead(v, MON_EVENING, None, 11.0)

    def test_below_must_it_fills_for_three_days(self):
        p, v = bare(three_days()), car(30.0)
        self.step(p, v)
        self.assertEqual(v.need_must.target_soc, round(146 * CONS / CAP * 100, 1))      # 46.5 %: what is promised
        self.assertEqual(v.need.source, "ahead")
        self.assertEqual(v.need.target_soc, round((46 + 46 + 146) * CONS / CAP * 100, 1))   # 75.7 %
        self.assertAlmostEqual(v.need.charge_kwh, round((v.need.target_soc - 30.0) / 100 * CAP / 0.9, 1))
        self.assertTrue(p._direct["sub"]["ahead_filling"])
        self.assertTrue(v.ahead["filling"])

    def test_enough_for_the_next_trip_nothing_is_charged(self):
        p, v = bare(three_days()), car(55.0)
        self.step(p, v)
        self.assertEqual(v.need.charge_kwh, 0.0)
        self.assertNotIn("ahead_filling", p._direct["sub"])

    def test_a_fill_goes_on_after_a_restart_and_ends_at_comfort(self):
        p, v = bare(three_days()), car(55.0)
        p._direct["sub"] = {"ahead_filling": True}             # restored from the store
        self.step(p, v)
        self.assertEqual(v.need.source, "ahead")
        v.soc = 75.0
        self.step(p, v)
        self.assertEqual(v.need.charge_kwh, 0.0)
        self.assertNotIn("ahead_filling", p._direct["sub"])

    def test_one_day_is_every_day_on_its_own(self):
        p, v = bare(three_days()), car(30.0, **{V_DAYS_AHEAD: 1})
        self.step(p, v)
        self.assertEqual(v.need.target_soc, v.need_must.target_soc)
        self.assertNotEqual(v.need.source, "ahead")

    def test_the_everyday_limit(self):
        p, v = bare(three_days()), car(30.0, **{V_DAILY_CAP: 60})
        self.step(p, v)
        self.assertEqual(v.need.target_soc, 60.0)

    def test_unknown_state_of_charge_or_no_departure_changes_nothing(self):
        p, v = bare(three_days()), car(30.0)
        v.need = v.need_must = must_need(v, MODE_PLUS)
        v.soc = None
        p._look_ahead(v, MON_EVENING, None, 11.0)
        self.assertIsNone(v.ahead)
        v.soc, v.departure = 30.0, None
        p._look_ahead(v, MON_EVENING, None, 11.0)
        self.assertIsNone(v.ahead)

    def test_a_failure_leaves_the_plan_for_the_next_trip(self):
        p, v = bare(), car(30.0)
        p._trips = lambda *a: (_ for _ in ()).throw(RuntimeError("boom"))
        self.step(p, v)
        self.assertEqual(v.need.target_soc, v.need_must.target_soc)


if __name__ == "__main__":
    unittest.main(verbosity=2)
