"""Coordinator: the warning that the car will not be ready, and the evening reminder to plug in (realtest of 16.11.2026).

A trip at 22:00 that cannot be reached with the battery was warned about at noon ("not reachable"). In the evening the car was
still not plugged in and nothing came any more: one warning per departure and kind. Now a car known not to be plugged in gets one
reminder from the evening hour on, once.

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
from custom_components.plugwhen.notice import check_ready  # noqa: E402

TZ = timezone(timedelta(hours=1))
DEP = datetime(2026, 11, 16, 22, 0, tzinfo=TZ)


def plugwhen() -> co.Plugwhen:
    p = co.Plugwhen.__new__(co.Plugwhen)
    p.hass = SimpleNamespace(config=SimpleNamespace(language="de"))
    p._sent = {}
    p._store = SimpleNamespace(async_delay_save=lambda *a, **k: None)
    p.out: list[tuple[str, str]] = []

    async def deliver(v, services, title, message, key):
        p.out.append((title, message))
        co.remember_sent(p._sent.setdefault(v.sub_id, []), key, co.SENT_KEEP)
        return True
    p._deliver = deliver
    return p


def car(plugged: bool | None, reachable: bool = False, charge: float = 52.0) -> co.Vehicle:
    v = co.Vehicle("sub", "Mercedes", {co.V_CAPACITY: 66, co.V_CHARGE_MAX: 11, co.V_NOTIFY: "notify.phone"})
    v.departure, v.plugged, v.soc = DEP, plugged, 29.0
    v.need = Need(km=300.0, kwh=76.0, target_soc=100.0, charge_kwh=charge, reachable=reachable, source="calendar")
    return v


def step(p: co.Plugwhen, v: co.Vehicle, now: datetime) -> None:
    v.notice = check_ready(v.need, v.soc, plugged=v.plugged, charging=False,
                           hours_to_departure=(DEP - now).total_seconds() / 3600.0, charge_kw_max=11.0)
    asyncio.run(p._send_ready(v, now))


class EveningReminderTests(unittest.TestCase):
    def test_warned_at_noon_reminded_in_the_evening_once(self):
        p, v = plugwhen(), car(plugged=False)
        step(p, v, DEP.replace(hour=12, minute=1))
        self.assertEqual(len(p.out), 1)
        self.assertEqual(p.out[0][0], "Mercedes: heute nicht bereit")
        self.assertIn("nicht erreichbar", p.out[0][1])
        self.assertIn("trotzdem anstecken", p.out[0][1])
        step(p, v, DEP.replace(hour=15))                     # afternoon: nothing new
        self.assertEqual(len(p.out), 1)
        step(p, v, DEP.replace(hour=19))                     # evening, still not plugged in: one reminder
        self.assertEqual(len(p.out), 2)
        self.assertIn("Erinnerung", p.out[1][1])
        step(p, v, DEP.replace(hour=19, minute=30))
        step(p, v, DEP.replace(hour=21))
        self.assertEqual(len(p.out), 2)                      # only once

    def test_plugged_in_by_the_evening_no_reminder(self):
        p, v = plugwhen(), car(plugged=False)
        step(p, v, DEP.replace(hour=12))
        v.plugged = True
        step(p, v, DEP.replace(hour=19))
        self.assertEqual(len(p.out), 1)

    def test_first_warning_in_the_evening_is_not_followed_by_a_reminder(self):
        p, v = plugwhen(), car(plugged=False, reachable=True, charge=20.0)   # fits in the 3 h left: only "plug in"
        step(p, v, DEP.replace(hour=19))
        step(p, v, DEP.replace(hour=20))
        self.assertEqual(len(p.out), 1)
        self.assertIn("Bitte anstecken", p.out[0][1])

    def test_plug_state_unknown_no_reminder(self):
        p, v = plugwhen(), car(plugged=None)
        step(p, v, DEP.replace(hour=12))
        step(p, v, DEP.replace(hour=19))
        self.assertEqual(len(p.out), 1)


if __name__ == "__main__":
    unittest.main()
