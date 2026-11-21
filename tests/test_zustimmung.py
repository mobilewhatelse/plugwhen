"""Tests for the consent with the list of what is sent (catalogue version 1): the link in both dialogs, the texts in de/en/strings,
the version kept on yes (set-up, question, switch, note under Repairs) and the one quiet note for those who shared before 0.10.1.

Home Assistant is not installed for the unit tests: its modules are replaced by small stand-ins while these tests run."""

from __future__ import annotations

import asyncio
import importlib
import importlib.abc
import importlib.machinery
import json
import re
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"
PKG = "plugwhen_zustimmung_test"
STUBBED = ("homeassistant", "voluptuous", "aiohttp")


class Stub:
    """Anything from Home Assistant: attributes are stubs again; a call with one function returns it (a decorator)."""

    def __init__(self, *a, **k):
        pass

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return Stub()

    def __call__(self, *a, **k):
        if len(a) == 1 and not k and callable(a[0]) and not isinstance(a[0], Stub):
            return a[0]
        return Stub()

    def __getitem__(self, key):
        return Stub()


class StubMeta(type):
    def __getattr__(cls, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return Stub()


class StubModule(types.ModuleType):
    """Names in capitals are classes (an entity can be based on them), the others stubs."""

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        if name[:1].isupper():
            cls = StubMeta(name, (Stub,), {})
            setattr(self, name, cls)
            return cls
        return Stub()


class Finder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, fullname, path, target=None):
        if fullname.split(".")[0] in STUBBED:
            return importlib.machinery.ModuleSpec(fullname, self, is_package=True)
        return None

    def create_module(self, spec):
        m = StubModule(spec.name)
        m.__path__ = []
        return m

    def exec_module(self, module):
        pass


class Issues:
    """Stand-in for homeassistant.helpers.issue_registry: which notes are open."""

    def __init__(self):
        self.open: set[str] = set()
        self.created: list[str] = []
        self.IssueSeverity = Stub()

    def async_create_issue(self, hass, domain, issue_id, **k):
        self.open.add(issue_id)
        self.created.append(issue_id)

    def async_delete_issue(self, hass, domain, issue_id):
        self.open.discard(issue_id)


class FlowBase:
    """Stand-in for RepairsFlow / ConfigFlow: records what would be shown."""

    def __init_subclass__(cls, **k):   # ConfigFlow takes domain=...
        super().__init_subclass__()

    def async_show_form(self, **k):
        return {"type": "form", **k}

    def async_create_entry(self, **k):
        return {"type": "create_entry", **k}


FINDER = Finder()
ISSUES = Issues()
mods: dict = {}
saved: dict = {}


def setUpModule():
    sys.meta_path.insert(0, FINDER)
    for name in list(sys.modules):
        if name.split(".")[0] in STUBBED:
            saved[name] = sys.modules.pop(name)
    importlib.import_module("homeassistant.helpers")
    sys.modules["homeassistant.helpers.issue_registry"] = ISSUES
    sys.modules["homeassistant.helpers"].issue_registry = ISSUES
    importlib.import_module("homeassistant.components.repairs").RepairsFlow = FlowBase
    ce = importlib.import_module("homeassistant.config_entries")
    for n in ("ConfigFlow", "OptionsFlow", "ConfigSubentryFlow"):
        setattr(ce, n, FlowBase)
    pkg = types.ModuleType(PKG)
    pkg.__path__ = [str(ROOT)]
    pkg.PlugwhenEntry = Stub()   # from the real __init__.py, which is not loaded here
    sys.modules[PKG] = pkg
    for name in ("rueckmeldung", "repairs", "config_flow", "coordinator"):
        mods[name] = importlib.import_module(f"{PKG}.{name}")


def tearDownModule():
    sys.meta_path.remove(FINDER)
    for name in list(sys.modules):
        if name.split(".")[0] in STUBBED or name == PKG or name.startswith(PKG + "."):
            sys.modules.pop(name, None)
    sys.modules.update(saved)


def fake_hass(lang="de", entries=()):
    return types.SimpleNamespace(config=types.SimpleNamespace(language=lang),
                                 config_entries=types.SimpleNamespace(async_entries=lambda domain: list(entries)))


class Store:
    def __init__(self):
        self.saves = 0

    def async_delay_save(self, data, delay=0):
        self.saves += 1


def plug(options=None, usage=None, share=False):
    """A Plugwhen coordinator without set-up: only what the consent needs."""
    p = mods["coordinator"].Plugwhen.__new__(mods["coordinator"].Plugwhen)
    p.hass = fake_hass()
    p.entry = types.SimpleNamespace(options=dict(options or {}))
    p._usage = dict(usage or {})
    p.share_usage = share
    p._katalog_asked = False
    p._evcc_store = Store()
    p._evcc_data = lambda: {}
    p.signal = "test"
    return p


def run(coro):
    return asyncio.run(coro)


class PrivacyUrlTest(unittest.TestCase):
    def test_language_of_home_assistant_with_english_fallback(self):
        rm = mods["rueckmeldung"]
        self.assertEqual(rm.privacy_url("de"), "https://www.aiwhatelse.eu/datenschutz/?lang=de#daten-teilen")
        self.assertEqual(rm.privacy_url("de-AT"), "https://www.aiwhatelse.eu/datenschutz/?lang=de#daten-teilen")
        self.assertEqual(rm.privacy_url("en"), "https://www.aiwhatelse.eu/datenschutz/?lang=en#daten-teilen")
        for lang in ("fr", "", None, "nl-BE"):
            self.assertEqual(rm.privacy_url(lang), "https://www.aiwhatelse.eu/datenschutz/?lang=en#daten-teilen")


class DialogsTest(unittest.TestCase):
    def test_finish_step_passes_the_link_and_keeps_the_version_on_yes(self):
        cf = mods["config_flow"]
        flow = cf.PlugwhenConfigFlow()
        flow.hass = fake_hass("de")
        shown = run(flow.async_step_finish(None))
        self.assertEqual(shown["step_id"], "finish")
        self.assertEqual(shown["description_placeholders"]["privacy_url"], mods["rueckmeldung"].privacy_url("de"))
        done = run(flow.async_step_finish({"share_usage": True}))
        self.assertEqual(done["options"]["katalog"], 1)
        self.assertTrue(done["options"]["share_usage"])

    def test_finish_step_without_yes_keeps_no_version(self):
        flow = mods["config_flow"].PlugwhenConfigFlow()
        flow.hass = fake_hass("en")
        self.assertIn("lang=en", run(flow.async_step_finish(None))["description_placeholders"]["privacy_url"])
        done = run(flow.async_step_finish({"share_usage": False}))
        self.assertNotIn("katalog", done["options"])

    def test_settings_dialog_keeps_the_consent_from_the_set_up(self):
        cf = mods["config_flow"]
        old = {"share_usage": True, "katalog": 1, cf.O_LOAD: "sensor.old"}
        new = cf.options_to_save(old, {cf.O_LOAD: "sensor.new", cf.O_AVAIL: ""})
        self.assertEqual(new, {"share_usage": True, "katalog": 1, cf.O_LOAD: "sensor.new"})
        self.assertEqual(cf.options_to_save({}, {cf.O_LOAD: "sensor.x"}), {cf.O_LOAD: "sensor.x"})   # nothing invented

    def test_both_repairs_pass_the_link(self):
        rp = mods["repairs"]
        for issue_id, cls in (("share_usage_question", rp.ShareUsageFlow), ("share_usage_check", rp.ShareCheckFlow)):
            flow = run(rp.async_create_fix_flow(None, issue_id, None))
            self.assertIsInstance(flow, cls)
            flow.hass = fake_hass("en")
            shown = run(flow.async_step_init())
            self.assertEqual(shown["step_id"], "confirm")
            self.assertEqual(shown["description_placeholders"]["privacy_url"], mods["rueckmeldung"].privacy_url("en"))

    def test_repairs_answer_reaches_every_plugwhen(self):
        rp = mods["repairs"]
        p = plug(share=True)
        entry = types.SimpleNamespace(runtime_data=p)
        flow = rp.ShareCheckFlow()
        flow.hass = fake_hass("de", [entry])
        self.assertEqual(run(flow.async_step_confirm({"share_usage": True}))["type"], "create_entry")
        self.assertEqual(p._usage["katalog"], 1)
        self.assertTrue(p.share_usage)


class TranslationsTest(unittest.TestCase):
    FILES = {"de": ROOT / "translations" / "de.json", "en": ROOT / "translations" / "en.json", "strings": ROOT / "strings.json"}

    @classmethod
    def setUpClass(cls):
        cls.t = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in cls.FILES.items()}

    def texts(self, t):
        issues = t["issues"]
        return {"finish": t["config"]["step"]["finish"]["description"],
                "question": issues["share_usage_question"]["fix_flow"]["step"]["confirm"]["description"],
                "check": issues["share_usage_check"]["fix_flow"]["step"]["confirm"]["description"]}

    def test_every_consent_text_links_the_list(self):
        for name, t in self.t.items():
            link = "[Was wann gesendet wird und warum]({privacy_url})" if name == "de" else "[What is sent when, and why]({privacy_url})"
            for key, text in self.texts(t).items():
                with self.subTest(file=name, text=key):
                    self.assertIn(link, text)
                    self.assertNotIn("aiwhatelse.eu/datenschutz", text)   # the address comes only from the code

    def test_short_text_keeps_what_matters(self):
        de, en = self.texts(self.t["de"]), self.texts(self.t["en"])
        for text in de.values():
            self.assertIn("Tageswerte ohne Kennung lassen sich nicht löschen", text)   # decision 11
            self.assertIn("Orte genauer als das Land", text)
            self.assertIn("Verantwortlich: Betreiber von aiwhatelse.eu", text)
        for text in en.values():
            self.assertIn("daily values without an id cannot be deleted", text)
            self.assertIn("places more precise than the country", text)
        # the note for earlier participants is short: one first paragraph that says what the switch does, then the consent text
        # without its first sentence (what the data help with)
        self.assertEqual(de["check"].split("\n\n")[0], "Sie teilen schon anonyme Daten, danke. Bitte einmal bestätigen: Es wird nichts "
                         "Neues gesendet, neu ist nur die Liste, was wann gesendet wird und warum. Schalter an und bestätigen: weiter "
                         "teilen. Schalter aus und bestätigen: Das Teilen wird ausgeschaltet.")
        self.assertEqual(en["check"].split("\n\n")[0], "You already share anonymous data, thank you. Please confirm once: nothing new is "
                         "sent, only the list of what is sent when and why is new. Switch on and confirm: keep sharing. Switch off and "
                         "confirm: sharing is switched off.")
        self.assertEqual(de["finish"], de["question"])
        for t in (de, en):
            head, rest = t["finish"].split("\n\n", 1)
            self.assertEqual(t["check"], t["check"].split("\n\n")[0] + "\n\n" + rest)
            self.assertNotIn(head, t["check"])

    def test_strings_equal_english_and_placeholders_equal_everywhere(self):
        self.assertEqual(self.t["strings"], self.t["en"])

        def flat(d, path=""):
            if isinstance(d, dict):
                for k, v in d.items():
                    yield from flat(v, f"{path}.{k}")
            elif isinstance(d, str):
                yield path, d

        de, en = dict(flat(self.t["de"])), dict(flat(self.t["en"]))
        self.assertEqual(set(de), set(en))
        for path in de:
            with self.subTest(key=path):
                self.assertEqual(set(re.findall(r"\{(\w+)\}", de[path])), set(re.findall(r"\{(\w+)\}", en[path])))


class KatalogTest(unittest.TestCase):
    def test_missing_or_odd_values_count_as_none(self):
        rm = mods["rueckmeldung"]
        self.assertEqual(rm.katalog_fassung({}, None), 0)
        self.assertEqual(rm.katalog_fassung({"katalog": "x"}, {"katalog": None}), 0)
        self.assertEqual(rm.katalog_fassung({"katalog": 1}, {}), 1)
        self.assertFalse(rm.katalog_fehlt(False, {}))
        self.assertTrue(rm.katalog_fehlt(True, {}, {}))
        self.assertFalse(rm.katalog_fehlt(True, {}, {"katalog": 1}))

    def test_earlier_participant_gets_one_quiet_note(self):
        ISSUES.open.clear()
        ISSUES.created.clear()
        p = plug(options={"share_usage": True}, share=True)   # set up before 0.10.1: no version kept
        self.assertFalse(p.katalog_ok())
        p._ask_katalog()
        p._ask_katalog()   # every tick: not created again
        self.assertEqual(ISSUES.created, ["share_usage_check"])
        self.assertIn("share_usage_check", ISSUES.open)

    def test_no_note_while_not_sharing_or_already_agreed(self):
        ISSUES.open.clear()
        ISSUES.created.clear()
        plug(share=False)._ask_katalog()
        plug(options={"katalog": 1}, share=True)._ask_katalog()
        plug(usage={"katalog": 1}, share=True)._ask_katalog()
        self.assertEqual(ISSUES.created, [])

    def test_confirm_keeps_the_version_and_closes_the_note(self):
        ISSUES.open.clear()
        p = plug(share=True)
        p._ask_katalog()
        p.confirm_katalog(True)
        self.assertTrue(p.share_usage)
        self.assertEqual(p._usage["katalog"], 1)
        self.assertTrue(p.katalog_ok())
        self.assertNotIn("share_usage_check", ISSUES.open)
        self.assertGreaterEqual(p._evcc_store.saves, 1)

    def test_decline_switches_sharing_off_and_the_ids_are_then_deleted(self):
        ISSUES.open.clear()
        rm = mods["rueckmeldung"]
        p = plug(share=True, usage={"kennungen": [{"k": "a", "monat": "2026-11"}]})
        p._ask_katalog()
        p.confirm_katalog(False)
        self.assertFalse(p.share_usage)
        self.assertNotIn("katalog", p._usage)
        self.assertNotIn("share_usage_check", ISSUES.open)
        self.assertEqual(rm.zu_loeschen(p._usage, p.share_usage), "a")   # the weekly data: delete like after switching off

    def test_yes_to_the_question_keeps_the_version_no_note_twice(self):
        ISSUES.open.clear()
        ISSUES.created.clear()
        p = plug()
        p.answer_usage(True)
        self.assertEqual(p._usage["katalog"], 1)
        p._ask_katalog()
        self.assertEqual(ISSUES.created, [])

    def test_set_up_version_survives_a_later_change_of_the_settings(self):
        p = plug(options={"share_usage": True, "katalog": 1}, share=True)
        p.ask_usage_once()
        self.assertEqual(p._usage["katalog"], 1)
        p.entry.options = {}   # the options flow replaces the options
        self.assertTrue(p.katalog_ok())

    def test_switch_turned_on_counts_as_agreed(self):
        sw = importlib.import_module(f"{PKG}.switch")
        p = plug()
        s = sw.ShareSwitch.__new__(sw.ShareSwitch)
        s.plug = p
        s.async_write_ha_state = lambda: None
        run(s.async_turn_on())
        self.assertTrue(p.share_usage)
        self.assertEqual(p._usage["katalog"], 1)


if __name__ == "__main__":
    unittest.main()
