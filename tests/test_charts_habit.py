"""Tests for the habit chart."""

from __future__ import annotations

import sys
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

from charts import BLUE, SUN, chart_habit  # noqa: E402
from habit import charging_habit  # noqa: E402

TZ = timezone(timedelta(hours=1))
START = datetime(2026, 9, 7, 0, 0, tzinfo=TZ)
NOW = START + timedelta(days=70)


def habit():
    s = {}
    for d in range(70):
        for h in range(24):
            t = START + timedelta(days=d, hours=h)
            s[t] = 3.0 if (t.weekday() in (2, 3) and h in (22, 23)) or (t.weekday() in (5, 6) and 11 <= h < 13) else 0.0
    return charging_habit(s, NOW)


class HabitChartTest(unittest.TestCase):
    def test_valid_svg_with_both_colours_and_the_weekdays(self):
        for lang, wd, title in (("de", "Mi", "Wann laden Sie?"), ("en", "Wed", "When do you charge?")):
            svg = chart_habit(habit(), lang)
            ET.fromstring(svg)
            self.assertIn(BLUE, svg)
            self.assertIn(SUN, svg)
            self.assertIn(wd, svg)
            self.assertIn(title, svg)
        self.assertIn("nachts", chart_habit(habit(), "de"))

    def test_without_enough_data_it_says_so(self):
        for h in (None, {}, {"status": "too_little_data"}):
            svg = chart_habit(h, "de")
            ET.fromstring(svg)
            self.assertIn("zu wenig Daten", svg)


if __name__ == "__main__":
    unittest.main()
