"""Tests for taking over the guard's vehicle and wallbox."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

from takeover import guard_wallbox, next_vehicle, pick_by_unit, sensor_by_value, vehicle_from_guard, wallbox_kw  # noqa: E402

CAR = {"kind": "vehicle", "name": "Mercedes", "soc_entity": "sensor.car_soc", "capacity_kwh": 66.0, "charge_kw_max": 11.0,
       "charge_kw_min": 1.4, "departure_entity": "time.wallbox_departure", "connected_entity": "binary_sensor.car_plug", "target_soc": 80.0}
WALLBOX = {"kind": "wallbox", "name": "Wallbox", "min_current": 6, "max_current": 16, "one_phase_option": "1 Phase",
           "phase_entity": "select.wallbox_phases", "power_entity": "sensor.wallbox_power"}
SWITCH = {"kind": "switch", "name": "Pool"}


class WallboxTest(unittest.TestCase):
    def test_one_phase_possible(self):
        self.assertEqual(wallbox_kw(WALLBOX), (1.4, 11.0))

    def test_three_phases_only(self):
        self.assertEqual(wallbox_kw({"min_current": 6, "max_current": 16}), (4.1, 11.0))

    def test_evcc_loadpoint_counts_as_wallbox(self):
        devices = [SWITCH, {"kind": "evcc", "min_current": 6, "max_current": 32, "evcc_one_phase": True}]
        self.assertEqual(wallbox_kw(guard_wallbox(devices)), (1.4, 22.1))

    def test_broken_currents(self):
        self.assertIsNone(wallbox_kw(None))
        self.assertIsNone(wallbox_kw({"min_current": "x", "max_current": 16}))
        self.assertIsNone(wallbox_kw({"min_current": 20, "max_current": 16}))
        self.assertIsNone(wallbox_kw({"max_current": 16}))


class VehicleTest(unittest.TestCase):
    def test_car_values_are_taken_over(self):
        out = vehicle_from_guard(CAR, [CAR, WALLBOX], "notify.mobile_app_a, notify.mobile_app_b")
        self.assertEqual(out["name"], "Mercedes")
        self.assertEqual(out["soc_entity"], "sensor.car_soc")
        self.assertEqual(out["capacity_kwh"], 66.0)
        self.assertEqual(out["plugged_entity"], "binary_sensor.car_plug")
        self.assertEqual(out["notify_service"], "notify.mobile_app_a, notify.mobile_app_b")

    def test_departure_is_not_taken_over(self):
        # an entity departure replaces the learned one in Plugwhen; a wallbox's fixed time would switch learning off
        self.assertNotIn("departure_entity", vehicle_from_guard(CAR, [CAR]))

    def test_car_power_wins_over_the_wallbox(self):
        car = {**CAR, "charge_kw_max": 7.4}
        self.assertEqual(vehicle_from_guard(car, [car, WALLBOX])["charge_kw_max"], 7.4)

    def test_wallbox_fills_missing_car_power(self):
        car = {k: v for k, v in CAR.items() if not k.startswith("charge_kw")}
        out = vehicle_from_guard(car, [car, WALLBOX])
        self.assertEqual((out["charge_kw_min"], out["charge_kw_max"]), (1.4, 11.0))

    def test_only_keys_with_values(self):
        out = vehicle_from_guard({"kind": "vehicle", "name": "A", "soc_entity": "sensor.a", "connected_entity": ""}, [])
        self.assertEqual(out, {"name": "A", "soc_entity": "sensor.a"})

    def test_notify_without_service_is_dropped(self):
        self.assertNotIn("notify_service", vehicle_from_guard(CAR, [CAR], "  ,nonsense "))


class NextVehicleTest(unittest.TestCase):
    def test_first_one_not_taken(self):
        second = {**CAR, "name": "Zweitauto", "soc_entity": "sensor.second_soc"}
        devices = [WALLBOX, CAR, second]
        self.assertEqual(next_vehicle(devices, set())["name"], "Mercedes")
        self.assertEqual(next_vehicle(devices, {"sensor.car_soc"})["name"], "Zweitauto")
        self.assertIsNone(next_vehicle(devices, {"sensor.car_soc", "sensor.second_soc"}))

    def test_without_guard_vehicles(self):
        self.assertIsNone(next_vehicle([WALLBOX, SWITCH], set()))
        self.assertIsNone(next_vehicle([{"kind": "vehicle", "name": "no soc"}], set()))


class PickTest(unittest.TestCase):
    def test_odometer_wins_over_the_range(self):
        c = [("sensor.car_soc", "%", "measurement"), ("sensor.car_a_range", "km", "measurement"),
             ("sensor.car_odometer", "km", "total_increasing"), ("sensor.car_temp", "°C", "measurement")]
        self.assertEqual(pick_by_unit(c, ("km", "mi")), "sensor.car_odometer")

    def test_without_state_class_the_id_decides(self):
        self.assertEqual(pick_by_unit([("sensor.b", "km", None), ("sensor.a", "km", None)], ("km",)), "sensor.a")

    def test_exclude_and_case(self):
        c = [("sensor.a", "KM", "total"), ("sensor.b", "km", None)]
        self.assertEqual(pick_by_unit(c, ("km",), exclude={"sensor.a"}), "sensor.b")
        self.assertIsNone(pick_by_unit([("sensor.a", None, "total")], ("km",)))


class ByValueTest(unittest.TestCase):
    """evcc knows odometer and state of charge of the car at its loadpoint: the sensor in Home Assistant with the same value is the car's."""

    def test_the_sensor_with_the_same_value(self):
        c = [("sensor.car_odometer", 61812.0, True), ("sensor.trip", 43.0, True), ("sensor.other_car_km", 20500.0, True)]
        self.assertEqual(sensor_by_value(c, 61813.2, 2.0), "sensor.car_odometer")

    def test_the_cars_own_sensor_before_a_copy_of_evcc(self):
        c = [("sensor.evcc_vehicle_odometer", 61812.0, False), ("sensor.car_odometer", 61812.0, True)]
        self.assertEqual(sensor_by_value(c, 61812.0, 2.0), "sensor.car_odometer")
        self.assertEqual(sensor_by_value(c[:1], 61812.0, 2.0), "sensor.evcc_vehicle_odometer")   # better than nothing

    def test_nothing_when_unclear_or_missing(self):
        two = [("sensor.a", 62.0, True), ("sensor.b", 61.0, True)]
        self.assertIsNone(sensor_by_value(two, 62.0, 2.5))
        self.assertIsNone(sensor_by_value(two, None, 2.5))
        self.assertIsNone(sensor_by_value([("sensor.a", 10.0, True)], 62.0, 2.5))


if __name__ == "__main__":
    unittest.main()
