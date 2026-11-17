"""Coordinator: the safety check before a departure switches the wallbox to "charge now" and tells the user why.

Replays the night of 16.11.2026 (promised 100 %, Plugwhen's own target fell to 40 %, 28 % in the car at 04:00).
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

from custom_components.plugwhen import coordinator as co, sicherheit  # noqa: E402
from custom_components.plugwhen.need import Need  # noqa: E402

TZ = timezone(timedelta(hours=1))
MON_7 = datetime(2026, 11, 16, 7, 0, tzinfo=TZ)
AT_4 = MON_7 - timedelta(hours=3)

CAPS_TRIP = {"variant": "trip", "mode": "select.wb_mode", "mode_grid": "Default", "mode_sun": "Eco", "mode_trip": "NextTrip",
             "trip_time": "time.wb_trip", "trip_energy": "number.wb_energy"}


class FakeServices:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict]] = []

    async def async_call(self, domain, name, data, blocking=False):
        self.calls.append((domain, name, data))


def plugwhen(caps: dict, states: dict[str, str] | None = None) -> co.Plugwhen:
    p = co.Plugwhen.__new__(co.Plugwhen)
    services = FakeServices()
    p.hass = SimpleNamespace(config=SimpleNamespace(language="de"), services=services,
                             states=SimpleNamespace(get=lambda e: SimpleNamespace(state=(states or {}).get(e)) if e in (states or {}) else None))
    p._sent, p._direct, p._evcc_data, p._messages = {}, {}, {}, {}
    p._store = p._evcc_store = SimpleNamespace(async_delay_save=lambda *a, **k: None)
    p.diag: list[str] = []
    p._diag_action = lambda v, now, text: p.diag.append(text)
    p.efficiency_of = lambda v: 0.9
    p.wallbox_control = lambda v: caps
    p.evcc_connection = lambda: None
    p.evcc_state = None
    p.written: list[tuple[str, object]] = []

    async def set_entity(eid, value):
        p.written.append((eid, value))
    p._set_entity = set_entity
    return p


def car(mode: str, soc: float = 28.0, planned: float = 40.5, charging: bool = False) -> co.Vehicle:
    v = co.Vehicle("sub", "Auto", {co.V_CAPACITY: 66, co.V_CHARGE_MAX: 11, co.V_NOTIFY: "notify.handy"})
    v.mode, v.soc, v.plugged, v.charging, v.departure = mode, soc, True, charging, MON_7
    v.need = Need(km=100, kwh=20, target_soc=planned, charge_kwh=5.0, reachable=True, source="learned")
    v.promise = sicherheit.Promise(MON_7, 100.0)
    return v


def run(coro):
    return asyncio.run(coro)


def act(p, v, now) -> None:
    """One run as in _act_once: check, switch, tell."""
    run(p._safety_step(v, now))
    run(p._direct_step(v, now))
    run(p._safety_tell(v, now))


def phone(p) -> list[dict]:
    return [d for dom, _n, d in p.hass.services.calls if dom == "notify"]


def in_ha(p) -> list[dict]:
    return [d for dom, n, d in p.hass.services.calls if (dom, n) == ("persistent_notification", "create")]


class SafetyCoordinatorTests(unittest.TestCase):
    def test_the_night_of_16_11_charges_now_and_tells(self):
        p, v = plugwhen(CAPS_TRIP, {"select.wb_mode": "Eco"}), car("direct")
        run(p._safety_step(v, AT_4))
        self.assertEqual(v.safety["reason"], "target_fell")
        self.assertEqual(p.hass.services.calls, [])   # nothing is told before the wallbox was switched
        run(p._direct_step(v, AT_4))
        run(p._safety_tell(v, AT_4))
        self.assertTrue(v.safety["switched"])
        data, = phone(p)
        self.assertEqual(p.hass.services.calls[-1][:2], ("notify", "handy"))
        self.assertIn("lädt jetzt", data["title"])
        self.assertIn("„Jetzt laden“", data["message"])
        note, = in_ha(p)   # also in Home Assistant's notifications
        self.assertEqual(note["message"], data["message"])
        self.assertEqual(note["notification_id"], "plugwhen_safety_sub")
        run(p._direct_step(v, AT_4))
        self.assertIn(("select.wb_mode", "Default"), p.written)   # the wallbox's grid mode: charges at full power now
        self.assertNotIn("number.wb_energy", [e for e, _ in p.written])   # no new trip value that would pause the wallbox

    def test_one_message_per_departure_and_reason(self):
        p, v = plugwhen(CAPS_TRIP, {"select.wb_mode": "Eco"}), car("direct")
        act(p, v, AT_4)
        v.safety = None
        act(p, v, AT_4 + timedelta(minutes=5))
        self.assertEqual(len(phone(p)), 1)
        self.assertEqual(len(in_ha(p)), 1)

    def test_no_second_message_within_a_few_hours_whatever_the_reason(self):
        """Field test 16.11.: seven messages in 18 minutes (another reason each time while the user tried things)."""
        p, v = plugwhen(CAPS_TRIP, {"select.wb_mode": "Eco"}), car("direct")
        act(p, v, AT_4)                                                   # target_fell
        v.safety = None
        v.need = Need(km=100, kwh=20, target_soc=100.0, charge_kwh=5.0, reachable=True, source="learned")
        v.stall_since = AT_4 - timedelta(minutes=5)
        act(p, v, AT_4 + timedelta(minutes=6))                            # stalled
        v.safety, v.stall_since = None, None
        act(p, v, AT_4 + timedelta(minutes=12))                           # tight
        self.assertEqual(len(phone(p)), 1)
        self.assertEqual(len(in_ha(p)), 1)
        self.assertIsNotNone(v.safety)   # the wallbox is still switched to charging now
        v.safety = None
        v.promise = sicherheit.Promise(MON_7 + timedelta(minutes=sicherheit.QUIET.seconds // 60), 100.0)
        v.departure = v.promise.departure
        act(p, v, AT_4 + sicherheit.QUIET + timedelta(minutes=1))         # long enough ago: told again
        self.assertEqual(len(phone(p)), 2)

    def test_without_a_phone_service_only_in_home_assistant_and_once(self):
        p, v = plugwhen(CAPS_TRIP, {"select.wb_mode": "Eco"}), car("direct")
        v.cfg[co.V_NOTIFY] = ""
        act(p, v, AT_4)
        v.safety = None
        act(p, v, AT_4 + timedelta(minutes=5))
        self.assertEqual(phone(p), [])
        self.assertEqual(len(in_ha(p)), 1)
        self.assertIsNotNone(v.safety)   # charging now does not need a message service

    def test_ends_at_the_target(self):
        p, v = plugwhen(CAPS_TRIP, {"select.wb_mode": "Eco"}), car("direct")
        run(p._safety_step(v, AT_4))
        v.soc = 99.5
        run(p._safety_step(v, AT_4 + timedelta(hours=2)))
        self.assertIsNone(v.safety)

    def test_ends_when_unplugged(self):
        p, v = plugwhen(CAPS_TRIP, {"select.wb_mode": "Eco"}), car("direct")
        run(p._safety_step(v, AT_4))
        v.plugged = False
        v.promise = sicherheit.update_promise(v.promise, v.departure, 40.0, False, AT_4)
        run(p._safety_step(v, AT_4 + timedelta(minutes=10)))
        self.assertIsNone(v.safety)

    def test_a_wallbox_that_is_not_reachable_the_message_says_so(self):
        # review 16.11.: the message said "switched to charge now" before anything was switched
        p, v = plugwhen(CAPS_TRIP, {"select.wb_mode": "unavailable"}), car("direct")
        act(p, v, AT_4)
        self.assertEqual(p.written, [])
        self.assertFalse(v.safety["switched"])
        data, = phone(p)
        self.assertIn("bitte Laden starten", data["title"])
        self.assertIn("konnte die Wallbox nicht", data["message"])

    def test_charge_now_also_over_a_change_by_hand(self):
        # the car must be charged: the safety check overrides a mode the user set by hand
        p, v = plugwhen(CAPS_TRIP, {"select.wb_mode": "Eco"}), car("direct")
        p._direct["sub"] = {"select.wb_mode": {"user": True, "until": MON_7.isoformat()}}
        act(p, v, AT_4)
        self.assertIn(("select.wb_mode", "Default"), p.written)
        self.assertTrue(v.safety["switched"])

    def test_buttons_press_start(self):
        caps = {"variant": "buttons", "start": "button.wb_start", "stop": "button.wb_stop"}
        p, v = plugwhen(caps), car("direct")
        run(p._safety_step(v, AT_4))
        run(p._direct_step(v, AT_4))
        self.assertEqual(p.written, [("button.wb_start", None)])

    def test_without_control_nothing(self):
        # off / learn: Plugwhen does not touch the wallbox; the readiness warning tells the user (and respects its switch)
        for mode in ("off", "learn"):
            p, v = plugwhen(CAPS_TRIP, {"select.wb_mode": "Eco"}), car(mode, soc=50.0, planned=100.0)
            run(p._safety_step(v, MON_7 - timedelta(hours=2)))   # 37 kWh missing, 2 h at 11 kW: tight, not charging
            self.assertIsNone(v.safety)
            self.assertEqual(p.hass.services.calls, [])

    def test_direct_without_a_controllable_wallbox_nothing(self):
        p, v = plugwhen({}), car("direct")
        run(p._safety_step(v, AT_4))
        self.assertIsNone(v.safety)
        self.assertEqual(p.hass.services.calls, [])

    def test_all_fine_nothing_happens(self):
        p, v = plugwhen(CAPS_TRIP, {"select.wb_mode": "Eco"}), car("direct", soc=95.0, planned=100.0, charging=True)
        run(p._safety_step(v, AT_4))
        self.assertIsNone(v.safety)
        self.assertEqual(p.hass.services.calls, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
