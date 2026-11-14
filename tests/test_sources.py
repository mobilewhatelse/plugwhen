"""Tests for 'where the data comes from'."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

from dashboard import ENTITY_KEYS, build_views  # noqa: E402
from sources import data_sources  # noqa: E402

CFG = {"soc_entity": "sensor.soc", "odometer_entity": "sensor.km", "evcc_vehicle": "db:3"}


class SourcesTest(unittest.TestCase):
    def test_sensors_win_evcc_fills_in(self):
        s = data_sources({**CFG, "plugged_entity": "binary_sensor.plug"}, True, {"source": "guard", "used": True, "ok": True})
        self.assertEqual(s["soc"], {"from": "sensor", "entity": "sensor.soc"})
        self.assertEqual(s["plugged"], {"from": "sensor", "entity": "binary_sensor.plug"})
        self.assertEqual(s["charging"], {"from": "evcc"})
        self.assertEqual(s["evcc"], {"address": "guard", "vehicle": "db:3", "ok": True, "error": None})
        self.assertEqual(s["departure"], {"from": "learned"})
        self.assertEqual(s["plan"], "recommendation")

    def test_without_evcc(self):
        s = data_sources(CFG, False, {})
        self.assertEqual(s["plugged"], {"from": None})
        self.assertIsNone(s["evcc"])
        self.assertEqual(s["taken_from"], [])

    def test_evcc_known_but_not_asked(self):
        self.assertIsNone(data_sources({}, False, {"source": "own", "used": False})["evcc"]["ok"])

    def test_plan_executed_later(self):
        self.assertEqual(data_sources(CFG, False, None, executed=True)["plan"], "executed")

    def test_origin_of_the_settings(self):
        self.assertEqual(data_sources({**CFG, "taken_from": ["guard", "evcc"]}, False, None)["taken_from"], ["guard", "evcc"])


class CardTest(unittest.TestCase):
    def test_card_in_both_languages(self):
        ids = {k: f"{d}.car_{k}" for k, d in ENTITY_KEYS.items()}
        for lang, title in (("de", "Woher die Daten kommen"), ("en", "Where the data comes from")):
            text = json.dumps(build_views([{"name": "Car", "ids": ids}], lang))
            self.assertIn(title, text)
            self.assertIn(".sources", text)


class CalendarCardTest(unittest.TestCase):
    def test_calendar_view_and_how_to_with_a_calendar(self):
        ids = {k: f"{d}.car_{k}" for k, d in ENTITY_KEYS.items()}
        text = json.dumps(build_views([{"name": "Car", "ids": ids, "calendar": "calendar.fahrten"}], "de"), ensure_ascii=False)
        self.assertIn('"type": "calendar"', text)
        self.assertIn("calendar.fahrten", text)
        self.assertIn("So tragen Sie eine Fahrt ein", text)

    def test_setup_hint_without_a_calendar(self):
        ids = {k: f"{d}.car_{k}" for k, d in ENTITY_KEYS.items()}
        text = json.dumps(build_views([{"name": "Car", "ids": ids}], "en"), ensure_ascii=False)
        self.assertNotIn('"type": "calendar"', text)
        self.assertIn("Local Calendar", text)


class TemplateSyntaxTest(unittest.TestCase):
    """Every markdown card must be a valid template in both languages (an apostrophe in a text once broke the English card)."""

    def test_all_cards_parse(self):
        try:
            import jinja2
        except ImportError:
            self.skipTest("jinja2 not installed")
        env = jinja2.Environment()
        ids = {k: f"{d}.car_{k}" for k, d in ENTITY_KEYS.items()}
        for lang in ("de", "en"):
            views = build_views([{"name": "Car", "ids": ids, "calendar": "calendar.trips", "evcc": True}], lang)
            for v in views:
                for sec in v["sections"]:
                    for card in sec["cards"]:
                        if card.get("type") == "markdown":
                            try:
                                env.parse(card["content"])
                            except jinja2.TemplateSyntaxError as err:
                                self.fail(f"{lang}: {err}: {card['content'][:120]}")


if __name__ == "__main__":
    unittest.main()
