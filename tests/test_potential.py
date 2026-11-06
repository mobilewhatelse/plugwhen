"""Tests for the potential calculator."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

from potential import Prices, calculate, find_sessions  # noqa: E402

TZ = timezone(timedelta(hours=1))
D0 = datetime(2027, 1, 4, 0, 0, tzinfo=TZ)   # Monday
H = timedelta(hours=1)


def household(days=21, charge_hours=(4, 5, 6), kwh_per_hour=None, house_kw=0.5, arrive=18, leave=7):
    """Every day the car comes home at `arrive`, leaves at `leave`; it charges in `charge_hours` (default: at full power,
    20 kWh in total, like a wallbox that starts late before departure)."""
    grid, car, trips = {}, {}, []
    per = kwh_per_hour or {h: 20.0 / len(charge_hours) for h in charge_hours}
    for d in range(days):
        day = D0 + timedelta(days=d)
        trips.append(day + timedelta(hours=leave))
        trips.append(day + timedelta(hours=arrive - 1))   # the trip home
        for h in range(24):
            t = day + timedelta(hours=h)
            c = per.get(h, 0.0)
            car[t] = c
            grid[t] = house_kw + c
    return grid, car, trips


AT = Prices(low=33.82, high=67.64, threshold=10.0)
LATE = {4: 10.5, 5: 9.5}   # 20 kWh in two hours at (almost) full power, just before leaving at 7


class SessionTest(unittest.TestCase):
    def test_window_starts_when_the_car_was_parked(self):
        grid, car, trips = household(days=3)
        s = find_sessions(grid, car, trips)
        self.assertEqual(len(s), 3)
        self.assertEqual(s[1].start.hour, 4)
        self.assertEqual(s[1].window_start.hour, 18)                     # parked the evening before
        self.assertEqual(s[1].leave.hour, 7)
        self.assertAlmostEqual(s[1].grid_kwh, 20.0, places=3)

    def test_recorded_plug_times_make_the_window_real(self):
        grid, car, trips = household(days=3, charge_hours=(4, 5), kwh_per_hour=LATE)
        day = D0 + timedelta(days=1)
        plugged = [(day - timedelta(hours=1, minutes=40), day + timedelta(hours=6, minutes=50))]   # 22:20 to 06:50
        s = find_sessions(grid, car, trips, plugged)
        self.assertTrue(s[1].plug_known)
        self.assertEqual(s[1].window_start.hour, 23)                     # first full hour after plugging in
        self.assertEqual(s[1].leave.hour, 6)                             # unplugged at 06:50
        self.assertFalse(s[0].plug_known)                                # no record: assumed from arrival
        self.assertEqual(s[2].window_start.hour, 18)

    def test_plugged_in_late_means_little_to_spread(self):
        grid, car, trips = household(days=21, charge_hours=(4, 5), kwh_per_hour=LATE)
        plugged = [(D0 + timedelta(days=d, hours=3, minutes=55), D0 + timedelta(days=d, hours=6, minutes=50)) for d in range(21)]
        free = calculate(grid, car, trips, prices=AT)
        late = calculate(grid, car, trips, prices=AT, plugged=plugged)
        self.assertEqual(late["sessions_with_plug_times"], late["sessions"])
        self.assertGreater(late["peak_spread_kw"], free["peak_spread_kw"] + 2)   # only 4-6 h to spread in

    def test_windows_never_overlap(self):
        grid, car, trips = household(days=5)
        s = find_sessions(grid, car, trips)
        for a, b in zip(s, s[1:]):
            self.assertLessEqual(a.leave, b.window_start)


class CalculateTest(unittest.TestCase):
    def test_late_full_power_charging_is_worth_spreading(self):
        r = calculate(*household(kwh_per_hour=LATE, charge_hours=(4, 5)), prices=AT, guard_kw=6.5)
        self.assertEqual(r["status"], "ok")
        self.assertAlmostEqual(r["peak_as_is_kw"], 0.5 + 0.7 + 11.0, places=1)
        self.assertLess(r["peak_spread_kw"], 3.0)                         # 20 kWh over 13 h
        self.assertEqual(r["strategies"]["spread"]["not_ready"], 0)
        self.assertGreater(r["saving_spread_per_year"], 100)
        self.assertEqual(r["verdict"], "worth_it")

    def test_a_guard_alone_cannot_catch_up_a_late_start(self):
        r = calculate(*household(kwh_per_hour=LATE, charge_hours=(4, 5)), guard_kw=6.5)
        g = r["strategies"]["guard"]
        self.assertLessEqual(max(g["peaks"].values()), 6.5 + 1e-6)
        self.assertGreater(g["not_ready"], 0)                              # 2-3 hours at about 5 kW are not 20 kWh

    def test_already_spread_charging_has_little_potential(self):
        hours = {h: 1.6 for h in list(range(19, 24)) + list(range(0, 7))}  # 1.6 kW all night
        r = calculate(*household(kwh_per_hour=hours, charge_hours=tuple(hours)))
        self.assertEqual(r["verdict"], "little")

    def test_wallbox_setting_is_enough_when_the_need_fills_the_night(self):
        hours = {h: 30.0 / 4 for h in (3, 4, 5, 6)}                        # 30 kWh in 9 h: spread 3.3 kW, fixed 4.1 kW
        r = calculate(*household(kwh_per_hour=hours, charge_hours=tuple(hours), arrive=22), fixed_kw=4.1)
        self.assertIn(r["verdict"], ("setting_enough", "worth_it"))
        self.assertEqual(r["strategies"]["fixed"]["not_ready"], 0)

    def test_too_little_data(self):
        r = calculate(*household(days=5))
        self.assertEqual(r["status"], "too_little_data")
        self.assertNotIn("verdict", r)

    def test_no_prices_no_money(self):
        r = calculate(*household())
        self.assertNotIn("saving_spread_per_year", r)
        self.assertNotIn("cost_per_year", r["strategies"]["as_is"])

    def test_model_check_against_measured_peaks(self):
        g, c, t = household(kwh_per_hour=LATE, charge_hours=(4, 5))
        r = calculate(g, c, t, measured_peaks={"2027-01": 12.0})
        self.assertAlmostEqual(r["model_error_kw"], 0.2, places=1)

    def test_pv_charging_stays_where_it_was(self):
        # car charges at noon from the sun: the grid shows nothing, there is no grid energy to move
        grid, car, trips = {}, {}, []
        for d in range(21):
            day = D0 + timedelta(days=d)
            trips.append(day + timedelta(hours=7))
            for h in range(24):
                t = day + timedelta(hours=h)
                car[t] = 5.0 if 11 <= h < 14 else 0.0
                grid[t] = 0.0 if 11 <= h < 14 else 0.3                    # the sun covers the car and the house
        r = calculate(grid, car, trips)
        self.assertEqual(r["status"], "too_little_data")                  # no grid sessions at all


class PricesTest(unittest.TestCase):
    def test_two_level_tariff(self):
        self.assertAlmostEqual(AT.monthly(12.0), (10 * 33.82 + 2 * 67.64) / 12, places=4)
        self.assertAlmostEqual(AT.monthly(5.0), 5 * 33.82 / 12, places=4)

    def test_single_price_with_minimum(self):
        be = Prices(low=52.0, high=52.0, minimum_kw=2.5)
        self.assertAlmostEqual(be.monthly(1.0), 2.5 * 52 / 12, places=4)
        self.assertAlmostEqual(be.monthly(6.0), 6 * 52 / 12, places=4)


if __name__ == "__main__":
    unittest.main()
