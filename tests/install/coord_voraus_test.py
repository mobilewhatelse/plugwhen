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
from custom_components.plugwhen.plan import make_plan  # noqa: E402

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


    def test_a_running_fill_keeps_its_target(self):
        p, v = bare(three_days()), car(30.0)
        self.step(p, v)
        self.assertEqual(p._direct["sub"]["ahead_target"], v.need.target_soc)
        held = v.need.target_soc
        v.soc, v.consumption = 50.0, CONS * 1.03            # colder tomorrow: three percent more consumption
        self.step(p, v)
        self.assertEqual(v.need.target_soc, held)
        v.soc = held                                         # done: nothing is kept
        self.step(p, v)
        self.assertNotIn("ahead_target", p._direct["sub"])

    def test_a_calendar_trip_keeps_its_margin_when_the_reserve_is_small(self):
        p, v = bare(), car(30.0)
        v.reserve_km = 0.0
        v.trips = [{"departure": TUE_7.isoformat(), "km": 200.0, "range_km": 230.0}]
        n = compute_need(p._plan_for(v, TUE_7, 1), v.reserve_km, v.soc, CAP, CONS, mode=MODE_PLUS)
        self.assertEqual(n.km, 230.0)


class SunHabitTests(unittest.TestCase):
    def sunny(self):
        day = TUE_7.replace(hour=0)
        return {day + timedelta(hours=h, minutes=m): 5.0 for h in range(11, 17) for m in (0, 15, 30, 45)}

    def early_home(self):
        return [Trip(TUE_7, 10.0, 146.0, 12.0)] + [Trip(TUE_7 + timedelta(days=i), 37.0, 146.0, 46.0) for i in (1, 2)]

    def target(self, v) -> float:
        p = bare(self.early_home())
        v.need = v.need_must = must_need(v, MODE_PLUS)
        p._look_ahead(v, MON_EVENING, self.sunny(), 11.0)
        return v.need.target_soc

    def test_the_learned_plug_in_hours_decide_which_sun_counts(self):
        nothing_learned = car(30.0)
        self.assertEqual(nothing_learned.plug_log.share_by_hour(MON_EVENING), None)
        with_sun = self.target(nothing_learned)                  # no habit yet: the time at home counts
        evenings_only = car(30.0)
        for d in range(29, 0, -1):                               # four weeks: plugged in 18:00 to 07:00, never by day
            evenings_only.plug_log.change(True, MON_EVENING - timedelta(days=d, hours=1))
            evenings_only.plug_log.change(False, MON_EVENING - timedelta(days=d) + timedelta(hours=12))
        self.assertGreater(self.target(evenings_only), with_sun)   # the midday sun would not reach this car: charged from the grid
        self.assertEqual(evenings_only.ahead["sun_kwh"], 0.0)
        self.assertEqual(evenings_only.ahead["sun_basis"], "plug_times")

    def test_the_habit_is_computed_once_an_hour(self):
        v = car(30.0)
        a = co.Plugwhen._plug_share(v, MON_EVENING)
        v.plug_share_cache = (v.plug_share_cache[0], {"marker": 1.0})
        self.assertEqual(co.Plugwhen._plug_share(v, MON_EVENING + timedelta(minutes=20)), {"marker": 1.0})
        self.assertEqual(co.Plugwhen._plug_share(v, MON_EVENING + timedelta(hours=1)), a)


class TwoCarsTests(unittest.TestCase):
    """Independent review of 0.10: with two cars at one wallbox the first car's charge for several days was handed on as taken,
    and the second car's NEXT trip no longer fitted (replayed: 30 kWh needed, 2.75 kWh planned)."""

    def household(self, conflict: bool):
        p = bare()
        a, b_ = car(30.0), car(30.0)
        a.sub_id, b_.sub_id, a.name, b_.name = "a", "b", "A", "B"
        b_.departure = TUE_7 - timedelta(hours=1)
        b_.plugged = False                                               # not plugged in yet: planned after car A
        p.vehicles = {"a": a, "b": b_}
        p.wallboxes = lambda v: ["sensor.wb"]
        p.calls: list[tuple[str, bool]] = []
        p.shadow: list[str] = []
        p.short_anyway = 0.0   # what car B misses even beside car A's next trip alone

        def compute_plan(x, now, others=None, blocked=None):
            ahead = not p._ahead_off
            p.calls.append((x.sub_id, ahead))
            if x.sub_id == "a":   # plugged in: planned first; with the charge ahead it takes the whole night
                quarters = {MON_EVENING + timedelta(minutes=15 * k): 11.0 for k in range(48 if ahead else 4)}
                x.charge_plan = {"status": "planned", "quarters": quarters, "ahead": ahead}
                if ahead:   # as _look_ahead does: the fill is remembered
                    p._direct.setdefault("a", {}).update(ahead_filling=True, ahead_target=80.0, ahead_for=TUE_7.isoformat())
            else:
                short = conflict and blocked is not None and len(blocked) > 8
                missing = (p.short_anyway + (30.0 if short else 0.0))
                x.charge_plan = {"status": "infeasible" if missing else "planned", "quarters": {}, "ahead": ahead,
                                 "shortfall_kwh": missing}

        p._compute_plan = compute_plan
        p._shadow_step = lambda x, now: p.shadow.append(x.sub_id)
        return p, a, b_

    def test_the_other_cars_next_trip_comes_before_charging_ahead(self):
        p, a, b_ = self.household(conflict=True)
        p._compute(None, MON_EVENING)
        self.assertEqual(b_.charge_plan["status"], "planned")            # its next trip fits
        self.assertFalse(a.charge_plan["ahead"])                         # nobody charges ahead in this run
        self.assertEqual(len(p.calls), 6)                                # next trips alone, with charging ahead, back again
        self.assertEqual(sorted(p.shadow), ["a", "b"])                   # the learn mode notes each car once
        self.assertFalse(p._ahead_off)

    def test_a_car_that_is_short_anyway_must_not_lose_the_rest(self):
        # follow-up of the independent review: car B's next trip does not fit even beside car A's next trip (9 kWh missing);
        # beside car A's charge ahead it would get nothing at all. "Infeasible before and after" is no reason to let that be
        p, a, b_ = self.household(conflict=True)
        p.short_anyway = 9.0
        p._compute(None, MON_EVENING)
        self.assertFalse(a.charge_plan["ahead"])
        self.assertEqual(b_.charge_plan["shortfall_kwh"], 9.0)

    def test_a_fill_started_in_the_dropped_run_is_forgotten(self):
        p, a, _b = self.household(conflict=True)
        p._direct["a"] = {"select.wb_mode": {"set": "Eco"}}            # what Plugwhen set on the wallbox stays
        p._compute(None, MON_EVENING)
        self.assertEqual(p._direct["a"], {"select.wb_mode": {"set": "Eco"}})
        p2, _a2, _b2 = self.household(conflict=True)
        p2._direct["a"] = {"ahead_filling": True, "ahead_target": 76.0, "ahead_for": TUE_7.isoformat()}
        p2._compute(None, MON_EVENING)
        self.assertEqual(p2._direct["a"]["ahead_target"], 76.0)          # a fill that ran before is kept as it was

    def test_without_a_conflict_both_charge_ahead(self):
        p, a, b_ = self.household(conflict=False)
        p._compute(None, MON_EVENING)
        self.assertTrue(a.charge_plan["ahead"])
        self.assertEqual(len(p.calls), 4)

    def test_one_car_is_planned_once(self):
        p, a, _b = self.household(conflict=False)
        p.vehicles = {"a": a}
        p._compute(None, MON_EVENING)
        self.assertEqual(p.calls, [("a", True)])

    def test_the_look_ahead_is_off_in_the_run_for_the_next_trips_alone(self):
        p, v = bare(three_days()), car(30.0)
        v.need = v.need_must = must_need(v, MODE_PLUS)
        p._ahead_off = True
        p._look_ahead(v, MON_EVENING, None, 11.0)
        self.assertEqual(v.need.target_soc, v.need_must.target_soc)
        self.assertEqual(p._direct, {})                                  # and nothing is remembered or forgotten


class FillEndsTests(unittest.TestCase):
    """Independent review of 0.10: without a plug sensor "unplugged" is never seen, and a car with its own charge limit below
    the target never gets there: the fill went on day after day and topped up every night again."""

    def step(self, p, v, now):
        v.need = v.need_must = must_need(v, MODE_PLUS)
        p._look_ahead(v, now, None, 11.0)

    def test_a_fill_ends_when_its_departure_is_past(self):
        p, v = bare(three_days()), car(30.0)
        v.plugged = None                                                 # no plug sensor
        self.step(p, v, MON_EVENING)
        self.assertEqual(p._direct["sub"]["ahead_for"], TUE_7.isoformat())
        v.soc = 70.0                                                     # the car's own limit: never reaches 75.7 %
        self.step(p, v, MON_EVENING + timedelta(hours=6))
        self.assertEqual(v.need.source, "ahead")                         # still the same night: the fill goes on
        v.soc, v.departure = 62.0, TUE_7 + timedelta(days=1)             # Tuesday evening, back home, above the next trip's need
        p._trips = lambda *a: [Trip(TUE_7 + timedelta(days=i), 37.0, 146.0, 46.0) for i in (1, 2, 3)]
        self.step(p, v, TUE_7 + timedelta(hours=12))
        self.assertEqual(v.need.charge_kwh, 0.0)                         # not topped up again
        self.assertNotIn("ahead_filling", p._direct["sub"])
        self.assertNotIn("ahead_for", p._direct["sub"])


class EvccFillTests(unittest.TestCase):
    """Independent review of 0.10: in the mode "via evcc" the charge for several days ended at the next trip's need - the
    look-ahead said "covered" and the plan was taken out of evcc."""

    def evcc_car(self, filling: bool):
        p, v = bare(three_days()), car(55.0)
        p._trip_at = lambda v, dep: None
        v.learn_km, v.weekly_full = True, False
        v.need_must = must_need(v, MODE_PLUS)                            # 46.5 %: covered at 55 %
        v.need = v.need_must
        v.horizon = {"status": "ok", "first_need": None, "lasts_until": "2026-11-19T07:00:00+01:00"}
        v.ahead = {"filling": filling, "target_soc": 75.7, "must_soc": 46.5}
        return p, v

    def test_a_running_fill_is_a_plan_for_evcc(self):
        p, v = self.evcc_car(True)
        plan, _week, reason, _lasts = p.evcc_plan_inputs(v, MON_EVENING)
        self.assertEqual((reason, plan["departure"], plan["target_soc"]), ("planned", TUE_7, 75.7))

    def test_cut_to_fit_evcc_still_gets_the_whole_wish(self):
        p, v = self.evcc_car(True)
        v.ahead.update(target_soc=60.0, cut_to_fit=True, wanted_soc=75.7)
        plan, *_ = p.evcc_plan_inputs(v, MON_EVENING)
        self.assertEqual(plan["target_soc"], 75.7)

    def test_without_a_fill_it_is_covered_as_before(self):
        p, v = self.evcc_car(False)
        plan, _week, reason, _lasts = p.evcc_plan_inputs(v, MON_EVENING)
        self.assertIsNone(plan)
        self.assertEqual(reason, "covered")


class PeakMattersTests(unittest.TestCase):
    """Wish of the user: capping peaks is the guard's job. Where peaks cost nothing (no guard, no demand charge) the plan need
    not charge flat."""

    def plugwhen(self, **options) -> co.Plugwhen:
        p = bare()
        p.entry = SimpleNamespace(options=options)
        p.wallboxes = lambda v: []
        p.shared_wallboxes = lambda: set()
        return p

    def test_without_guard_and_price_the_plan_charges_compactly(self):
        p, v = self.plugwhen(), car(30.0)
        self.assertFalse(p._peak_matters())
        self.assertEqual(p._pref_kw(v, 11.0), 8.25)
        plan = make_plan(MON_EVENING, TUE_7, 22.0, 11.0, 1.4, pref_kw=p._pref_kw(v, 11.0))
        self.assertEqual(plan["status"], "planned")
        self.assertAlmostEqual(plan["planned_kwh"], 22.0, places=1)
        self.assertGreaterEqual(min(plan["quarters"].values()), 8.2)

    def test_where_peaks_cost_nothing_a_slow_car_has_the_whole_night(self):
        # the plan assumes the wallbox power that is set; a car that really takes 3.7 kW must still be ready: early
        p, v = self.plugwhen(), car(30.0)
        plan = make_plan(MON_EVENING, TUE_7, 20.0, 11.0, 1.4, pref_kw=p._pref_kw(v, 11.0), pref_kw2=4.0, early=not p._peak_matters())
        start = min(plan["quarters"])
        self.assertEqual(start, MON_EVENING)
        self.assertGreaterEqual((TUE_7 - start).total_seconds() / 3600.0 * 3.7, 20.0)   # even at 3.7 kW it gets there

    def test_with_a_guard_a_load_forecast_or_a_demand_charge_it_stays_flat(self):
        for options in ({co.O_WAECHTER: "entry"}, {co.O_LOAD: "sensor.load"}, {co.O_PRICE_LOW: 33.82}, {co.O_PRICE_HIGH: "67.64"}):
            p, v = self.plugwhen(**options), car(30.0)
            self.assertTrue(p._peak_matters(), options)
            self.assertEqual(p._pref_kw(v, 11.0), 4.0)

    def test_a_higher_preferred_power_of_the_car_is_kept(self):
        p, v = self.plugwhen(), car(30.0, **{co.V_CHARGE_PREF: 10.0})
        self.assertEqual(p._pref_kw(v, 11.0), 10.0)

    def test_a_shared_wallbox_charges_compactly_also_with_a_guard(self):
        p, v = self.plugwhen(**{co.O_WAECHTER: "entry"}), car(30.0)
        p.wallboxes, p.shared_wallboxes = (lambda v: ["sensor.wb"]), (lambda: {"sensor.wb"})
        self.assertEqual(p._pref_kw(v, 11.0), 8.25)


class FitTests(unittest.TestCase):
    """Review of 0.10: a charge for several days that does not fit before the departure made the plan say "the target cannot
    be reached", although the next trip was fine."""

    def plan_for(self, hours: float):
        return lambda kwh: make_plan(MON_EVENING, MON_EVENING + timedelta(hours=hours), kwh, 11.0, 1.4)

    def ahead_car(self, soc: float = 30.0):
        p, v = bare(three_days()), car(soc)
        v.need = v.need_must = must_need(v, MODE_PLUS)
        p._look_ahead(v, MON_EVENING, None, 11.0)
        self.assertEqual(v.need.source, "ahead")
        return p, v

    def test_enough_time_the_whole_charge_is_planned(self):
        p, v = self.ahead_car()
        plan = p._fit_ahead(v, self.plan_for(12))
        self.assertEqual(plan["status"], "planned")
        self.assertEqual(v.need.target_soc, 75.7)
        self.assertNotIn("cut_to_fit", v.ahead)

    def test_little_time_it_is_cut_to_what_fits_and_the_plan_stays_fine(self):
        p, v = self.ahead_car()                              # 33.5 kWh wanted, two hours at 11 kW
        plan = p._fit_ahead(v, self.plan_for(2))
        self.assertEqual(plan["status"], "planned")
        self.assertAlmostEqual(v.need.charge_kwh, 22.0, delta=0.2)
        self.assertGreater(v.need.target_soc, v.need_must.target_soc)   # the next trip and more
        self.assertLess(v.need.target_soc, 75.7)
        self.assertTrue(v.ahead["cut_to_fit"])
        self.assertEqual(v.ahead["target_soc"], v.need.target_soc)
        self.assertAlmostEqual(v.ahead["wanted_kwh"], 33.5, delta=0.1)   # the wallbox still gets the whole wish
        self.assertEqual(v.ahead["wanted_soc"], 75.7)

    def test_when_not_even_the_next_trip_fits_the_plan_says_so_for_the_next_trip(self):
        p, v = self.ahead_car()                              # the next trip alone needs 12.1 kWh, half an hour gives 5.5
        plan = p._fit_ahead(v, self.plan_for(0.5))
        self.assertEqual(plan["status"], "infeasible")
        self.assertEqual(v.need, v.need_must)
        self.assertAlmostEqual(plan["needed_kwh"], v.need_must.charge_kwh, delta=0.05)

    def test_without_a_charge_ahead_nothing_changes(self):
        p, v = bare(three_days()), car(30.0, **{V_DAYS_AHEAD: 1})
        v.need = v.need_must = must_need(v, MODE_PLUS)
        p._look_ahead(v, MON_EVENING, None, 11.0)
        plan = p._fit_ahead(v, self.plan_for(0.5))
        self.assertEqual(plan["status"], "infeasible")       # as before: the next trip does not fit, and it says so


if __name__ == "__main__":
    unittest.main(verbosity=2)
