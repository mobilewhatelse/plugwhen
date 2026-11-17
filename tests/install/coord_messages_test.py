"""Coordinator: the messages to the phone are kept for the dashboard ('Latest messages'), newest first, at most MESSAGES_KEEP,
and are stored with the sent keys (field 17.11.2026: a message swiped away on the phone could not be read again).

Runs in the Home Assistant image (imports homeassistant), found by tests/install/run_coordinator_tests.py.
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from datetime import datetime
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from custom_components.plugwhen import coordinator as co  # noqa: E402


def plugwhen(fail: bool = False) -> co.Plugwhen:
    p = co.Plugwhen.__new__(co.Plugwhen)
    p.calls = []

    async def call(domain, name, data, blocking=False):
        if fail:
            raise RuntimeError("no such service")
        p.calls.append((domain, name, data))
    p.hass = SimpleNamespace(config=SimpleNamespace(language="de"), services=SimpleNamespace(async_call=call))
    p._sent, p._messages, p.saved = {}, {}, []
    p._store = SimpleNamespace(async_delay_save=lambda f, d: p.saved.append(f()))
    return p


def car(sub: str = "sub") -> co.Vehicle:
    return co.Vehicle(sub, "Mercedes", {co.V_NOTIFY: "notify.phone"})


class MessagesTest(unittest.TestCase):
    def test_a_delivered_message_is_kept_newest_first_and_stored(self):
        p, v = plugwhen(), car()
        for i in range(3):
            self.assertTrue(asyncio.run(p._deliver(v, ["notify.phone"], "Plugwhen · Mercedes", f"Meldung {i}", f"k{i}")))
        recent = p.recent_messages(v)
        self.assertEqual([m["text"] for m in recent], ["Meldung 2", "Meldung 1", "Meldung 0"])
        for m in recent:                                                  # date and time to the minute, with the zone
            t = datetime.fromisoformat(m["t"])
            self.assertEqual(t.second, 0)
            self.assertIsNotNone(t.tzinfo)
        self.assertEqual(p.saved[-1]["messages"]["sub"][0]["text"], "Meldung 2")
        self.assertIn("k2", p.saved[-1]["sent"]["sub"])

    def test_at_most_the_latest_ones_per_car(self):
        p, v, w = plugwhen(), car(), car("other")
        for i in range(co.MESSAGES_KEEP + 5):
            asyncio.run(p._deliver(v, ["notify.phone"], "t", f"m{i}", f"k{i}"))
        asyncio.run(p._deliver(w, ["notify.phone"], "t", "anderes Auto", "x"))
        self.assertEqual(len(p.recent_messages(v)), co.MESSAGES_KEEP)
        self.assertEqual(p.recent_messages(v)[0]["text"], f"m{co.MESSAGES_KEEP + 4}")
        self.assertEqual([m["text"] for m in p.recent_messages(w)], ["anderes Auto"])

    def test_nothing_kept_when_nothing_was_delivered(self):
        p, v = plugwhen(fail=True), car()
        self.assertFalse(asyncio.run(p._deliver(v, ["notify.phone"], "t", "m", "k")))
        self.assertEqual(p.recent_messages(v), [])


if __name__ == "__main__":
    unittest.main()
