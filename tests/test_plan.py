"""Tests for the charging plan."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

from plan import charging_allowed, make_plan  # noqa: E402

TZ = timezone(timedelta(hours=1))
NOW = datetime(2027, 1, 12, 17, 5, tzinfo=TZ)
DEPART = datetime(2027, 1, 13, 7, 0, tzinfo=TZ)


def load(high_by_hour=None, default=0.5):
    out, t = [], NOW.replace(minute=0)
    while t < DEPART + timedelta(hours=1):
        high = (high_by_hour or {}).get(t.hour, default)
        out.append({"t": t, "typical": high / 2, "high": high, "n": 4})
        t += timedelta(minutes=15)
    return out


def plan(**kw):
    args = dict(now=NOW, departure=DEPART, need_kwh=24.0, max_kw=11.0, min_kw=1.4, load=load(), target_kw=9.5)
    args.update(kw)
    return make_plan(**args)


class PlanTest(unittest.TestCase):
    def test_charges_in_the_quietest_hours(self):
        quiet = {h: 0.3 for h in (2, 3, 4)}
        p = plan(load=load({**{h: 3.0 for h in range(17, 24)}, **{h: 3.0 for h in range(0, 8)}, **quiet}))
        self.assertEqual(p["status"], "planned")
        self.assertAlmostEqual(p["planned_kwh"], 24.0, places=1)
        hours = {t.hour for t in p["quarters"]}
        self.assertTrue(hours <= {1, 2, 3, 4, 5}, hours)    # the quiet 02-05 first, a little beyond
        self.assertLessEqual(p["ready_at"], DEPART)

    def test_never_exceeds_the_peak_target(self):
        p = plan(load=load(default=6.0), need_kwh=10.0)     # room = 9.5 - 6.0 = 3.5 kW
        self.assertTrue(all(kw <= 3.5 + 1e-9 for kw in p["quarters"].values()))
        self.assertAlmostEqual(p["planned_kwh"], 10.0, places=1)

    def test_infeasible_says_how_much_is_missing(self):
        p = plan(load=load(default=9.0), need_kwh=40.0)     # room 0.5 kW, below the minimum: no quarter qualifies
        self.assertEqual(p["status"], "infeasible")
        self.assertEqual(p["planned_kwh"], 0.0)
        self.assertEqual(p["shortfall_kwh"], 40.0)

    def test_not_needed_and_no_departure(self):
        self.assertEqual(plan(need_kwh=0.0)["status"], "not_needed")
        self.assertEqual(plan(departure=NOW - timedelta(minutes=5))["status"], "no_departure")

    def test_available_power_comes_first(self):
        avail = {datetime(2027, 1, 12, 23, 0, tzinfo=TZ) + timedelta(minutes=15 * i): 4.0 for i in range(8)}   # 23-01 h
        p = plan(available_kw=avail, need_kwh=6.0)
        self.assertAlmostEqual(p["available_kwh"], 6.0, places=1)
        self.assertEqual(p["grid_kwh"], 0.0)
        self.assertTrue(all(t in avail for t in p["quarters"]))

    def test_without_peak_target_and_equal_load_the_later_quarters_win(self):
        p = plan(target_kw=None, load=load(default=1.0), need_kwh=5.5)   # 5.5 kWh at 11 kW = 2 quarters
        self.assertEqual(len(p["quarters"]), 2)
        self.assertEqual(p["ready_at"], DEPART)

    def test_no_load_forecast_at_all_still_plans(self):
        p = plan(load=None, target_kw=None, need_kwh=11.0)
        self.assertEqual(p["status"], "planned")
        self.assertAlmostEqual(p["planned_kwh"], 11.0, places=1)

    def test_running_quarter_counts_only_its_rest(self):
        p = plan(need_kwh=1.0, target_kw=None, load=load(default=0.0), now=datetime(2027, 1, 13, 6, 50, tzinfo=TZ))
        self.assertLessEqual(max(p["quarters"]), DEPART)

    def test_latest_start(self):
        p = plan(need_kwh=22.0)
        self.assertEqual(p["latest_start"], DEPART - timedelta(hours=2))

    def test_windows_merge_and_sum(self):
        p = plan(load=load(default=0.5), need_kwh=11.0, target_kw=None)
        self.assertAlmostEqual(sum(w["energy_kwh"] for w in p["windows"]), p["planned_kwh"], places=1)
        for a, b in zip(p["windows"], p["windows"][1:]):
            self.assertLess(a["end"], b["start"])

    def test_wallbox_minimum_is_respected(self):
        p = plan(need_kwh=0.2, target_kw=None, load=load(default=0.5))
        self.assertTrue(all(kw >= 1.4 for kw in p["quarters"].values()))

    def test_charging_allowed(self):
        p = plan(load=load(default=0.5), need_kwh=5.5, target_kw=None)
        planned = next(iter(p["quarters"]))
        self.assertTrue(charging_allowed(p, planned + timedelta(minutes=7)))
        self.assertFalse(charging_allowed(p, NOW))
        self.assertIsNone(charging_allowed(plan(need_kwh=0.0), NOW))


if __name__ == "__main__":
    unittest.main()
