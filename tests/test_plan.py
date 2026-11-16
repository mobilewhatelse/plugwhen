"""Tests for the charging plan."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

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
        quiet_kw = [kw for t, kw in p["quarters"].items() if t.hour in quiet]
        busy_kw = [kw for t, kw in p["quarters"].items() if t.hour not in quiet]
        self.assertGreater(min(quiet_kw), max(busy_kw))     # the quiet 02-05 get the most
        house = {t: (0.3 if t.hour in quiet else 3.0) for t in p["quarters"]}
        self.assertLess(max(kw + house[t] for t, kw in p["quarters"].items()), 5.0)   # not 8 kW in three hours
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

    def test_without_peak_target_the_rest_is_spread_not_bunched(self):
        p = plan(target_kw=None, load=load(default=1.0), need_kwh=24.0)   # 24 kWh over ~14 h
        self.assertAlmostEqual(p["planned_kwh"], 24.0, places=1)
        self.assertLess(max(p["quarters"].values()), 2.5)                # not 11 kW at the end
        self.assertGreater(len(p["quarters"]), 40)

    def test_spread_tops_up_to_one_level(self):
        busy = {h: 4.0 for h in (17, 18, 19, 20, 21)}                     # evening: the house uses a lot
        p = plan(target_kw=None, load=load(busy, default=0.5), need_kwh=24.0)
        totals = [kw + (4.0 if t.hour in busy else 0.5) for t, kw in p["quarters"].items()]
        self.assertLess(max(totals) - min(totals), 0.05)                 # house plus car: one level everywhere
        self.assertTrue(all(t.hour not in busy for t in p["quarters"]))

    def test_small_need_uses_few_late_quarters_at_least_the_minimum(self):
        p = plan(target_kw=None, load=load(default=1.0), need_kwh=5.5)
        self.assertTrue(all(kw >= 1.4 for kw in p["quarters"].values()))
        self.assertAlmostEqual(p["planned_kwh"], 5.5, places=1)
        self.assertEqual(p["ready_at"], DEPART)

    def test_sun_first_then_spread_at_night(self):
        avail = {datetime(2027, 1, 12, 18, 0, tzinfo=TZ) + timedelta(minutes=15 * i): 3.0 for i in range(4)}   # 18-19 h
        p = plan(available_kw=avail, target_kw=None, load=load(default=0.5), need_kwh=20.0)
        self.assertAlmostEqual(p["available_kwh"], 3.0, places=1)
        self.assertAlmostEqual(p["planned_kwh"], 20.0, places=1)
        night = [kw for t, kw in p["quarters"].items() if t not in avail]
        self.assertLess(max(night), 2.5)

    def test_grid_energy_is_planned_behind_the_sun_when_it_fits(self):
        """Review of 0.10: with sun at midday the grid part was also put into the morning before it. A battery filled from the
        grid in the morning has no room for a sun that turns out stronger than forecast."""
        now = datetime(2027, 6, 12, 8, 0, tzinfo=TZ)
        dep = now + timedelta(hours=23)                                   # tomorrow 07:00
        sun = {now + timedelta(hours=3, minutes=15 * k): 5.0 for k in range(12)}   # 11:00 to 14:00, 15 kWh
        quiet_morning = [{"t": now + timedelta(minutes=15 * k), "typical": 0.1, "high": 0.2 if k < 12 else 1.5, "n": 4}
                         for k in range(92)]                              # the house is quietest before the sun comes
        p = make_plan(now, dep, 30.0, 11.0, 1.4, available_kw=sun, pref_kw=4.0, load=quiet_morning)
        self.assertEqual(p["status"], "planned")
        self.assertAlmostEqual(p["available_kwh"], 15.0, places=1)
        grid = [t for t in p["quarters"] if t not in sun]
        self.assertGreater(min(grid), max(sun))                           # nothing from the grid before or during the sun
        self.assertLessEqual(max(p["quarters"][t] for t in grid), 4.05)   # and no higher power than the preferred one

    def test_when_it_does_not_fit_behind_the_sun_the_whole_time_is_used(self):
        now = datetime(2027, 6, 12, 8, 0, tzinfo=TZ)
        dep = now + timedelta(hours=7)                                    # 15:00, one hour after the sun
        sun = {now + timedelta(hours=3, minutes=15 * k): 5.0 for k in range(12)}
        p = make_plan(now, dep, 30.0, 11.0, 1.4, available_kw=sun, pref_kw=4.0)
        self.assertEqual(p["status"], "planned")
        self.assertAlmostEqual(p["planned_kwh"], 30.0, places=1)
        self.assertLess(min(t for t in p["quarters"] if t not in sun), min(sun))   # the morning is needed too

    def test_behind_the_sun_never_means_a_higher_power(self):
        now = datetime(2027, 6, 12, 8, 0, tzinfo=TZ)
        dep = now + timedelta(hours=8)                                    # two hours after the sun: 15 kWh would need 7.5 kW there
        sun = {now + timedelta(hours=3, minutes=15 * k): 5.0 for k in range(12)}
        p = make_plan(now, dep, 30.0, 11.0, 1.4, available_kw=sun, pref_kw=4.0)
        grid = [t for t in p["quarters"] if t not in sun]
        self.assertLess(max(p["quarters"][t] for t in grid), 6.0)         # spread over morning and afternoon instead
        self.assertLess(min(grid), min(sun))

    def test_behind_the_sun_only_if_everything_fits_there_when_the_sun_fails(self):
        """Review: the forecast promises 25 of the 30 kWh, the grid part of 5 kWh would fit into the two hours behind the sun.
        But if the sun fails, 30 kWh do not fit into two hours: then the quiet morning is used, as before."""
        now = datetime(2027, 6, 12, 8, 0, tzinfo=TZ)
        dep = now + timedelta(hours=8)                                    # 16:00, two hours behind the sun
        sun = {now + timedelta(hours=1, minutes=15 * k): 5.0 for k in range(20)}   # 09:00 to 14:00, 25 kWh
        quiet_morning = [{"t": now + timedelta(minutes=15 * k), "typical": 0.1, "high": 0.2 if k < 4 else 1.5, "n": 4}
                         for k in range(32)]
        p = make_plan(now, dep, 30.0, 11.0, 1.4, available_kw=sun, pref_kw=4.0, load=quiet_morning)
        self.assertEqual(p["status"], "planned")
        grid = [t for t in p["quarters"] if t not in sun]
        self.assertLess(min(grid), min(sun))                              # the morning: not everything is left to the end
        # with four hours behind the sun everything would fit there (44 kWh at 11 kW): then the grid part waits
        later = make_plan(now, dep + timedelta(hours=2), 30.0, 11.0, 1.4, available_kw=sun, pref_kw=4.0,
                          load=quiet_morning + [{"t": dep + timedelta(minutes=15 * k), "typical": 0.1, "high": 1.5, "n": 4} for k in range(8)])
        self.assertGreater(min(t for t in later["quarters"] if t not in sun), max(sun))

    def test_without_sun_only_spread(self):
        p = plan(available_kw=None, target_kw=None, load=None, need_kwh=20.0)
        self.assertEqual(p["available_kwh"], 0.0)
        self.assertLess(max(p["quarters"].values()), 2.0)

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

    def test_preferred_power_is_not_undercut_when_the_energy_fits(self):
        p = plan(target_kw=None, load=load(default=1.0), need_kwh=12.0, pref_kw=4.0)       # 12 kWh fit easily at 4 kW
        self.assertTrue(all(kw >= 4.0 - 1e-6 for kw in p["quarters"].values()), min(p["quarters"].values()))
        self.assertAlmostEqual(p["planned_kwh"], 12.0, places=1)
        self.assertEqual(p["spread_floor_kw"], 4.0)

    def test_preferred_power_gives_way_when_the_peak_target_leaves_less_room(self):
        # the house takes 7 kW all night, the target is 9.5 kW: only 2.5 kW are left for the car, below the preferred 4 kW
        p = plan(load=load(default=7.0), need_kwh=10.0, pref_kw=4.0)
        self.assertEqual(p["status"], "planned")
        self.assertAlmostEqual(p["planned_kwh"], 10.0, places=1)
        self.assertTrue(all(kw <= 2.5 + 1e-9 for kw in p["quarters"].values()))
        self.assertEqual(p["spread_floor_kw"], 1.4)

    def test_charging_allowed(self):
        p = plan(load=load(default=0.5), need_kwh=5.5, target_kw=None)
        planned = next(iter(p["quarters"]))
        self.assertTrue(charging_allowed(p, planned + timedelta(minutes=7)))
        self.assertFalse(charging_allowed(p, NOW))
        self.assertIsNone(charging_allowed(plan(need_kwh=0.0), NOW))


if __name__ == "__main__":
    unittest.main()
