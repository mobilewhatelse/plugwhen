"""Tests for the sun windows: when does plugging in with the sun make sense (works without a solar plant, then there are none)."""

from __future__ import annotations

import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from charts import chart_sun_windows  # noqa: E402
from test_horizon import SAT, at, plan, sun  # noqa: E402


class SunWindowsTest(unittest.TestCase):
    def test_the_sunny_weekend_gives_two_windows_inside_the_home_times(self):
        r = plan()
        w = r["sun_windows"]
        self.assertEqual(len(w), 2)
        self.assertTrue(all(x["sun_kwh"] >= 10 for x in w))
        self.assertEqual(w[0]["from"][11:16], "10:00")
        self.assertEqual(w[0]["to"][11:16], "13:00")
        for x in w:                                              # every window lies in the time the car is at home
            self.assertLessEqual(x["home_from"], x["from"])
            self.assertLessEqual(x["to"], x["departure"])

    def test_windows_that_replace_grid_energy_are_recommended(self):
        r = plan()
        self.assertEqual({x["purpose"] for x in r["sun_windows"]}, {"precharge"})
        self.assertEqual(r["best_sun_window"]["from"], r["sun_windows"][0]["from"])

    def test_sun_without_a_need_is_a_spare_window_and_never_the_best_one(self):
        r = plan(soc_kwh=60.0)                                   # a full battery: nothing is missing anywhere in the sunny days
        self.assertTrue(r["sun_windows"])
        self.assertTrue(all(x["purpose"] == "spare" for x in r["sun_windows"]))
        self.assertIsNone(r["best_sun_window"])

    def test_without_a_solar_forecast_there_are_no_windows(self):
        r = plan(sun_kw=None)
        self.assertEqual(r["sun_windows"], [])
        self.assertIsNone(r["best_sun_window"])

    def test_a_cloud_for_one_quarter_hour_does_not_split_a_window(self):
        s = sun(days=(0,))
        del s[at(0, 11, 15)]
        r = plan(sun_kw=s)
        self.assertEqual(len(r["sun_windows"]), 1)

    def test_a_longer_gap_splits_the_window(self):
        s = sun(days=(0,))
        for m in (0, 15, 30, 45):
            del s[at(0, 11, m)]
        r = plan(sun_kw=s)
        self.assertEqual(len(r["sun_windows"]), 2)

    def test_power_below_the_minimum_is_not_a_window(self):
        r = plan(sun_kw=sun(kw=0.5))
        self.assertEqual(r["sun_windows"], [])


class SunChartTest(unittest.TestCase):
    def test_valid_svg_in_both_languages_with_weekdays_and_the_best_window(self):
        for lang, wd, best in (("de", "Sa", "Am sinnvollsten"), ("en", "Sat", "Best:")):
            svg = chart_sun_windows(plan(), SAT, lang)
            ET.fromstring(svg)
            self.assertIn(wd, svg)
            self.assertIn(best, svg)
            self.assertIn("#f2b632", svg)                        # sun
            self.assertIn("#f0883e", svg)                        # the recommended frame

    def test_without_a_solar_forecast_it_says_so(self):
        for lang, text in (("de", "Ohne Solarprognose"), ("en", "Without a solar forecast")):
            svg = chart_sun_windows(plan(sun_kw=None), SAT, lang)
            ET.fromstring(svg)
            self.assertIn(text, svg)

    def test_no_sun_in_the_home_times_says_so(self):
        svg = chart_sun_windows(plan(sun_kw=sun(kw=0.2)), SAT, "de")
        ET.fromstring(svg)
        self.assertIn("Keine Sonne", svg)

    def test_unknown_state_of_charge_and_missing_data_do_not_crash(self):
        for h in (None, {}, plan(soc_kwh=None)):
            ET.fromstring(chart_sun_windows(h, SAT, "de"))

    def test_spare_windows_have_no_orange_frame(self):
        svg = chart_sun_windows(plan(soc_kwh=60.0), SAT, "de")
        ET.fromstring(svg)
        self.assertEqual(svg.count("stroke='#f0883e'"), 1)                       # only the frame in the legend
        self.assertGreater(chart_sun_windows(plan(), SAT, "de").count("stroke='#f0883e'"), 1)


if __name__ == "__main__":
    unittest.main()
