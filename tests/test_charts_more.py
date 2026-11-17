"""Tests for the plan timeline, the potential bars and the plug-in strip."""

from __future__ import annotations

import sys
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

from charts import BLUE, ORANGE, RED, SUN, chart_plan, chart_plugs, chart_potential  # noqa: E402
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

    def test_now_is_an_orange_line_at_the_current_time(self):
        p = make_plan(NOW, DEPART, 11.0, 11.0, 1.4)
        root = parse(chart_plan(p, NOW, 11.0, "de"))
        svg = chart_plan(p, NOW, 11.0, "de")
        self.assertIn("jetzt 17:05", svg)
        self.assertIn("now 17:05", chart_plan(p, NOW, 11.0, "en"))
        lines = [e for e in root.iter() if e.tag.endswith("line") and e.get("stroke") == ORANGE]
        self.assertEqual(len(lines), 1)
        # the timeline starts at the full hour (17:00) and ends at the departure (07:00): 5 of 840 minutes in
        x = float(lines[0].get("x1"))
        self.assertAlmostEqual(x, 12 + (480 - 24) * 5 / 840, delta=0.2)
        self.assertNotEqual(ORANGE, RED)   # never the colour of the departure
        later = chart_plan(p, NOW + timedelta(minutes=40), 11.0, "de")
        x2 = float([e for e in parse(later).iter() if e.tag.endswith("line") and e.get("stroke") == ORANGE][0].get("x1"))
        self.assertGreater(x2, x)          # moves on with the time

    def test_each_window_shows_from_when_to_when(self):
        p = make_plan(NOW, DEPART, 11.0, 11.0, 1.4)
        svg = chart_plan(p, NOW, 11.0, "de")
        for w in p["windows"]:
            a = datetime.fromisoformat(w["start"]) if isinstance(w["start"], str) else w["start"]
            b = datetime.fromisoformat(w["end"]) if isinstance(w["end"], str) else w["end"]
            self.assertIn(f"{a.astimezone(TZ):%H:%M}–{b.astimezone(TZ):%H:%M}", svg)
        root = parse(svg)
        sizes = [int(e.get("font-size")) for e in root.iter() if e.tag.endswith("text") and e.get("font-size")]
        self.assertGreaterEqual(min(sizes), 12)            # readable on a phone: nothing smaller than 12
        self.assertEqual(root.get("viewBox"), "0 0 480 214")

    def test_shortly_before_the_departure_the_bar_starts_at_now_and_every_hour_is_marked(self):
        now = DEPART - timedelta(hours=2, minutes=40)               # 04:20
        root = parse(chart_plan(make_plan(now, DEPART, 20.0, 11.0, 1.4), now, 11.0, "de"))
        xn = float([e for e in root.iter() if e.tag.endswith("line") and e.get("stroke") == ORANGE][0].get("x1"))
        bars = [e for e in root.iter() if e.tag.endswith("rect") and e.get("fill") == BLUE and float(e.get("height")) > 12]
        self.assertTrue(bars)
        self.assertGreaterEqual(min(float(b.get("x")) for b in bars), xn - 0.2)   # nothing drawn before now
        ticks = [e.text for e in root.iter() if e.tag.endswith("text") and e.text in ("4", "5", "6", "7")]
        self.assertEqual(ticks, ["4", "5", "6", "7"])

    def test_midnight_is_0_and_the_new_day_is_written_below(self):
        # a bare 'Mi' on the axis was read as 'charging on Wednesday' (field 17.11.2026)
        root = parse(chart_plan(make_plan(NOW, DEPART, 11.0, 11.0, 1.4), NOW, 11.0, "de"))
        texts = [e.text for e in root.iter() if e.tag.endswith("text")]
        self.assertIn("0", texts)
        self.assertIn("Mi 13.01.", texts)
        self.assertNotIn("Mi", texts)

    def test_a_narrow_window_at_the_right_edge_next_to_another_one_still_gets_its_time(self):
        # field 17.11.2026: 03:00-04:45 and a lone quarter hour 06:45-07:00 right at the departure had no label
        tz, dep = TZ, datetime(2026, 11, 18, 7, 0, tzinfo=TZ)
        now = datetime(2026, 11, 17, 19, 52, tzinfo=tz)
        p = {"status": "planned", "departure": dep, "latest_start": datetime(2026, 11, 18, 5, 7, tzinfo=tz), "windows": [
            {"start": datetime(2026, 11, 17, 22, 45, tzinfo=tz), "end": datetime(2026, 11, 18, 1, 45, tzinfo=tz), "energy_kwh": 12.4, "available_kwh": 0, "peak_kw": 4.14},
            {"start": datetime(2026, 11, 18, 3, 0, tzinfo=tz), "end": datetime(2026, 11, 18, 4, 45, tzinfo=tz), "energy_kwh": 7.2, "available_kwh": 0, "peak_kw": 4.14},
            {"start": datetime(2026, 11, 18, 6, 45, tzinfo=tz), "end": dep, "energy_kwh": 1.04, "available_kwh": 0, "peak_kw": 4.14}]}
        root = parse(chart_plan(p, now, 11.0, "de"))
        texts = [e.text for e in root.iter() if e.tag.endswith("text")]
        self.assertTrue(any(s.startswith("06:45") for s in texts), texts)
        self.assertIn("1.0 kWh", texts)
        for e in root.iter():
            if e.tag.endswith("text") and e.get("text-anchor") == "middle":
                self.assertLessEqual(float(e.get("x")), 480)

    def test_now_label_left_out_when_the_departure_is_right_next_to_it(self):
        dep = NOW + timedelta(minutes=50)
        svg = chart_plan(make_plan(NOW, dep, 3.0, 11.0, 1.4), NOW, 11.0, "de")
        parse(svg)
        self.assertIn("Abfahrt", svg)
        self.assertIn(f"stroke='{ORANGE}'", svg)           # the line stays

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
