"""Coordinator: never two runs of warnings/evcc/wallbox at once, readable error texts.

Runs in the Home Assistant image (imports homeassistant):
MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W):/w" -w /w --entrypoint python \
  ghcr.io/home-assistant/home-assistant:2026.11.1 tests/install/coord_lock_test.py
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from custom_components.plugwhen import coordinator as co  # noqa: E402


def bare() -> co.Plugwhen:
    p = co.Plugwhen.__new__(co.Plugwhen)
    p._acting, p._act_again = False, False
    return p


class RunLockTests(unittest.IsolatedAsyncioTestCase):
    async def test_a_second_run_waits_and_follows_once(self):
        p, calls, gate = bare(), [], asyncio.Event()

        async def slow(now):   # a wallbox over the cloud: the first command takes long
            calls.append(now)
            if len(calls) == 1:
                await gate.wait()

        p._act_once = slow
        now = datetime(2026, 11, 15, 18, 0, tzinfo=timezone.utc)
        first = asyncio.create_task(p._send_and_act(now))
        await asyncio.sleep(0)
        for _ in range(3):   # three triggers meanwhile (tick, sensor changes)
            await p._send_and_act(now)
        self.assertEqual(len(calls), 1, "no second run while the first is busy")
        gate.set()
        await first
        self.assertEqual(len(calls), 2, "the runs asked for meanwhile follow exactly once")
        self.assertFalse(p._acting)

    async def test_an_error_frees_the_lock(self):
        p = bare()

        async def boom(now):
            raise RuntimeError("x")

        p._act_once = boom
        with self.assertRaises(RuntimeError):
            await p._send_and_act(datetime.now(timezone.utc))
        self.assertFalse(p._acting)


class ErrTextTests(unittest.TestCase):
    def test_texts(self):
        self.assertEqual(co.err_text(TimeoutError()), "TimeoutError (no answer in time)")
        self.assertEqual(co.err_text(RuntimeError("")), "RuntimeError")
        self.assertEqual(co.err_text(ValueError(" bad ")), "bad")
        self.assertEqual(len(co.err_text(ValueError("x" * 500))), 120)


if __name__ == "__main__":
    unittest.main(verbosity=2)
