"""Tests for the dashboard builder."""

from __future__ import annotations

import json
import sys
import unittest
from enum import Enum
from pathlib import Path
from types import SimpleNamespace

sys.path.append(str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

from dashboard import ENTITY_KEYS, build_views, is_installed  # noqa: E402


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

    def test_the_latest_messages_can_be_read_on_the_dashboard(self):
        """Field 17.11.2026: a message swiped away on the phone could not be read again. The overview lists the latest ones."""
        views = build_views([{"name": "Car", "ids": ids("car")}], "de")
        overview = views[0]["sections"]
        heads = [c.get("heading") for s in overview for c in s["cards"] if c["type"] == "heading"]
        self.assertIn("Letzte Hinweise", heads)
        md = [c["content"] for s in overview for c in s["cards"] if c["type"] == "markdown" and "'recent'" in c["content"]]
        self.assertEqual(len(md), 1)
        self.assertIn(f"state_attr('{ids('car')['notice_enabled']}', 'recent')", md[0])
        self.assertIn("weggeklickt", md[0])                     # what shows while there is none yet
        try:
            import jinja2
        except ImportError:
            return
        jinja2.Environment().parse(md[0])

    def test_would_switch_only_while_the_trial_run_is_on(self):
        """Field 17.11.2026: 'Würde schalten: aus' in the mode 'direct' only puzzled. The tile is shown while it is not 'off'."""
        views = build_views([{"name": "Car", "ids": ids("car")}], "de")
        cards = [c for v in views for s in v.get("sections", []) for c in s.get("cards", [])]
        ws = ids("car")["would_switch"]
        self.assertFalse([c for c in cards if c["type"] == "tile" and c.get("entity") == ws])
        cond = [c for c in cards if c["type"] == "conditional" and c["card"].get("entity") == ws]
        self.assertEqual(len(cond), 1)
        self.assertEqual(cond[0]["conditions"][0], {"condition": "state", "entity": ws, "state_not": "off"})

    def test_several_days_can_be_set_on_the_dashboard(self):
        """Field 17.11.2026: 'kann man das nicht aufs dashboard legen' - days at once and the limit in the settings card."""
        text = json.dumps(build_views([{"name": "Car", "ids": ids("car")}], "de"), ensure_ascii=False)
        for s in ('"entity": "number.car_days_ahead", "name": "Tage auf einmal laden"',
                  '"entity": "number.car_daily_cap", "name": "Grenze für mehrere Tage"'):
            self.assertIn(s, text)
        old = {k: v for k, v in ids("car").items() if k not in ("days_ahead", "daily_cap")}
        self.assertNotIn("days_ahead", json.dumps(build_views([{"name": "Car", "ids": old}], "de")))   # older ids: nothing breaks

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
        top = [c for c in cards if c["type"] == "tile" and c.get("entity") == sw]
        self.assertEqual(len(top), 1)                                   # the switch alone
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

    def test_settings_are_full_width_tiles_so_the_names_are_not_cut_off(self):
        """Field 17.11.2026 (phone): in an entities row the names were cut off ('Für so viele Tag…'). Now one tile per setting,
        full width, short names; numbers with +/- (days: a slider), switches toggle on a tap."""
        views = build_views([{"name": "Car", "ids": ids("car")}], "de")
        cards = [c for v in views for s in v.get("sections", []) for c in s.get("cards", [])]
        keys = ("reserve_km", "learn_km", "notice_enabled", "days_ahead", "daily_cap", "weekly_full")
        for k in keys:
            eid = ids("car")[k]
            tile = [c for c in cards if c["type"] == "tile" and c.get("entity") == eid]
            self.assertEqual(len(tile), 1, k)
            self.assertEqual(tile[0]["grid_options"], {"columns": "full"}, k)
            self.assertLessEqual(len(tile[0]["name"]), 32, tile[0]["name"])
            if eid.startswith("number."):
                self.assertEqual(tile[0]["features"][0]["type"], "numeric-input")
            else:
                self.assertEqual(tile[0]["tap_action"], {"action": "toggle"})
        days = [c for c in cards if c.get("entity") == ids("car")["days_ahead"]][0]
        self.assertEqual(days["features"][0]["style"], "slider")
        self.assertFalse(any(c["type"] == "entities" and any(e.get("entity") in [ids("car")[k] for k in keys] for e in c["entities"])
                             for c in cards))

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
            state = "off"

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
            ent = type("E", (), {"attributes": attrs, "state": "charge"})()

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

    def test_waechter_card_only_while_the_peak_guard_is_missing(self):
        car = [{"name": "X", "ids": ids("x")}]
        for lang, head, after in (("de", "Passt dazu: Viertelstunden-Wächter", "Dashboard neu erstellen"),
                                  ("en", "Goes well with: Viertelstunden-Wächter", "create the dashboard again")):
            views = build_views(car, lang, waechter=False)
            last = views[0]["sections"][-1]                             # tab Overview, at the end
            text = json.dumps(last, ensure_ascii=False)
            self.assertEqual(last["cards"][0], {"type": "heading", "heading": head, "icon": "mdi:shield-check-outline"})
            self.assertIn("repository=viertelstunden-waechter", text)    # straight into the marketplace
            self.assertIn("aiwhatelse.eu/spitzenwaechter", text)
            self.assertIn(after, text)
            for v in views[1:]:
                self.assertNotIn("Viertelstunden-Wächter", json.dumps(v, ensure_ascii=False))   # only once, in the overview
        for state in (True, None):                                       # installed, or not known: no card
            self.assertNotIn("Passt dazu", json.dumps(build_views(car, "de", waechter=state), ensure_ascii=False))


class InstalledTests(unittest.TestCase):
    """'Goes well with': the peak guard counts as installed only with a loaded config entry. A disabled entry or one that failed
    to set up does nothing, so the card stays."""

    class State(Enum):   # like homeassistant.config_entries.ConfigEntryState
        LOADED = "loaded"
        NOT_LOADED = "not_loaded"
        SETUP_ERROR = "setup_error"
        SETUP_RETRY = "setup_retry"

    def entries(self, *states):
        return [SimpleNamespace(state=s) for s in states]

    def test_only_a_loaded_entry_counts(self):
        S = self.State
        self.assertFalse(is_installed([]))
        self.assertFalse(is_installed(None))
        self.assertFalse(is_installed(self.entries(S.NOT_LOADED)))          # disabled
        self.assertFalse(is_installed(self.entries(S.SETUP_ERROR, S.SETUP_RETRY)))
        self.assertTrue(is_installed(self.entries(S.NOT_LOADED, S.LOADED)))
        self.assertTrue(is_installed(self.entries("loaded")))
        self.assertFalse(is_installed([SimpleNamespace()]))                   # no state at all

    def test_the_dashboard_service_uses_it(self):
        src = (Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen" / "__init__.py").read_text(encoding="utf-8")
        self.assertIn('waechter=is_installed(hass.config_entries.async_entries("viertelstunden_waechter"))', src)
        self.assertNotIn('bool(hass.config_entries.async_entries("viertelstunden_waechter"))', src)



class PlanProposalTests(unittest.TestCase):
    """A wallbox with a "next trip" mode decides itself when to charge: the plan card says the windows are a proposal."""

    def test_the_note_is_in_the_shipped_dashboard_in_both_languages(self):
        for lang, word in (("de", "Vorschlag"), ("en", "proposal")):
            text = json.dumps(build_views([{"name": "Car", "ids": ids("car")}], lang), ensure_ascii=False)
            self.assertIn(word, text)
            self.assertIn("'wallbox_decides'", text)   # only shown for such a wallbox (attribute of the plan sensor)


class WeekPreviewTests(unittest.TestCase):
    """The card 'Week preview' next to the look-ahead chart: one table row per departure from horizon.days, rendered strictly."""

    HORIZON = {"status": "ok", "days": [
        {"departure": "2026-11-23T07:30:00+01:00", "window_start": "2026-11-22T17:00:00+01:00", "need_kwh": 0.0,
         "latest_start": None, "latest_start_pref": None, "sun_direct_kwh": 0.0, "precharge_kwh": 0.0, "grid_kwh": 0.0},
        {"departure": "2026-11-24T07:30:00+01:00", "window_start": "2026-11-23T17:30:00+01:00", "need_kwh": 8.4,
         "latest_start": "2026-11-24T06:43:00+01:00", "latest_start_pref": "2026-11-24T05:10:00+01:00",
         "sun_direct_kwh": 0.0, "precharge_kwh": 2.0, "grid_kwh": 6.4},
        {"departure": "2026-11-25T07:30:00+01:00", "window_start": "2026-11-24T16:00:00+01:00", "need_kwh": 3.1,
         "latest_start": "2026-11-25T07:13:00+01:00", "latest_start_pref": None, "sun_direct_kwh": 3.1, "precharge_kwh": 0.0, "grid_kwh": 0.0},
    ], "precharge": [{"window_start": "2026-11-22T17:00:00+01:00", "sun_from": "2026-11-23T10:00:00+01:00",
                      "sun_to": "2026-11-23T13:00:00+01:00", "kwh": 2.0, "for_departure": "2026-11-24T07:30:00+01:00"}]}

    @staticmethod
    def _card(lang: str) -> str:
        views = build_views([{"name": "Car", "ids": ids("car")}], lang)
        md = [c["content"] for s in views[0]["sections"] for c in s["cards"] if c["type"] == "markdown" and "'horizon'" in c["content"]]
        return md

    @staticmethod
    def _render(content: str, attrs: dict, state: str = "charge") -> str:
        import jinja2
        from datetime import datetime

        ent = type("E", (), {"attributes": attrs, "state": state})()

        class States:
            def __call__(self, eid):
                return state

            def __getattr__(self, domain):
                return type("D", (), {"__getattr__": lambda self, name: ent})()

        env = jinja2.Environment(undefined=jinja2.StrictUndefined)
        env.filters.update(as_datetime=datetime.fromisoformat, as_local=lambda v: v)
        return env.from_string(content).render(states=States(), state_attr=lambda e, a: None)

    def test_the_table_sits_next_to_the_look_ahead_chart(self):
        views = build_views([{"name": "Car", "ids": ids("car")}], "de")
        section = [s for s in views[0]["sections"] if s["cards"][0].get("heading") == "Die nächsten Abfahrten"][0]
        contents = [c.get("content", "") for c in section["cards"]]
        chart = [i for i, c in enumerate(contents) if "horizon_chart" in c][0]
        self.assertIn("**Wochenvorschau**", contents[chart + 1])
        self.assertEqual(len(self._card("de")), 1)

    def test_german_table(self):
        text = self._render(self._card("de")[0], {"horizon": self.HORIZON, "pref_kw": 3.7})
        self.assertIn("| Tag | Abfahrt | Bedarf kWh | Anstecken ab | Spätestens laden ab | Sonne/Netz |", text)
        self.assertIn("| Mo 23.11. | 07:30 | 0 | So 17:00 | – nicht nötig | Mit Sonne vorladen 2.0 kWh für Di 07:30 |", text)
        self.assertIn("| Di 24.11. | 07:30 | 8.4 | Mo 17:30 | Di 05:10 | Sonne 0 · Netz 6.4 · vorgeladen 2.0 |", text)
        self.assertIn("| Mi 25.11. | 07:30 | 3.1 | Di 16:00 | Mi 07:13 | Sonne 3.1 · Netz 0 |", text)   # no preferred power: full power
        self.assertIn("_Anstecken ab: ab dann ist das Auto zu Hause.", text)

    def test_english_table(self):
        text = self._render(self._card("en")[0], {"horizon": self.HORIZON})
        self.assertIn("**Week preview**", text)
        self.assertIn("| Day | Departure | Need kWh | Plug in from | Start charging by | Sun/grid |", text)
        self.assertIn("| Mon 23.11. | 07:30 | 0 | Sun 17:00 | – not needed | Charge ahead with the sun 2.0 kWh for Tue 07:30 |", text)
        self.assertIn("| Tue 24.11. | 07:30 | 8.4 | Mon 17:30 | Tue 05:10 | sun 0 · grid 6.4 · charged ahead 2.0 |", text)

    def test_without_a_look_ahead_a_short_note(self):
        for lang, none, no_need in (("de", "Noch keine Vorschau", "kein Laden nötig"), ("en", "No preview yet", "No charging is needed")):
            card = self._card(lang)[0]
            for attrs in ({}, {"horizon": None}, {"horizon": {"status": "unknown_soc", "days": []}}, {"horizon": {"status": "ok"}}):
                text = self._render(card, attrs)
                self.assertIn(none, text, attrs)
                self.assertNotIn("|", text)
            self.assertIn(no_need, self._render(card, {"horizon": {"status": "no_need", "days": self.HORIZON["days"][:1]}}))
            self.assertEqual(self._render(card, {}, "unavailable"), "")   # right after a restart: nothing at all
        old = {"status": "ok", "days": [{"departure": "2026-11-23T07:30:00+01:00"}]}   # an older look-ahead without the new fields
        self.assertIn("| Mo 23.11. | 07:30 | 0 | – | – nicht nötig | – |", self._render(self._card("de")[0], {"horizon": old}))


class MissingSensorTests(unittest.TestCase):
    """18.11.2026: right after a restart the dashboard drew before the sensors were back - 'None' has no attribute 'attributes'
    in the log. Every attribute access must be safe while the entity does not exist."""

    def test_no_bare_attribute_access(self):
        import re

        ids = {k: f"{d}.car_{k}" for k, d in ENTITY_KEYS.items()}
        text = json.dumps(build_views([{"name": "Car", "ids": ids}], "de"))
        bare = [m.group(0) for m in re.finditer(r"states\.([a-z_]+\.[a-z0-9_]+)\.attributes(?! if states\.\1 else)", text)]
        self.assertEqual(bare, [])


    def test_cards_wait_for_their_sensors(self):
        text = json.dumps(build_views([{"name": "Car", "ids": {k: f"{d}.car_{k}" for k, d in ENTITY_KEYS.items()}}], "de"))
        self.assertIn("{% if states.sensor.car_charge_plan", text)

    @staticmethod
    def _cards():
        out = []

        def walk(x):
            if isinstance(x, dict):
                if x.get("type") == "markdown":
                    out.append(x["content"])
                for v in x.values():
                    walk(v)
            elif isinstance(x, list):
                for v in x:
                    walk(v)
        walk(build_views([{"name": "Car", "ids": {k: f"{d}.car_{k}" for k, d in ENTITY_KEYS.items()}}], "de"))
        return out

    @staticmethod
    def _render(content: str, state: str, attrs: dict) -> str:
        """Strictly, like the frontend: every entity has `state` and `attrs`."""
        import jinja2

        ent = type("E", (), {"attributes": attrs, "state": state})()

        class States:
            def __call__(self, eid):
                return state

            def __getattr__(self, domain):
                return type("D", (), {"__getattr__": lambda self, name: ent})()

        env = jinja2.Environment(undefined=jinja2.StrictUndefined)
        env.filters.update(as_datetime=lambda v: v, as_local=lambda v: v)
        return env.from_string(content).render(states=States(), state_attr=lambda e, a: None)

    def test_learning_cards_render_while_the_sensors_are_unavailable(self):
        """Right after a restart a sensor is 'unavailable': the entity exists, its own attributes do not. The learning check
        (coverage, gain points, days, departure), the charging habit, the calibration line and the would-switch line render
        strictly without an UndefinedError; numbers only appear once the attributes are there."""
        cards = self._cards()
        picks = {name: [c for c in cards if word in c] for name, word in (
            ("learning_check", "**Kilometer:**"), ("habit", "Ladegewohnheit"), ("calibration", "Ladeverluste"),
            ("would_switch", "Probelauf aus"))}
        for name, found in picks.items():
            self.assertEqual(len(found), 1, name)
        restored = {"restored": True, "friendly_name": "Car"}   # what Home Assistant keeps of an entity that is not back yet
        # 'unavailable' is held back by the gate of _wait_for_sensors; 'unknown' with attributes missing reaches the template itself
        for state in ("unavailable", "unknown"):
            for attrs in (restored, {}):
                for name, (content,) in picks.items():
                    try:
                        text = self._render(content, state, attrs)
                    except Exception as e:  # noqa: BLE001 - jinja2.UndefinedError and anything else the template raises
                        self.fail(f"{name} ({state}): {type(e).__name__}: {e}")
                    if name in ("learning_check", "calibration") or state == "unavailable":
                        self.assertEqual(text, "", f"{name} ({state})")
                if state == "unknown":
                    self.assertEqual(self._render(picks["habit"][0], state, attrs),
                                     "Noch zu wenig Daten für die Ladegewohnheit (28 Tage nötig).")

    def test_every_card_waits_while_its_sensors_are_unavailable(self):
        """Review 20.11.2026: the status line (soc), readiness (checks), trips (trip_calendar), look-ahead (horizon) and sources
        read attributes without a guard. Every card that reads attributes renders nothing while a sensor is 'unavailable'."""
        gated = [c for c in self._cards() if c.startswith("{% if states.")]
        for word in ("at.soc", "a.checks", "a.trip_calendar", "a.horizon", ".sources"):   # the five are all behind the gate
            self.assertTrue([c for c in gated if word in c], word)
        self.assertGreaterEqual(len(gated), 9)
        for attrs in ({}, {"restored": True, "friendly_name": "Car"}):
            for content in gated:
                try:
                    self.assertEqual(self._render(content, "unavailable", attrs), "", content[:100])
                except Exception as e:  # noqa: BLE001 - jinja2.UndefinedError and anything else the template raises
                    self.fail(f"{type(e).__name__}: {e} | {content[:100]}")

    def test_an_available_sensor_shows_the_card_as_before(self):
        cards = self._cards()
        for word, state, attrs in (
                ("**Kilometer:**", "reserve_enough", {"days": 40, "coverage_reserve_pct": 80, "coverage_learned_pct": 82,
                                                      "gain_points": 2, "ready_early_pct": 90, "ready_median_pct": 70}),
                ("**Ziel bei Abfahrt:**", "charge", {"soc": 30, "plugged": True, "target_soc": 75.7, "range_km": 146.0,
                                                     "reachable": True})):
            content = [c for c in cards if word in c][0]
            inner = content[content.index("%}") + 2:-len("{% endif %}")]   # the card without the gate
            text = self._render(content, state, attrs)
            self.assertIn(word, text)
            self.assertEqual(text, self._render(inner, state, attrs))

    def test_learning_check_still_shows_its_numbers(self):
        lc = [c for c in self._cards() if "**Kilometer:**" in c][0]
        full = {"days": 40, "coverage_reserve_pct": 80, "coverage_learned_pct": 82, "gain_points": 2,
                "ready_early_pct": 90, "ready_median_pct": 70}
        same = self._render(lc, "reserve_enough", full)
        self.assertIn("(80 → 82 %)", same)
        self.assertIn("an 90 Prozent der Tage rechtzeitig fertig gewesen, bis zur üblichen nur an 70 %.", same)
        self.assertIn("wären 12 Prozentpunkte", self._render(lc, "learning_helps", {**full, "gain_points": 12}))
        self.assertIn("Zur Abfahrt gibt es noch keine Aussage.",
                      self._render(lc, "little", {**full, "ready_early_pct": None, "ready_median_pct": None}))
        self.assertIn("geprüft wurden 5 Tage, nötig sind 21.", self._render(lc, "too_little_data", {"days": 5}))


if __name__ == "__main__":
    unittest.main()
