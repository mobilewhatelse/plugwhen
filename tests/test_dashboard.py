"""Tests for the dashboard builder."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

from dashboard import ENTITY_KEYS, build_views  # noqa: E402


def ids(prefix):
    return {k: f"{d}.{prefix}_{k}" for k, d in ENTITY_KEYS.items()}


class DashboardTest(unittest.TestCase):
    def test_one_vehicle_all_entities_used(self):
        """Every entity except the ones left out on purpose (their numbers are in the status line or a chart)."""
        hidden = {"need_range", "target_soc", "week_plan"}
        views = build_views([{"name": "Car", "ids": ids("car")}], "en")
        text = json.dumps(views)
        for key, eid in ids("car").items():
            if key in hidden:
                self.assertNotIn(f'"entity": "{eid}"', text, key)
            else:
                self.assertIn(eid, text, key)
        self.assertEqual([v["path"] for v in views], ["plugwhen", "lernen", "details"])
        self.assertEqual(views[0]["type"], "sections")

    def test_day_bar_shows_which_days_are_ticked(self):
        """Field test 16.11.2026: the buttons without an icon looked the same on and off. Now tiles with a green check."""
        text = json.dumps(build_views([{"name": "Car", "ids": ids("car")}], "de"), ensure_ascii=False)
        views = json.loads(text)
        tiles = []

        def walk(x):
            if isinstance(x, dict):
                if str(x.get("entity", "")).startswith("switch.car_weekly_day_"):
                    tiles.append(x)
                for val in x.values():
                    walk(val)
            elif isinstance(x, list):
                for val in x:
                    walk(val)
        walk(views)
        self.assertEqual([t["name"] for t in tiles], ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"])
        for t in tiles:
            self.assertEqual((t["type"], t["color"], t["hide_state"]), ("tile", "green", True))
            self.assertEqual(t["tap_action"], {"action": "toggle"})

    def test_weekly_full_shows_only_the_switch_while_off(self):
        """Field test 16.11.2026: with the switch off the days stayed. Now target, days and status sit in one conditional card."""
        views = build_views([{"name": "Car", "ids": ids("car")}], "de")
        sw = ids("car")["weekly_full"]
        cards = [c for v in views for s in v.get("sections", []) for c in s.get("cards", [])]
        top = [c for c in cards if c["type"] == "entities" and any(e.get("entity") == sw for e in c["entities"])]
        self.assertEqual(len(top), 1)
        self.assertEqual(len(top[0]["entities"]), 1)                    # the switch alone
        cond = [c for c in cards if c["type"] == "conditional" and c["conditions"][0].get("entity") == sw]
        self.assertEqual(len(cond), 1)
        self.assertEqual(cond[0]["conditions"][0]["state"], "on")
        inner = json.dumps(cond[0])
        self.assertIn(ids("car")["weekly_target"], inner)
        for d in range(7):
            self.assertIn(ids("car")[f"weekly_day_{d}"], inner)
        self.assertIn("Volladen", inner)
        outside = json.dumps([c for c in cards if c is not cond[0]])
        self.assertNotIn(ids("car")["weekly_day_0"], outside)

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

    def test_learn_card_renders_strictly_when_learn_mode_is_off(self):
        """The frontend renders templates strictly: in the mode 'direct' the would-switch sensor is 'off' and has no
        reason/until/summary, the text card must still render, and the empty chart must not leave an empty card."""
        import jinja2

        i = ids("x")
        views = build_views([{"name": "X", "ids": i}], "de")
        cards = [c for s in views[1]["sections"] for g in s["cards"] for c in g.get("cards", [g])]
        md = [c for c in cards if c["type"] == "markdown" and "Probelauf aus. Fahrten und Verbrauch lernt Plugwhen trotzdem weiter." in c["content"]]
        self.assertEqual(len(md), 1)

        class Ent:
            attributes = {"friendly_name": "x"}

        class States:
            def __call__(self, eid):
                return "off"

            def __getattr__(self, domain):
                return type("D", (), {"__getattr__": lambda self, name: Ent()})()

        env = jinja2.Environment(undefined=jinja2.StrictUndefined)
        env.filters.update(as_datetime=lambda v: v, as_local=lambda v: v)
        self.assertEqual(env.from_string(md[0]["content"]).render(states=States()), "Probelauf aus. Fahrten und Verbrauch lernt Plugwhen trotzdem weiter.")
        chart = [c for c in cards if c["type"] == "conditional" and "chart" in c["card"].get("content", "")]
        self.assertEqual(len(chart), 1)
        self.assertEqual(chart[0]["conditions"][0], {"condition": "state", "entity": i["would_switch"], "state_not": "off"})

    def test_status_line_shows_the_next_trip_and_a_charge_ahead(self):
        """Strictly rendered: a car without the new attributes (an older state) must still render."""
        import jinja2

        i = ids("x")
        views = build_views([{"name": "X", "ids": i}], "de")
        cards = [c for v in views for s in v["sections"] for g in s["cards"] for c in g.get("cards", [g])]
        md = [c for c in cards if c["type"] == "markdown" and "**Ziel bei Abfahrt:**" in c["content"] and "angesteckt" in c["content"]]
        self.assertEqual(len(md), 1)

        def render(attrs: dict) -> str:
            ent = type("E", (), {"attributes": attrs})()

            class States:
                def __getattr__(self, domain):
                    return type("D", (), {"__getattr__": lambda self, name: ent})()

            env = jinja2.Environment(undefined=jinja2.StrictUndefined)
            return env.from_string(md[0]["content"]).render(states=States(), state_attr=lambda e, a: None)

        base = {"soc": 30, "plugged": True, "target_soc": 75.7, "range_km": 146.0, "reachable": True}
        old_state = render(base)
        self.assertIn("**Ziel bei Abfahrt:** 75.7 % (146.0 km)", old_state)
        self.assertNotIn("im Voraus", old_state)
        ahead = {"filling": True, "target_soc": 75.7, "days": 3, "sun_kwh": 0.0}
        filling = render({**base, "must_soc": 46.5, "ahead": ahead})
        self.assertIn("**Ziel bei Abfahrt:** 46.5 % (146.0 km) · **lädt im Voraus bis:** 75.7 % (3 Tage)", filling)
        self.assertNotIn("Sonne", filling)
        self.assertIn("der Sonne überlassen 6.3 kWh", render({**base, "must_soc": 46.5, "ahead": {**ahead, "sun_kwh": 6.3}}))
        self.assertNotIn("im Voraus", render({**base, "must_soc": 46.5, "ahead": {**ahead, "filling": False}}))

    def test_fleet_card_only_while_sharing_is_off(self):
        main = {"feedback_text": "text.fb", "feedback_send": "button.fb", "share_usage": "switch.share"}
        for lang, words in (("de", "Flottenwerte sind aus"), ("en", "Fleet values are off")):
            views = build_views([{"name": "X", "ids": ids("x")}], lang, main_ids=main)
            first = views[1]["sections"][0]["cards"][0]              # tab Learning, at the top
            self.assertEqual(first["type"], "conditional")
            self.assertEqual(first["conditions"], [{"condition": "state", "entity": "switch.share", "state": "off"}])
            self.assertIn(words, json.dumps(first, ensure_ascii=False))
            self.assertNotIn("Ladeverlust", json.dumps(first, ensure_ascii=False))   # the fleet values are consumption only
        views = build_views([{"name": "X", "ids": ids("x")}], "en")   # without the main device: no card
        self.assertNotIn("Fleet values", json.dumps(views))


if __name__ == "__main__":
    unittest.main()
