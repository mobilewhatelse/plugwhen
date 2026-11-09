"""Tests for evcc as an optional source (read only)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# the integration folder has a select.py that would hide the standard module asyncio needs: load asyncio without it on the path
_INTEGRATION = str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen")
_saved = [p for p in sys.path if p == _INTEGRATION]
for _p in _saved:
    sys.path.remove(_p)
import asyncio  # noqa: E402

sys.path.insert(0, _INTEGRATION)

from evcc import (  # noqa: E402
    EvccAuthError, EvccClient, EvccError, connection, live_vehicle, loadpoint_kw, match_vehicle, parse_vehicles, vehicle_from_evcc,
)

# shaped like evcc 0.319 (demo and a real installation)
STATE = {
    "vehicles": {
        "db:3": {"title": "Mercedes", "capacity": 66, "features": ["Streaming"]},
        "vehicle_2": {"title": "white Model 3", "capacity": 80},
        "broken": "x",
    },
    "loadpoints": [
        {"title": "Carport", "vehicleName": "db:3", "connected": True, "charging": True, "chargePower": 7360.0,
         "minCurrent": 6, "maxCurrent": 16, "chargerPhases1p3p": True, "phasesConfigured": 0},
        {"title": "Garage", "vehicleName": "", "connected": False, "charging": False, "chargePower": 0,
         "minCurrent": 6, "maxCurrent": 32, "chargerPhases1p3p": False, "phasesConfigured": 3},
    ],
}


class ConnectionTest(unittest.TestCase):
    def test_own_address_wins(self):
        self.assertEqual(connection("192.168.1.5:7070", "pw", {"evcc_site_url": "http://other:7070"}), ("http://192.168.1.5:7070", "pw", "own"))

    def test_guard_address_with_its_password(self):
        self.assertEqual(connection("", None, {"evcc_site_url": "http://evcc.local:7070/", "evcc_site_password": "g"}),
                         ("http://evcc.local:7070", "g", "guard"))

    def test_own_address_never_takes_the_guards_password(self):
        self.assertEqual(connection("http://a:7070", None, {"evcc_site_url": "http://b:7070", "evcc_site_password": "g"}),
                         ("http://a:7070", None, "own"))

    def test_without_evcc(self):
        self.assertIsNone(connection(None, None, None))
        self.assertIsNone(connection(" ", None, {"evcc_site_url": ""}))


class ParseTest(unittest.TestCase):
    def test_vehicles(self):
        v = parse_vehicles(STATE)
        self.assertEqual([x["key"] for x in v], ["broken"][:0] + ["db:3", "vehicle_2"])
        self.assertEqual(v[0], {"key": "db:3", "title": "Mercedes", "capacity_kwh": 66.0})
        self.assertEqual(parse_vehicles(None), [])
        self.assertEqual(parse_vehicles({"vehicles": []}), [])

    def test_loadpoint_power(self):
        self.assertEqual(loadpoint_kw(STATE["loadpoints"][0]), (1.4, 11.0))     # can switch to one phase
        self.assertEqual(loadpoint_kw(STATE["loadpoints"][1]), (4.1, 22.1))     # three phases only
        self.assertEqual(loadpoint_kw({"minCurrent": 6, "maxCurrent": 16, "phasesConfigured": 1}), (1.4, 3.7))
        self.assertIsNone(loadpoint_kw({"minCurrent": 0, "maxCurrent": 16}))
        self.assertIsNone(loadpoint_kw(None))

    def test_vehicle_settings(self):
        self.assertEqual(vehicle_from_evcc(STATE, "db:3"),
                         {"evcc_vehicle": "db:3", "name": "Mercedes", "capacity_kwh": 66.0, "charge_kw_min": 1.4, "charge_kw_max": 11.0})
        out = vehicle_from_evcc(STATE, "vehicle_2")    # not at a loadpoint: the first loadpoint's power
        self.assertEqual((out["name"], out["charge_kw_max"]), ("white Model 3", 11.0))
        self.assertEqual(vehicle_from_evcc(STATE, "nope"), {})

    def test_match_by_name_else_first_free(self):
        self.assertEqual(match_vehicle(STATE, "mercedes ", set()), "db:3")
        self.assertEqual(match_vehicle(STATE, "Golf", set()), "db:3")
        self.assertEqual(match_vehicle(STATE, None, {"db:3"}), "vehicle_2")
        self.assertIsNone(match_vehicle(STATE, None, {"db:3", "vehicle_2"}))

    def test_car_at_a_loadpoint_before_the_alphabet(self):
        st = {"vehicles": {"bike": {"title": "black VanMoof", "capacity": 0.46}, "golf": {"title": "blue e-Golf", "capacity": 44},
                           "tesla": {"title": "white Model 3", "capacity": 80}},
              "loadpoints": [{"vehicleName": "golf"}, {"vehicleName": "tesla"}, {"vehicleName": ""}]}
        self.assertEqual(match_vehicle(st, None, set()), "golf")
        self.assertEqual(match_vehicle(st, None, {"golf"}), "tesla")
        self.assertEqual(match_vehicle(st, None, {"golf", "tesla"}), "bike")

    def test_live_values(self):
        self.assertEqual(live_vehicle(STATE, "db:3"), {"plugged": True, "charging": True, "power_kw": 7.36})
        self.assertIsNone(live_vehicle(STATE, "vehicle_2"))     # evcc does not know where this car is


class _Resp:
    def __init__(self, status, text, cookie=None):
        self.status, self._text, self.cookies = status, text, ({"auth": cookie} if cookie else {})

    async def text(self):
        return self._text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class _Session:
    def __init__(self, answers):
        self.answers, self.calls = list(answers), []

    def request(self, method, url, **kw):
        self.calls.append((method, url, kw.get("headers"), kw.get("json")))
        return self.answers.pop(0)


class ClientTest(unittest.TestCase):
    def run_(self, coro):
        return asyncio.run(coro)

    def test_state_with_result_wrapper(self):
        s = _Session([_Resp(200, '{"result": {"vehicles": {}}}')])
        self.assertEqual(self.run_(EvccClient(s, "evcc:7070").state()), {"vehicles": {}})
        self.assertEqual(s.calls[0][1], "http://evcc:7070/api/state")

    def test_logs_in_when_asked(self):
        s = _Session([_Resp(401, "no"), _Resp(200, "", cookie="abc"), _Resp(200, "{}")])
        self.run_(EvccClient(s, "http://evcc", "pw").state())
        self.assertEqual(s.calls[1][3], {"password": "pw"})
        self.assertEqual(s.calls[2][2], {"Cookie": "auth=abc"})

    def test_errors(self):
        with self.assertRaises(EvccAuthError):
            self.run_(EvccClient(_Session([_Resp(401, "no")]), "http://evcc").state())
        with self.assertRaises(EvccError):
            self.run_(EvccClient(_Session([_Resp(500, "boom")]), "http://evcc").state())
        with self.assertRaises(EvccError):
            self.run_(EvccClient(_Session([_Resp(200, "<html>")]), "http://evcc").state())


if __name__ == "__main__":
    unittest.main()
