"""Large attributes stay out of the recorder: the latest messages of the notice switch are not written to the database with
every change of the switch.

switch.py imports Home Assistant, so the unit test reads the class from the source (ast) instead."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"


def unrecorded(module: str, cls: str) -> set[str] | None:
    """The names in `_unrecorded_attributes = frozenset({...})` of a class, None if the class does not set it."""
    for node in ast.parse((PKG / module).read_text(encoding="utf-8")).body:
        if isinstance(node, ast.ClassDef) and node.name == cls:
            for item in node.body:
                if isinstance(item, ast.Assign) and any(getattr(t, "id", "") == "_unrecorded_attributes" for t in item.targets):
                    call = item.value
                    assert isinstance(call, ast.Call) and getattr(call.func, "id", "") == "frozenset", ast.dump(call)
                    return set(ast.literal_eval(call.args[0]))
            return None
    raise AssertionError(f"{cls} not in {module}")


class UnrecordedTests(unittest.TestCase):
    def test_notice_switch_keeps_the_messages_out_of_the_database(self):
        self.assertEqual(unrecorded("switch.py", "NoticeSwitch"), {"recent"})

    def test_the_messages_are_still_an_attribute(self):
        """The dashboard reads them (state_attr ... 'recent'): only the recorder leaves them out."""
        self.assertIn('{"recent": self.plug.recent_messages(self.vehicle)}', (PKG / "switch.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
