"""Bug report: nothing that identifies anybody, flat enough for the server (three levels), small enough (16 KB with the text)."""

from __future__ import annotations

import json
import logging
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.append(str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

import fehlerbericht as fb  # noqa: E402

NOW = datetime(2026, 11, 15, 18, 0, tzinfo=timezone.utc)


def depth(x, d=0):
    if isinstance(x, dict):
        return max([depth(v, d + 1) for v in x.values()] or [d])
    if isinstance(x, list):
        return max([depth(v, d + 1) for v in x] or [d])
    return d


class AnonymTests(unittest.TestCase):
    def test_nothing_that_identifies(self):
        t = fb.anonym("Mein Tesla Rot: select.tesla_rot_lademodus antwortet nicht, http://192.168.5.10:8123/api von max@example.com,"
                      " Eintrag 01JABCDEF0123456789abcdef0 VIN WVWZZZ1JZXW000001 an 10.0.0.2", ["Mein Tesla Rot"])
        for bad in ("Tesla Rot", "tesla_rot", "192.168", "max@", "example.com", "WVWZZZ", "10.0.0.2", "01JABCDEF"):
            self.assertNotIn(bad, t)
        self.assertIn("select antwortet nicht", t)
        self.assertIn("<name>", t)

    def test_versions_stay(self):
        self.assertEqual(fb.anonym("Version 0.9.1 auf 2026.11.1"), "Version 0.9.1 auf 2026.11.1")

    def test_none_and_limit(self):
        self.assertIsNone(fb.anonym(None))
        self.assertEqual(len(fb.anonym("x" * 900)), 300)


class CallsTests(unittest.TestCase):
    def test_slow_and_failed(self):
        c = fb.Calls()
        c.call("select.a", 2.0)
        c.call("select.a", 24.0)
        c.call("select.a", 1.0, TimeoutError())
        c.reply("select.a", True, 30.0)
        c.reply("select.a", False, None)
        s = c.summary("select.a")
        self.assertEqual((s["befehle"], s["langsam"], s["fehlgeschlagen"], s["laengste_s"]), (3, 1, 1, 24.0))
        self.assertEqual(s["fehlerarten"], {"TimeoutError": 1})
        self.assertEqual((s["uebernommen"], s["nicht_uebernommen"], s["uebernahme_laengste_s"]), (1, 1, 30.0))
        self.assertIn("1 langsam", c.text("select.a"))
        self.assertIsNone(c.text("select.b"))


class LinesTests(unittest.TestCase):
    def test_keeps_only_warnings_and_the_last_ones(self):
        h = fb.Lines()
        log = logging.getLogger("fb_test")
        log.addHandler(h)
        log.propagate = False
        try:
            log.info("not kept")
            for i in range(30):
                log.warning("Wallbox %s", i)
        finally:
            log.removeHandler(h)
        self.assertEqual(len(h.lines), fb.MAX_LINES)
        self.assertEqual(h.lines[-1][2], "Wallbox 29")


class SensorTests(unittest.TestCase):
    def test_states(self):
        self.assertEqual(fb.sensor_state(None), "fehlt")
        self.assertEqual(fb.sensor_state(SimpleNamespace(state="unavailable")), "nicht_verfuegbar")
        self.assertEqual(fb.sensor_state(SimpleNamespace(state="unknown")), "unbekannt")
        self.assertEqual(fb.sensor_state(SimpleNamespace(state="55", last_reported=NOW - timedelta(minutes=5)), NOW), "ok")
        self.assertEqual(fb.sensor_state(SimpleNamespace(state="55", last_reported=NOW - timedelta(hours=3)), NOW), "ok, älter als 1 h")


class PlanTextTests(unittest.TestCase):
    def test_relative_only(self):
        self.assertEqual(fb.rel_h(NOW + timedelta(hours=2, minutes=30), NOW), "in 2.5 h")
        self.assertEqual(fb.rel_h((NOW - timedelta(hours=1)).isoformat(), NOW), "vor 1.0 h")
        self.assertIsNone(fb.rel_h(None, NOW))

    def test_windows(self):
        plan = {"status": "planned", "needed_kwh": 6.7, "planned_kwh": 6.7,
                "windows": [{"start": NOW + timedelta(hours=2), "end": NOW + timedelta(hours=3, minutes=30), "energy_kwh": 6.7,
                             "peak_kw": 7.4}]}
        txt = fb.windows_text(plan, NOW)
        self.assertIn("in 2.0 h für 1.50 h 6.7 kWh (max 7.4 kW)", txt)
        self.assertNotIn("18:", txt)   # no clock time
        self.assertIn("keine Fenster", fb.windows_text({"status": "unknown_soc", "windows": []}, NOW))
        self.assertIsNone(fb.windows_text(None, NOW))


class ReportTests(unittest.TestCase):
    def report(self, lines=5):
        autos = [{"betriebsart": "direct", "wallbox_mode": "anker_solix: 3 Befehle, Mittel 21.3 s",
                  "sensor_soc": "ok (mercedesme)", "extra": {"a": {"b": 1}}, "kalender_fehler": "Kalender Familie Huber fehlt"}]
        zeilen = [("15. 19:44", "WARNING", f"Plugwhen: wallbox of Mein Auto not controlled: switch.ev_laden_pause {'x' * 200}")
                  for _ in range(lines)]
        return fb.bericht("0.9.1", "2026.11.1", {"autos": 1, "herkunft": ["anker_solix"], "betriebsarten": {"direct": 1}},
                          autos, zeilen, {"evcc": None}, ["Mein Auto", "Familie Huber"])

    def test_flat_enough_for_the_server(self):
        self.assertLessEqual(depth(self.report()), 3)   # the server keeps three levels (gemeinsam.php sauber)

    def test_no_names_or_entity_ids(self):
        s = json.dumps(self.report(), ensure_ascii=False)
        for bad in ("Mein Auto", "Huber", "ev_laden_pause"):
            self.assertNotIn(bad, s)
        self.assertNotIn("evcc", self.report()["fehler"], "empty errors are left out")

    def test_small_enough(self):
        b = self.report(lines=20)
        self.assertLessEqual(len(json.dumps(b, ensure_ascii=False).encode()), fb.MAX_BYTES)
        self.assertGreater(len(b["protokoll"]), 0)

    def test_display_after_sending(self):
        b = self.report()
        v = fb.anzeige(b, True, True)
        self.assertIn("ist angekommen", v)
        self.assertIn("anker_solix: 3 Befehle", v)
        self.assertIn("Protokoll:", v)
        self.assertIn("wäre genau das", fb.anzeige(b, True, False))
        self.assertIn("Exactly this was sent", fb.anzeige(b, False, True))


class NoClockTests(unittest.TestCase):
    """Feedback 15.11.: the first real report carried the last press of a button and the departure time as clock times."""

    def test_masked_in_texts(self):
        t = fb.anonym("Abfahrt 07:20:00, gedrückt 2026-11-12T05:40:41.758274+00:00, Version 0.9.1 auf 2026.11.1")
        self.assertNotIn("07:20", t)
        self.assertNotIn("05:40", t)
        self.assertIn("0.9.1", t)
        self.assertIn("2026.11.1", t)

    def test_setting_now(self):
        self.assertEqual(fb.state_text("button.start", (NOW - timedelta(hours=3)).isoformat(), NOW), "gedrückt vor 3.0 h")
        self.assertEqual(fb.state_text("time.trip_time", "07:20:00", NOW), "gesetzt")
        self.assertEqual(fb.state_text("select.mode", "Eco", NOW), "Eco")
        self.assertEqual(fb.state_text("number.energy", "30000.0", NOW), "30000.0")

    def test_log_lines_relative(self):
        import time
        self.assertEqual(fb.ago(time.time() - 7200), "vor 2.0 h")


class GenericNameTests(unittest.TestCase):
    """Feedback 15.11.: devices called "Wallbox" and "Mercedes" erased the kind, the maker and an integration in the report."""

    def test_generic_words_are_no_names(self):
        keep = ["wallbox", "jackery", "Mercedes-Benz", "EQB 250"]
        self.assertEqual(fb.real_names(["Wallbox", "Mercedes", "Jackery", "Familie Huber", "", None], keep), ["Familie Huber"])

    def test_kind_and_maker_stay(self):
        t = fb.anonym("wallbox: mbapi2020, Mercedes-Benz, EQB 250", fb.real_names(["Wallbox", "Mercedes"], ["wallbox", "Mercedes-Benz"]))
        self.assertEqual(t, "wallbox: mbapi2020, Mercedes-Benz, EQB 250")


if __name__ == "__main__":
    unittest.main()
