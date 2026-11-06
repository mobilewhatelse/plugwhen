"""Tests for the dashboard builder."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

from dashboard import ENTITY_KEYS, build_views  # noqa: E402


def ids(prefix):
    return {k: f"{d}.{prefix}_{k}" for k, d in ENTITY_KEYS.items()}


class DashboardTest(unittest.TestCase):
    def test_one_vehicle_all_entities_used(self):
        views = build_views([{"name": "Car", "ids": ids("car")}], "en")
        text = json.dumps(views)
        for eid in ids("car").values():
            self.assertIn(eid, text)
        self.assertEqual(len(views), 1)
        self.assertEqual(views[0]["type"], "sections")

    def test_two_vehicles_have_their_names_in_the_headings(self):
        views = build_views([{"name": "A", "ids": ids("a")}, {"name": "B", "ids": ids("b")}], "de")
        heads = [c["heading"] for s in views[0]["sections"] for c in s["cards"] if c["type"] == "heading"]
        self.assertTrue(any(h.startswith("A · ") for h in heads) and any(h.startswith("B · ") for h in heads))

    def test_language(self):
        de = json.dumps(build_views([{"name": "X", "ids": ids("x")}], "de"), ensure_ascii=False)
        en = json.dumps(build_views([{"name": "X", "ids": ids("x")}], "en-GB"), ensure_ascii=False)
        self.assertIn("Nächste Abfahrt", de)
        self.assertIn("Next departure", en)

    def test_only_standard_cards(self):
        views = build_views([{"name": "X", "ids": ids("x")}], "en")
        types = {c["type"] for s in views[0]["sections"] for c in s["cards"]}
        self.assertTrue(types <= {"heading", "tile", "markdown", "entities"}, types)

    def test_templates_are_balanced(self):
        for lang in ("de", "en"):
            views = build_views([{"name": "X", "ids": ids("x")}], lang)
            for s in views[0]["sections"]:
                for c in s["cards"]:
                    if c["type"] == "markdown":
                        t = c["content"]
                        self.assertEqual(t.count("{{"), t.count("}}"), t[:80])
                        self.assertEqual(t.count("{%"), t.count("%}"), t[:80])


if __name__ == "__main__":
    unittest.main()
