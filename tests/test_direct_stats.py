"""How the wallbox follows in the mode 'direct' (direct_stats.py)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

import direct_stats as ds  # noqa: E402


class DirectStatsTest(unittest.TestCase):
    def test_key_has_no_names(self):
        self.assertEqual(ds.key("go_e", "Gemini flex 11kW", None), "go_e|Gemini flex 11kW|?")
        self.assertEqual(ds.key("a|b", "", "1.2"), "a/b|?|1.2")

    def test_summary(self):
        s = {}
        k = ds.key("go_e", "Gemini", "56.2")
        for sec in (2, 3, 4, 5, 60):
            ds.record(s, k, True, sec)
        ds.record(s, k, False)
        out = ds.summary(s)
        self.assertEqual(out, [{"art": "wallbox", "integration": "go_e", "modell": "Gemini", "firmware": "56.2",
                                "befehle": 6, "fehl_anteil": 0.17, "antwort_s_median": 4, "antwort_s_p95": 60}])

    def test_limits(self):
        s = {}
        for i in range(5):
            ds.record(s, f"p|m{i}|f", True, 1)
        self.assertEqual(len(s), ds.MAX_MODELS)
        for i in range(80):
            ds.record(s, "p|m0|f", True, i)
        self.assertEqual(len(s["p|m0|f"]["t"]), ds.MAX_TIMES)

    def test_only_failures_no_times(self):
        s = {}
        ds.record(s, "p|m|f", False)
        self.assertEqual(ds.summary(s)[0]["fehl_anteil"], 1.0)
        self.assertNotIn("antwort_s_median", ds.summary(s)[0])
        self.assertEqual(ds.summary({}), [])


if __name__ == "__main__":
    unittest.main()
