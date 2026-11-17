"""A lone short grid piece is folded into the other windows (field case 17.11.2026: 12.4 + 7.3 + 1.0 kWh at 06:45)."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

import plan as P  # noqa: E402

TZ = timezone(timedelta(hours=1))
NOW = datetime(2026, 11, 17, 19, 52, tzinfo=TZ)
DEP = datetime(2026, 11, 18, 7, 0, tzinfo=TZ)


def at(h, m, day=17):
    return datetime(2026, 11, day, h, m, tzinfo=TZ)


def load(quiet, busy=2.0):
    out, t = [], at(19, 45)
    while t < DEP:
        out.append({"t": t, "typical": 0.3, "high": 0.4 if quiet(t) else busy, "n": 10})
        t += timedelta(minutes=15)
    return out


def field_quiet(t):
    return at(22, 45) <= t < at(1, 45, 18) or at(3, 0, 18) <= t < at(4, 45, 18) or t == at(6, 45, 18)


def windows(p):
    return [(w["start"].strftime("%H:%M"), w["end"].strftime("%H:%M")) for w in p["windows"]]


class FoldTest(unittest.TestCase):
    def test_the_quarter_hour_before_the_departure_goes_into_the_two_big_windows(self):
        p = P.make_plan(NOW, DEP, 20.7, 11.0, 1.4, load=load(field_quiet), target_kw=10.0, pref_kw=4.0)
        self.assertEqual(p["status"], "planned")
        self.assertEqual(windows(p), [("22:45", "01:45"), ("03:00", "04:45")])
        self.assertAlmostEqual(p["planned_kwh"], 20.7, delta=0.05)          # nothing lost
        self.assertLess(max(w["peak_kw"] for w in p["windows"]), 4.14 + P.FOLD_KW)
        self.assertEqual(p["ready_at"], at(4, 45, 18))

    def test_without_folding_it_would_be_three_pieces(self):
        old = P.SMALL_PIECE_QUARTERS
        P.SMALL_PIECE_QUARTERS = 0
        try:
            p = P.make_plan(NOW, DEP, 20.7, 11.0, 1.4, load=load(field_quiet), target_kw=10.0, pref_kw=4.0)
        finally:
            P.SMALL_PIECE_QUARTERS = old
        self.assertEqual(len(p["windows"]), 3)

    def test_kept_when_folding_would_raise_the_peak_too_much(self):
        # only two quiet quarter hours besides the lone one: 1 kWh more on half an hour is 2 kW more, far above FOLD_KW
        quiet = lambda t: t in (at(23, 0), at(23, 15), at(6, 45, 18))   # noqa: E731
        p = P.make_plan(NOW, DEP, 3.0, 11.0, 1.4, load=load(quiet, busy=9.0), target_kw=10.0, pref_kw=4.0)
        self.assertEqual(len(p["windows"]), 2)

    def test_kept_when_it_would_go_above_the_peak_target(self):
        p = P.make_plan(NOW, DEP, 20.7, 11.0, 1.4, load=load(field_quiet), target_kw=4.5, pref_kw=4.0)
        for w in p["windows"]:
            self.assertLessEqual(w["peak_kw"], 4.5 - 0.4 + 1e-6)

    def test_a_single_window_stays_as_it_is(self):
        quiet = lambda t: at(22, 45) <= t < at(1, 45, 18)   # noqa: E731
        p = P.make_plan(NOW, DEP, 6.0, 11.0, 1.4, load=load(quiet), target_kw=10.0, pref_kw=4.0)
        self.assertEqual(len(p["windows"]), 1)


if __name__ == "__main__":
    unittest.main()
