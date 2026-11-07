"""Tests for the plan timeline, the potential bars and the plug-in strip."""

from __future__ import annotations

import sys
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

from charts import BLUE, RED, SUN, chart_plan, chart_plugs, chart_potential  # noqa: E402
from plan import make_plan  # noqa: E402

TZ = timezone(timedelta(hours=1))
NOW = datetime(2027, 1, 12, 17, 5, tzinfo=TZ)
DEPART = datetime(2027, 1, 13, 7, 0, tzinfo=TZ)


def parse(svg):
    return ET.fromstring(svg)


class PlanChartTest(unittest.TestCase):
    def test_planned_grid_only_shows_blue_windows_and_the_departure(self):
        p = make_plan(NOW, DEPART, 11.0, 11.0, 1.4)
        svg = chart_plan(p, NOW, 11.0, "de")
        parse(svg)
        self.assertIn(BLUE, svg)
        self.assertNotIn(f"fill='{SUN}'/><text", svg.split("Sonne")[0][-40:] if False else "")
        self.assertIn("Abfahrt Mi 07:00", svg)
        self.assertIn("jetzt", svg)

    def test_sun_part_is_yellow(self):
        avail = {datetime(2027, 1, 12, 18, 0, tzinfo=TZ) + timedelta(minutes=15 * i): 3.0 for i in range(4)}
        p = make_plan(NOW, DEPART, 6.0, 11.0, 1.4, available_kw=avail)
        svg = chart_plan(p, NOW, 11.0, "en")
        parse(svg)
        self.assertIn(f"fill='{SUN}'", svg)
        self.assertIn("departure Wed 07:00", svg)

    def test_states_without_windows_are_a_short_line(self):
        self.assertIn("nichts geladen", chart_plan(make_plan(NOW, DEPART, 0.0, 11.0, 1.4), NOW, 11.0, "de"))
        self.assertIn("Ladestand unbekannt", chart_plan({"status": "unknown_soc"}, NOW, 11.0, "de"))
        self.assertIn("No departure", chart_plan({"status": "no_departure"}, NOW, 11.0, "en"))
        self.assertIn("Ladestand unbekannt", chart_plan(None, NOW, 11.0, "de"))

    def test_infeasible_says_what_is_missing(self):
        p = make_plan(NOW, NOW + timedelta(hours=1), 40.0, 11.0, 1.4)
        svg = chart_plan(p, NOW, 11.0, "de")
        parse(svg)
        self.assertIn(RED, svg)
        self.assertIn("Es fehlen", svg)

    def test_iso_strings_work_too(self):
        p = make_plan(NOW, DEPART, 11.0, 11.0, 1.4)
        p2 = {**p, "departure": p["departure"].isoformat(),
              "windows": [{**w, "start": w["start"].isoformat(), "end": w["end"].isoformat()} for w in p["windows"]]}
        parse(chart_plan(p2, NOW, 11.0, "de"))


class PotentialChartTest(unittest.TestCase):
    def test_bars_costs_and_not_ready(self):
        pot = {"status": "ok", "strategies": {
            "as_is": {"peaks": {"2026-10": 12.8}, "cost_per_year": 505, "not_ready": 0},
            "guard": {"peaks": {"2026-10": 9.5}, "cost_per_year": 321, "not_ready": 0},
            "fixed": {"peaks": {"2026-10": 6.1}, "cost_per_year": 201, "not_ready": 2},
            "spread": {"peaks": {"2026-10": 8.3}, "cost_per_year": 235, "not_ready": 0}}}
        svg = chart_potential(pot, "de", "€")
        parse(svg)
        for s in ("wie bisher", "12.8 kW · 505 €", "2× nicht fertig", "verteilt (Plugwhen)"):
            self.assertIn(s, svg)

    def test_without_prices_only_kw(self):
        pot = {"status": "ok", "strategies": {"as_is": {"peaks": {"m": 12.0}, "cost_per_year": None, "not_ready": 0},
                                              "spread": {"peaks": {"m": 8.0}, "not_ready": 0}}}
        svg = chart_potential(pot, "en", "$")
        parse(svg)
        self.assertIn("12.0 kW", svg)
        self.assertNotIn("$", svg)

    def test_not_ok_is_a_short_line(self):
        self.assertIn("zu wenig Daten", chart_potential({"status": "too_little_data"}, "de"))
        self.assertIn("data missing", chart_potential({"status": "no_data"}, "en"))
        self.assertIn("data missing", chart_potential(None, "en"))


class PlugChartTest(unittest.TestCase):
    def test_strips_for_fourteen_days(self):
        iv = [(NOW - timedelta(days=2, hours=4), NOW - timedelta(days=1, hours=14)), (NOW - timedelta(hours=3), None)]
        svg = chart_plugs(iv, NOW, "de")
        root = parse(svg)
        self.assertGreaterEqual(svg.count(f"fill='{BLUE}'"), 3)          # the night across midnight is two pieces, plus now
        self.assertIn("Di 12.01.", svg)
        self.assertTrue(root.tag.endswith("svg"))

    def test_old_intervals_are_ignored_and_empty_says_so(self):
        svg = chart_plugs([(NOW - timedelta(days=40), NOW - timedelta(days=39))], NOW, "en")
        parse(svg)
        self.assertNotIn(f"fill='{BLUE}'", svg)
        self.assertIn("No plug-in times", chart_plugs([], NOW, "en"))


if __name__ == "__main__":
    unittest.main()
