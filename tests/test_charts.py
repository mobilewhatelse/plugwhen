"""Tests for the two SVG charts."""

from __future__ import annotations

import sys
import unittest
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

from charts import chart_learning, chart_shadow  # noqa: E402
from insight import learning_check  # noqa: E402
from learning import DayRecord  # noqa: E402

TODAY = date(2027, 3, 15)


def parse(svg):
    return ET.fromstring(svg)          # raises if the SVG is not well-formed


def check():
    recs = [DayRecord(date(2027, 1, 4) + timedelta(days=i), km=150.0 if (i % 7) == 2 else 30.0, first_move_hour=7.0) for i in range(120)]
    return learning_check(recs, 100)


class ChartTest(unittest.TestCase):
    def test_learning_chart_is_valid_svg_in_both_languages(self):
        for lang in ("de", "en"):
            svg = chart_learning(check(), lang)
            root = parse(svg)
            self.assertTrue(root.tag.endswith("svg"))
            self.assertIn("100 %", svg)                                          # learned value covers all days
            self.assertIn("n=", svg)
        self.assertIn("Reserve plus Gelerntes", chart_learning(check(), "de"))
        self.assertIn("Rechtzeitig fertig je Wochentag", chart_learning(check(), "de"))
        self.assertIn("reserve plus learned", chart_learning(check(), "en"))

    def test_learning_chart_without_data_says_so(self):
        for c in (None, {}, learning_check([], 100)):
            svg = chart_learning(c, "de")
            parse(svg)
            self.assertIn("zu wenig Daten", svg)

    def test_shadow_chart_with_few_days_says_still_learning_and_counts(self):
        days = {(TODAY - timedelta(days=1)).isoformat(): {"charge_charging": 7200, "pause_idle": 3600, "pause_charging": 3600, "charge_idle": 0},
                TODAY.isoformat(): {"charge_charging": 0, "pause_idle": 1800, "pause_charging": 0, "charge_idle": 1800}}
        for lang, text in (("de", "Lernt noch · 2 von 7 Tagen"), ("en", "Still learning · 2 of 7 days")):
            svg = chart_shadow(days, TODAY, lang)
            parse(svg)
            self.assertIn(text, svg)
            self.assertNotIn("#2fbf71", svg)                          # no bars until it can say something

    def test_shadow_chart_shows_agreement_and_difference(self):
        days = {(TODAY - timedelta(days=i)).isoformat(): {"charge_charging": 7200, "pause_idle": 3600, "pause_charging": 3600 * (i % 2),
                                                         "charge_idle": 1800 * (i % 3)} for i in range(1, 9)}
        svg = chart_shadow(days, TODAY, "de")
        parse(svg)
        self.assertIn("#2fbf71", svg)
        self.assertIn("#e5534b", svg)
        self.assertIn("abweichend", svg)

    def test_shadow_chart_without_days_says_so(self):
        for d in (None, {}, {TODAY.isoformat(): {"charge_charging": 0, "pause_idle": 0, "pause_charging": 0, "charge_idle": 0}}):
            svg = chart_shadow(d, TODAY, "en")
            parse(svg)
            self.assertIn("No data yet", svg)

    def test_texts_are_escaped(self):
        svg = chart_learning({**check(), "reserve_km": 100}, "en")
        self.assertNotIn("<script", svg)
        parse(svg)

    def test_a_long_history_does_not_break_the_shadow_chart(self):
        days = {(TODAY - timedelta(days=i)).isoformat(): {"charge_charging": 3600 * 3, "pause_idle": 3600 * 10, "pause_charging": 3600 * (i % 5),
                                                         "charge_idle": 0} for i in range(60)}
        parse(chart_shadow(days, TODAY, "de", count=14))


if __name__ == "__main__":
    unittest.main()
