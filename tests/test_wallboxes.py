"""Tests for several cars and several wallboxes."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

from plan import make_plan  # noqa: E402
from wallboxes import (  # noqa: E402
    active_wallbox, car_hourly, cumulative, plan_order, shared, soc_rise_hours, taken_by_others, wallbox_ids,
)

TZ = timezone(timedelta(hours=1))
NOW = datetime(2027, 1, 12, 17, 5, tzinfo=TZ)
DEPART = datetime(2027, 1, 13, 7, 0, tzinfo=TZ)
H = [datetime(2027, 1, 12, h, tzinfo=TZ) for h in range(24)]


def load(default=0.5):
    out, t = [], NOW.replace(minute=0)
    while t < DEPART + timedelta(hours=1):
        out.append({"t": t, "typical": default, "high": default, "n": 8})
        t += timedelta(minutes=15)
    return out


class WallboxListTest(unittest.TestCase):
    def test_ids_first_then_more_without_doubles(self):
        self.assertEqual(wallbox_ids("sensor.a", ["sensor.b", "sensor.a", "", None]), ["sensor.a", "sensor.b"])
        self.assertEqual(wallbox_ids(None, "sensor.b"), ["sensor.b"])
        self.assertEqual(wallbox_ids(None, None), [])

    def test_shared_counters(self):
        self.assertEqual(shared({"car1": ["sensor.a", "sensor.b"], "car2": ["sensor.b"], "car3": []}), {"sensor.b"})
        self.assertEqual(shared({"car1": ["sensor.a", "sensor.a"]}), set())


class EnergyPerCarTest(unittest.TestCase):
    def test_own_counter_counts_fully_and_quiet_hours_are_zero(self):
        out = car_hourly({"sensor.a": {H[1]: 3.0, H[2]: 0.0}}, set(), set())
        self.assertEqual(out, {H[1]: 3.0, H[2]: 0.0})

    def test_shared_counter_counts_only_while_the_soc_rose(self):
        rise = soc_rise_hours([(H[0], 40.0), (H[1], 40.5), (H[2], 50.0), (H[3], 60.0), (H[4], 60.0)])
        self.assertEqual(rise, {H[2], H[3]})
        # the other car charged at hour 6, this car at hours 2/3 (the hour before a rise counts too: the mean lags)
        out = car_hourly({"sensor.shared": {H[1]: 4.0, H[2]: 5.0, H[6]: 7.0}}, {"sensor.shared"}, rise)
        self.assertEqual(out, {H[1]: 4.0, H[2]: 5.0, H[6]: 0.0})

    def test_two_wallboxes_add_up_and_make_a_counter(self):
        out = car_hourly({"sensor.home": {H[1]: 2.0}, "sensor.work": {H[1]: 1.0, H[2]: 4.0}}, set(), set())
        self.assertEqual(cumulative(out), [(H[1], 3.0), (H[2], 7.0)])


class ActiveWallboxTest(unittest.TestCase):
    def test_one_wallbox_is_always_that_one(self):
        self.assertEqual(active_wallbox({}, {"sensor.a": 1.0}, False, None), "sensor.a")

    def test_the_rising_counter_while_charging(self):
        before = {"sensor.home": 100.0, "sensor.work": 50.0}
        self.assertEqual(active_wallbox(before, {"sensor.home": 100.0, "sensor.work": 50.8}, True, "sensor.home"), "sensor.work")

    def test_nothing_rises_or_not_charging_keeps_the_last(self):
        before = {"sensor.home": 100.0, "sensor.work": 50.0}
        self.assertEqual(active_wallbox(before, {"sensor.home": 100.0, "sensor.work": 50.0}, True, "sensor.work"), "sensor.work")
        self.assertEqual(active_wallbox(before, {"sensor.home": 103.0, "sensor.work": 50.0}, False, "sensor.work"), "sensor.work")
        self.assertIsNone(active_wallbox({}, {"sensor.home": 1.0, "sensor.work": 2.0}, True, None))


class OrderTest(unittest.TestCase):
    def test_plugged_first_then_departure_then_name(self):
        cars = [
            {"id": "b", "plugged": False, "departure": DEPART, "name": "B"},
            {"id": "a", "plugged": True, "departure": DEPART + timedelta(days=1), "name": "A"},
            {"id": "c", "plugged": False, "departure": DEPART - timedelta(hours=2), "name": "C"},
            {"id": "d", "plugged": None, "departure": None, "name": "D"},
        ]
        self.assertEqual(plan_order(cars), ["a", "c", "b", "d"])


class TwoCarsPlanTest(unittest.TestCase):
    def test_second_car_stays_under_the_target_with_the_first(self):
        first = make_plan(NOW, DEPART, 30.0, 11.0, 1.4, load=load(), target_kw=8.0, pref_kw=4.0)
        others, blocked = taken_by_others([({"sensor.a"}, first["quarters"])], {"sensor.b"})
        self.assertFalse(blocked)   # another wallbox: only the peak is shared
        second = make_plan(NOW, DEPART, 20.0, 11.0, 1.4, load=load(), target_kw=8.0, others_kw=others, pref_kw=4.0)
        for t, kw in second["quarters"].items():
            self.assertLessEqual(0.5 + others.get(t, 0.0) + kw, 8.0 + 1e-6, t)
        self.assertEqual(second["status"], "planned")
        # without knowing the first car the second one would have planned above the target
        alone = make_plan(NOW, DEPART, 20.0, 11.0, 1.4, load=load(), target_kw=8.0, pref_kw=4.0)
        self.assertTrue(any(0.5 + others.get(t, 0.0) + kw > 8.0 + 1e-6 for t, kw in alone["quarters"].items()))

    def test_shared_wallbox_never_at_the_same_time(self):
        # at a shared wallbox the plans are compact (full power), so that both fit into the night
        first = make_plan(NOW, DEPART, 20.0, 11.0, 1.4, load=load(), target_kw=20.0, pref_kw=8.25)
        others, blocked = taken_by_others([({"sensor.shared"}, first["quarters"])], {"sensor.shared"})
        self.assertEqual(blocked, set(first["quarters"]))
        second = make_plan(NOW, DEPART, 15.0, 11.0, 1.4, load=load(), target_kw=20.0, others_kw=others, blocked=blocked, pref_kw=8.25)
        self.assertFalse(set(second["quarters"]) & set(first["quarters"]))
        self.assertGreater(second["planned_kwh"], 14.9)

    def test_sun_goes_to_the_first_car(self):
        sun = {NOW.replace(minute=0) + timedelta(hours=1, minutes=15 * i): 5.0 for i in range(4)}
        others = {t: 5.0 for t in sun}   # the first car takes all of it
        second = make_plan(NOW, DEPART, 5.0, 11.0, 1.4, available_kw=sun, others_kw=others)
        self.assertEqual(second["available_kwh"], 0.0)


if __name__ == "__main__":
    unittest.main()
