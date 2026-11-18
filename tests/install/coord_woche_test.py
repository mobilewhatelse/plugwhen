"""A whole week with a real setup (18.11.2026): the coordinator's complete plan computation every 15 minutes for 7 days.

The car charges what the plan says, drives its learned trips and the calendar trips, and is away for the usual hours. Checked:
enough charge at every departure, never below the reserve after a trip, the everyday limit holds (above it only the weekly full
charge or a long trip), the weekly full charge once a week, the deadline never jumps back, and the heads-up "charging needed
tomorrow" is never said for a departure that was then reached without charging.

Found with it (18.11.2026): the evening-before charge rolled on night after night and filled the battery to 95-100 % for trips
two days later, with a deadline after the car had already left (vorabend.py, now only a later trip of the same day).

Runs in the Home Assistant image (imports homeassistant):
MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W):/w" -w /w --entrypoint python \
  ghcr.io/home-assistant/home-assistant:2026.11.1 tests/install/coord_woche_test.py
"""

from __future__ import annotations

import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from custom_components.plugwhen import coordinator as co, vollladen as vl  # noqa: E402
from custom_components.plugwhen.learning import WeekdayPlan  # noqa: E402
from custom_components.plugwhen.notice import tip_ahead  # noqa: E402

TZ = timezone(timedelta(hours=1))
CAP, CONS, EFF, RESERVE_KM = 66.0, 0.25, 0.907, 100.0
Q = timedelta(minutes=15)
START = datetime(2026, 11, 18, 17, 0, tzinfo=TZ)   # Wednesday evening
# the learned week of the field car: samples, km typical, km high, share of days driven, departure hour
WEEK = {0: (8, 78.5, 82, 1.0, 8.5), 1: (8, 41.5, 59, 1.0, 6.5), 2: (8, 50.5, 136, 1.0, 7.0), 3: (8, 41.5, 46, 1.0, 7.0),
        4: (8, 27, 80, 0.88, 7.0), 5: (8, 33.5, 68, 0.88, 13.0), 6: (8, 13, 51, 0.62, 14.0)}
AWAY_H = {0: 9, 1: 9, 2: 9, 3: 9, 4: 8, 5: 4, 6: 3}
CALENDAR = [{"departure": "2026-11-19T20:00:00+01:00", "km": 65.0, "range_km": 100.0},
            {"departure": "2026-11-21T20:00:00+01:00", "km": 52.8, "range_km": 100.0}]


def plan(wd: int) -> WeekdayPlan:
    s, kt, kh, ds, h = WEEK[wd]
    return WeekdayPlan(wd, s, kt, kh, ds, h, 0.9, h)


class Week:
    """Drives the coordinator like Home Assistant does and plays the car."""

    def __init__(self, soc: float, *, calendar=CALENDAR, waechter: bool = True, days_ahead: int = 3, cap: float = 85.0,
                 weekly_days=frozenset({2}), hold: datetime | None = None, hold_day: date | None = None,
                 unplugged_after: tuple[datetime, ...] = ()):
        self.soc, self.home, self.plugged, self.back_at = soc, True, True, None
        self.cap, self.unplugged_after = cap, unplugged_after
        p = co.Plugwhen.__new__(co.Plugwhen)
        p.efficiency_of = lambda v: EFF
        p._direct, p._evcc_data, p._fleet, p.share_usage, p.vehicles, p.evcc_state = {}, {}, {}, False, {}, None
        p._evcc_store = SimpleNamespace(async_delay_save=lambda *a, **k: None)
        p.entry = SimpleNamespace(options={co.O_WAECHTER: "guard"} if waechter else {})
        p._float = lambda eid: self.soc if eid == "sensor.soc" else None
        p._age_s = lambda eid, now: 60.0
        p._is_on = lambda eid: self.plugged if eid == "binary_sensor.plug" else self.charging
        p._track_plug = lambda v, now: None
        p._temp_at = lambda when, now: None
        p._load_inputs = lambda now: (None, None)
        p._availability = lambda now: (None, None)
        p.wallboxes = lambda v: []
        p.shared_wallboxes = lambda: set()
        v = co.Vehicle("sub", "Auto", {co.V_CAPACITY: CAP, co.V_SOC: "sensor.soc", co.V_PLUGGED: "binary_sensor.plug",
                                       co.V_CHARGING: "binary_sensor.charging", co.V_DAYS_AHEAD: days_ahead, co.V_DAILY_CAP: cap,
                                       co.V_CHARGE_MAX: 11.0})
        v.model = SimpleNamespace(plan=plan, consumption_at=lambda t, f: (CONS, "curve"))
        v.reserve_km, v.learn_km, v.trips, v.mode = RESERVE_KM, True, calendar, "direct"
        v.weekly_full, v.weekly_days, v.weekly_target = True, weekly_days, 100.0
        v.weekly_hold, v.weekly_hold_day = hold, hold_day
        self.p, self.v, self.charging = p, v, False
        self.trips = self._departures(calendar)
        self.left: list[dict] = []        # every departure: when, km, state of charge, what the plan promised just before
        self.charged: list[tuple[datetime, float, str, float]] = []   # quarter hours charged: when, kWh, need source, soc reached
        self.tips: list[tuple[datetime, datetime, float]] = []         # heads-up: when, for which departure, kWh
        self.deadlines: list[tuple[datetime, datetime]] = []           # what the plan charged towards, every quarter hour
        self.problems: list[str] = []
        self.last: datetime | None = None

    @staticmethod
    def _departures(calendar) -> list[tuple[datetime, float]]:
        out, d = [], START.date()
        while d <= (START + timedelta(days=8)).date():
            s, kt, kh, ds, h = WEEK[d.weekday()]
            if ds >= 0.5:
                out.append((datetime(d.year, d.month, d.day, int(h), int(round((h % 1) * 60)), tzinfo=TZ), kt))
            d += timedelta(days=1)
        out += [(datetime.fromisoformat(t["departure"]), float(t["km"])) for t in calendar]
        return sorted(out)

    def run(self, days: int = 7) -> "Week":
        t, before = START, None
        while t < START + timedelta(days=days):
            if not self.home and self.back_at and t >= self.back_at:
                self.home, self.back_at = True, None
                self.plugged = self.last not in self.unplugged_after   # not plugged in until the next departure
            kwq = 0.0
            leaving = [km for d, km in self.trips if d == t]
            if self.home:   # Home Assistant sees the car before it leaves
                self.p._compute_plan(self.v, t)
                kwq = self._look(t) if self.plugged else 0.0
                if not leaving:   # at the departure itself the plan already counts for the next one
                    before = (self.v.need_must.target_soc if self.v.need_must else None)
            if leaving and self.home:
                self.left.append({"at": t, "km": leaving[0], "soc": self.soc, "must": before})
                self.last = t
                self.soc -= leaving[0] * CONS / CAP * 100.0
                self.home, self.plugged = False, False
                self.back_at = t + timedelta(hours=AWAY_H[t.weekday()] if t.hour < 12 else 3)
                kwq = 0.0
            if kwq:
                kwh = kwq * 0.25
                self.soc = min(100.0, self.soc + kwh * EFF / CAP * 100.0)
                self.charged.append((t, kwh, self.v.need.source, max(self.v.need_must.target_soc, self.soc)))
            t += Q
        return self

    def _look(self, t: datetime) -> float:
        v = self.v
        dep = v.departure
        if v.pre_evening:
            dep = datetime.fromisoformat(v.pre_evening["by"])
            if v.departure is not None and dep > v.departure:
                self.problems.append(f"{t:%a %H:%M}: charge before the first trip has its deadline {dep:%a %H:%M} after the "
                                     f"departure {v.departure:%a %H:%M}")
        if dep is not None:
            self.deadlines.append((t, dep))
        tip = tip_ahead(v.horizon, t)
        if tip is not None and tip.kind == "charge":
            self.tips.append((t, tip.departure, tip.kwh))
        self.charging = bool((v.charge_plan.get("quarters") or {}).get(t))
        return float((v.charge_plan.get("quarters") or {}).get(t) or 0.0)


class Checks:
    def check_week(self, w: Week, *, weekly_weeks: int = 1):
        reserve = RESERVE_KM * CONS / CAP * 100.0
        self.assertGreaterEqual(len(w.left), 7, "the car must have driven the week")
        for x in w.left:
            if x["must"] is not None:
                self.assertGreaterEqual(x["soc"], x["must"] - 1.0, f"{x['at']:%a %H:%M}: left with {x['soc']:.1f} %, "
                                                                     f"the plan promised {x['must']} %")
            after = x["soc"] - x["km"] * CONS / CAP * 100.0
            self.assertGreaterEqual(after, reserve - 1.0, f"{x['at']:%a %H:%M}: {after:.1f} % after the trip, below the reserve")
        self.assertEqual(w.problems, [])
        # the deadline never jumps back (a moving deadline moves the charge away)
        for (t1, d1), (t2, d2) in zip(w.deadlines, w.deadlines[1:]):
            self.assertFalse(d2 < d1 and d1 > t2, f"deadline back from {d1:%a %H:%M} to {d2:%a %H:%M} at {t2:%a %H:%M}")
        # above the everyday limit only for the weekly full charge
        full = [x for x in w.left if x["soc"] >= 99.0]
        self.assertLessEqual(len(full), weekly_weeks, f"full at {[f'{x['at']:%a %H:%M}' for x in full]}")
        # charged above the everyday limit only for the weekly full charge, a trip that needs it or the later trip of the day
        for t, kwh, source, reached in w.charged:
            if reached > w.cap + 1.0:
                self.assertNotEqual(source, "ahead", f"{t:%a %H:%M}: charged ahead to {reached:.1f} %")
        # a heads-up "charging needed" for a departure that was then reached without any charging was wrong
        for t, dep, kwh in w.tips:
            gone = [x for x in w.left if x["at"] == dep]
            if not gone or kwh < 1.0:
                continue
            got = sum(k for c, k, _, _ in w.charged if t <= c < dep)
            self.assertGreater(got, 0.5, f"{t:%a %H:%M}: said {kwh} kWh needed for {dep:%a %H:%M}, reached without charging")


class WeekTests(Checks, unittest.TestCase):
    def test_the_field_car_as_it_is_tonight(self):
        # the kept full charge of the old build: for Thursday 20:00, chosen on Wednesday
        w = Week(82.0, hold=datetime(2026, 11, 19, 20, 0, tzinfo=TZ), hold_day=date(2026, 11, 18)).run()
        self.check_week(w, weekly_weeks=2)

    def test_the_field_car_without_a_peak_guard(self):
        w = Week(82.0, waechter=False, hold=datetime(2026, 11, 19, 20, 0, tzinfo=TZ), hold_day=date(2026, 11, 18)).run()
        self.check_week(w, weekly_weeks=2)

    def test_a_fresh_start(self):
        self.check_week(Week(82.0).run(), weekly_weeks=2)

    def test_low_state_of_charge(self):
        self.check_week(Week(35.0).run(), weekly_weeks=2)

    def test_every_day_on_its_own(self):
        self.check_week(Week(60.0, days_ahead=1, cap=80.0).run(), weekly_weeks=2)

    def test_without_the_weekly_full_charge(self):
        self.check_week(Week(60.0, weekly_days=frozenset()).run(), weekly_weeks=0)

    def test_not_plugged_in_between_the_two_trips_on_thursday(self):
        # the wish behind the evening-before charge: Thursday morning and evening, not plugged in in between
        w = Week(55.0, weekly_days=frozenset(), unplugged_after=(datetime(2026, 11, 19, 7, 0, tzinfo=TZ),)).run()
        self.assertTrue(any(x["at"] == datetime(2026, 11, 19, 20, 0, tzinfo=TZ) for x in w.left))
        self.check_week(w, weekly_weeks=0)   # enough for the evening trip, charged before the morning one

    def test_the_week_charges_no_more_than_it_drives(self):
        # no double charging: over the week the grid gives what was driven (plus what is left in the battery), not more
        w = Week(60.0, weekly_days=frozenset()).run()
        driven = sum(x["km"] for x in w.left) * CONS
        charged = sum(k for _, k, _, _ in w.charged) * EFF
        end = w.soc
        self.assertAlmostEqual(charged, driven + (end - 60.0) / 100.0 * CAP, delta=0.5)
        self.assertLessEqual(end, w.cap + 1.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
