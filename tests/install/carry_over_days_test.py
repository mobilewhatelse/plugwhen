"""The day selection of earlier 0.9.2 builds is carried over to the day switches and removed from the registry. Needs Home
Assistant installed, so it runs in its Docker image:

docker run --rm -v "$PWD:/w" -w /w --entrypoint python ghcr.io/home-assistant/home-assistant:stable tests/install/carry_over_days_test.py
"""

from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.append(str(Path(__file__).resolve().parents[2]))

import custom_components.plugwhen as pw  # noqa: E402
from custom_components.plugwhen import coordinator as co  # noqa: E402


class FakeRegistry:
    def __init__(self, ids: dict[str, str]) -> None:
        self.ids, self.removed = ids, []

    def async_get_entity_id(self, domain, platform, unique_id):
        return self.ids.get(unique_id)

    def async_remove(self, eid):
        self.removed.append(eid)


def run(old_state: str | None, has_select: bool = True):
    v = co.Vehicle("sub1", "Auto", {})
    plug = types.SimpleNamespace(vehicles={"sub1": v})
    reg = FakeRegistry({"sub1_weekly_days": "select.auto_tage"} if has_select else {})
    states = {"select.auto_tage": types.SimpleNamespace(state=types.SimpleNamespace(state=old_state))} if old_state else {}
    with mock.patch("homeassistant.helpers.entity_registry.async_get", return_value=reg), \
            mock.patch("homeassistant.helpers.restore_state.async_get", return_value=types.SimpleNamespace(last_states=states)):
        pw._carry_over_weekly_days(object(), plug)
    return v, reg


class CarryOverTests(unittest.TestCase):
    def test_saturday_or_sunday_is_kept(self):
        v, reg = run("weekend")
        self.assertEqual(v.weekly_days_old, frozenset({5, 6}))
        self.assertEqual(reg.removed, ["select.auto_tage"])

    def test_friday_to_sunday(self):
        v, _ = run("friday_sunday")
        self.assertEqual(v.weekly_days_old, frozenset({4, 5, 6}))

    def test_no_stored_state_gives_the_default(self):
        v, reg = run(None)
        self.assertIsNone(v.weekly_days_old)   # the switches then take Saturday and Sunday
        self.assertEqual(reg.removed, ["select.auto_tage"])

    def test_installations_without_the_selection_are_untouched(self):
        v, reg = run(None, has_select=False)
        self.assertIsNone(v.weekly_days_old)
        self.assertEqual(reg.removed, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
