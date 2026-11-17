"""Coordinator: what Plugwhen sets on the wallbox and gives back (code review of 16.11.2026).

* a wallbox that is not reachable is left alone, nothing is forgotten, nothing counts as written;
* a change by hand is respected until the coming departure;
* a value that never showed up (slow wallbox over the cloud) is waited for and then sent again;
* evcc's loadpoint mode is given back after "charge now", also when evcc is read less often than Plugwhen acts.

Runs in the Home Assistant image (imports homeassistant), found by tests/install/run_coordinator_tests.py.
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from custom_components.plugwhen import coordinator as co  # noqa: E402
from custom_components.plugwhen.need import Need  # noqa: E402

TZ = timezone(timedelta(hours=1))
DEP = datetime(2026, 11, 17, 7, 0, tzinfo=TZ)
T0 = DEP - timedelta(hours=10)
MODE = "select.wb_mode"
CAPS_TRIP = {"variant": "trip", "mode": MODE, "mode_grid": "Default", "mode_sun": "Eco", "mode_trip": "NextTrip",
             "trip_time": "time.wb_trip", "trip_energy": "number.wb_energy", "trip_energy_unit": "kWh"}


def plugwhen(states: dict[str, str], caps: dict | None = None, follow: bool = True) -> co.Plugwhen:
    """`follow` = the wallbox shows what was set at once (False: a slow wallbox, the state stays)."""
    p = co.Plugwhen.__new__(co.Plugwhen)
    p.states = states
    p.hass = SimpleNamespace(config=SimpleNamespace(language="de"),
                             states=SimpleNamespace(get=lambda e: SimpleNamespace(state=states[e]) if e in states else None))
    p._sent, p._direct, p._evcc_data = {}, {}, {}
    p._store = p._evcc_store = SimpleNamespace(async_delay_save=lambda *a, **k: None)
    p.diag: list[str] = []
    p._diag_action = lambda v, now, text: p.diag.append(text)
    p.efficiency_of = lambda v: 0.9
    p.wallbox_control = lambda v: caps or CAPS_TRIP
    p.evcc_connection = lambda: None
    p.evcc_state = None
    p.written: list[tuple[str, object]] = []

    async def set_entity(eid, value):
        if states.get(eid) in ("unavailable", "unknown"):
            raise AssertionError(f"command to {eid} although it is not reachable")
        p.written.append((eid, value))
        if follow and value is not None:
            states[eid] = str(value)
    p._set_entity = set_entity
    return p


def car(mode: str = "direct", charge_kwh: float = 0.0) -> co.Vehicle:
    v = co.Vehicle("sub", "Auto", {co.V_CAPACITY: 66, co.V_CHARGE_MAX: 11})
    v.mode, v.soc, v.plugged, v.charging, v.departure = mode, 50.0, True, False, DEP
    v.need = Need(km=100, kwh=20, target_soc=60.0, charge_kwh=charge_kwh, reachable=True, source="learned")
    return v


def run(coro):
    return asyncio.run(coro)


class NotReachableTests(unittest.TestCase):
    def test_left_alone_and_nothing_forgotten(self):
        # the Wi-Fi restarts every night at 03:10: before, "unavailable" counted as a change by the user, the next run sent
        # into the void and remembered "unavailable" as the mode to give back
        states = {MODE: "Default"}
        p, v = plugwhen(states), car()
        run(p._own(v, MODE, "Eco", T0))
        self.assertEqual(states[MODE], "Eco")
        states[MODE] = "unavailable"
        for k in (1, 2, 3):
            self.assertIsNone(run(p._own(v, MODE, "Eco", T0 + timedelta(minutes=5 * k))))
        self.assertEqual(p._direct["sub"][MODE]["orig"], "Default")
        states[MODE] = "Eco"   # back as it was
        run(p._own(v, MODE, "Eco", T0 + timedelta(minutes=30)))
        self.assertEqual(run(p._own(v, MODE, None, T0 + timedelta(hours=1))), f"{MODE}=Default")   # given back
        self.assertNotIn(MODE, p._direct["sub"])

    def test_a_record_of_an_earlier_version_with_unavailable_is_dropped_without_an_error(self):
        states = {MODE: "Eco"}
        p, v = plugwhen(states), car("learn")
        p._direct["sub"] = {MODE: {"set": "Eco", "orig": "unavailable"}}
        run(p._direct_step(v, T0))
        self.assertEqual(p.written, [])
        self.assertNotIn(MODE, p._direct["sub"])
        self.assertIsNone(v.direct_last)   # no error

    def test_trip_values_are_not_written_and_do_not_count_as_written(self):
        states = {MODE: "unavailable", "time.wb_trip": "unavailable", "number.wb_energy": "unavailable"}
        p, v = plugwhen(states), car(charge_kwh=12.0)
        run(p._direct_step(v, T0))
        self.assertEqual(p.written, [])
        self.assertNotIn("trip_written", p._direct.get("sub", {}))
        states.update({MODE: "Eco", "time.wb_trip": "06:00:00", "number.wb_energy": "3.0"})
        run(p._direct_step(v, T0 + timedelta(minutes=5)))
        self.assertIn(("number.wb_energy", 12.0), p.written)
        self.assertIn((MODE, "NextTrip"), p.written)

    def test_a_value_already_there_counts_as_written(self):
        # after a restart the value in the wallbox is the planned one: the next small step of charging must not be written
        states = {MODE: "NextTrip", "time.wb_trip": "07:00:00", "number.wb_energy": "12.0"}
        p, v = plugwhen(states), car(charge_kwh=12.0)
        run(p._direct_step(v, T0))
        v.need = Need(km=100, kwh=20, target_soc=60.0, charge_kwh=11.6, reachable=True, source="learned")
        v.soc = 50.5
        run(p._direct_step(v, T0 + timedelta(minutes=5)))
        self.assertNotIn("number.wb_energy", [e for e, _ in p.written])


class ByHandTests(unittest.TestCase):
    def test_respected_until_the_departure(self):
        # before: the change by hand held for one run only, the next one set Plugwhen's mode again
        states = {MODE: "Default"}
        p, v = plugwhen(states), car()
        run(p._own(v, MODE, "Eco", T0))
        run(p._own(v, MODE, "Eco", T0 + timedelta(minutes=5)))   # seen
        states[MODE] = "Default"                                  # the user wants to charge now
        for k in range(2, 8):
            self.assertIsNone(run(p._own(v, MODE, "Eco", T0 + timedelta(minutes=5 * k))))
        self.assertEqual(states[MODE], "Default")
        self.assertEqual(len([d for d in p.diag if "von Hand" in d]), 1)
        v.departure = DEP + timedelta(days=1)                     # the departure is past, the next one is planned
        self.assertEqual(run(p._own(v, MODE, "Eco", DEP + timedelta(minutes=1))), f"{MODE}=Eco")

    def test_leaving_direct_gives_nothing_back_after_a_change_by_hand(self):
        states = {MODE: "Default"}
        p, v = plugwhen(states), car()
        run(p._own(v, MODE, "Eco", T0))
        run(p._own(v, MODE, "Eco", T0 + timedelta(minutes=5)))
        states[MODE] = "Default"
        run(p._own(v, MODE, "Eco", T0 + timedelta(minutes=10)))
        v.mode = "learn"
        run(p._direct_step(v, T0 + timedelta(minutes=15)))
        self.assertEqual(states[MODE], "Default")
        self.assertNotIn(MODE, p._direct["sub"])


class SlowWallboxTests(unittest.TestCase):
    def test_waited_for_then_sent_again_not_taken_as_a_change_by_hand(self):
        states = {MODE: "Default"}
        p, v = plugwhen(states, follow=False), car()
        run(p._own(v, MODE, "Eco", T0))
        self.assertIsNone(run(p._own(v, MODE, "Eco", T0 + timedelta(seconds=30))))   # not visible yet: wait
        self.assertEqual(len(p.written), 1)
        self.assertEqual(run(p._own(v, MODE, "Eco", T0 + timedelta(seconds=co.OWN_GRACE_S + 5))), f"{MODE}=Eco")
        self.assertEqual(p._direct["sub"][MODE]["orig"], "Default")
        self.assertEqual([d for d in p.diag if "von Hand" in d], [])


class EvccLoadpointTests(unittest.TestCase):
    def test_given_back_after_charge_now_although_evcc_is_read_less_often(self):
        # before: the old mode read earlier looked like a change by the user, the record was dropped every second run and
        # evcc could stay on "now" for good
        p, v = plugwhen({}), car("evcc")
        v.cfg[co.V_EVCC_VEHICLE] = "car1"
        p.evcc_connection = lambda: ("http://evcc", None, "own")
        p.evcc_state = {"loadpoints": [{"vehicleName": "car1", "mode": "pv"}]}
        sent: list[tuple[int, str]] = []

        class Client:
            def __init__(self, *a, **k) -> None:
                pass

            async def set_loadpoint_mode(self, number, mode):
                sent.append((number, mode))

        import homeassistant.helpers.aiohttp_client as ac
        orig_client, orig_session = co.EvccClient, ac.async_create_clientsession
        co.EvccClient, ac.async_create_clientsession = Client, lambda hass, **kw: None   # Plugwhen's own session (HACS review)
        try:
            for _ in range(4):   # several runs before evcc is read again
                run(p._evcc_loadpoint_mode(v, "now"))
            self.assertEqual(sent, [(1, "now")])
            self.assertEqual(p._direct["sub"]["evcc_loadpoint"]["orig"], "pv")
            run(p._evcc_loadpoint_mode(v, None))
            self.assertEqual(sent, [(1, "now"), (1, "pv")])
        finally:
            co.EvccClient, ac.async_create_clientsession = orig_client, orig_session


if __name__ == "__main__":
    unittest.main(verbosity=2)
