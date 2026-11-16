"""Safety check before every departure: promise, when to charge now, when it ends. The night of 16.11.2026 replayed."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

import sicherheit as s  # noqa: E402

TZ = timezone(timedelta(hours=1))
SUN_EVENING = datetime(2026, 11, 15, 18, 50, tzinfo=TZ)
MON_7 = datetime(2026, 11, 16, 7, 0, tzinfo=TZ)
CAP, EFF, KW = 66.0, 0.9, 11.0


def chk(now, promise, planned, soc, charging=False, stalled=0.0, plugged=True):
    return s.check(now, promise, planned, soc, plugged=plugged, charging=charging, stalled_min=stalled,
                   capacity_kwh=CAP, efficiency=EFF, max_kw=KW)


class PromiseTests(unittest.TestCase):
    def test_kept_and_raised_while_plugged(self):
        p = s.update_promise(None, MON_7, 100.0, True, SUN_EVENING)
        self.assertEqual(p, s.Promise(MON_7, 100.0))
        p = s.update_promise(p, MON_7, 40.0, True, SUN_EVENING + timedelta(hours=5))   # Plugwhen lowered its target at midnight
        self.assertEqual(p.target, 100.0)

    def test_follows_a_departure_that_moved_an_hour(self):
        p = s.update_promise(s.Promise(MON_7, 100.0), MON_7 + timedelta(hours=1), 40.0, True, SUN_EVENING + timedelta(hours=7))
        self.assertEqual(p, s.Promise(MON_7 + timedelta(hours=1), 100.0))

    def test_unplugged_forgets(self):
        self.assertIsNone(s.update_promise(s.Promise(MON_7, 100.0), MON_7, 100.0, False, SUN_EVENING))

    def test_after_the_departure_a_new_promise(self):
        tue = MON_7 + timedelta(days=1)
        p = s.update_promise(s.Promise(MON_7, 100.0), tue, 45.0, True, MON_7 + timedelta(hours=4))
        self.assertEqual(p, s.Promise(tue, 45.0))


class CheckTests(unittest.TestCase):
    def test_nothing_before_three_hours(self):
        self.assertIsNone(chk(MON_7 - timedelta(hours=4), s.Promise(MON_7, 100.0), 40.0, 28.0))

    def test_the_night_of_16_11_is_caught(self):
        # 04:00, Plugwhen's own target had fallen to 40 %, the promise was 100 %
        a = chk(MON_7 - timedelta(hours=3), s.Promise(MON_7, 100.0), 40.5, 28.0)
        self.assertEqual(a.reason, "target_fell")
        self.assertAlmostEqual(a.missing_kwh, round(72 / 100 * CAP / EFF, 1))

    def test_a_wallbox_that_does_not_charge(self):
        a = chk(MON_7 - timedelta(hours=2), s.Promise(MON_7, 45.0), 45.0, 40.0, charging=False, stalled=12)
        self.assertEqual(a.reason, "stalled")

    def test_tight_time(self):
        # 20 kWh missing, 2 h left at 11 kW = 22 kWh possible: tight
        a = chk(MON_7 - timedelta(hours=2), s.Promise(MON_7, 70.0), 70.0, 70.0 - 20 * EFF / CAP * 100, charging=True)
        self.assertEqual(a.reason, "tight")

    def test_plenty_of_time_while_charging_is_fine(self):
        self.assertIsNone(chk(MON_7 - timedelta(hours=3), s.Promise(MON_7, 45.0), 45.0, 40.0, charging=True))

    def test_reached_or_unplugged_or_unknown_soc_no_alarm(self):
        self.assertIsNone(chk(MON_7 - timedelta(hours=1), s.Promise(MON_7, 100.0), 100.0, 99.6))
        self.assertIsNone(chk(MON_7 - timedelta(hours=1), s.Promise(MON_7, 100.0), 40.0, 28.0, plugged=False))
        self.assertIsNone(chk(MON_7 - timedelta(hours=1), s.Promise(MON_7, 100.0), 40.0, None))

    def test_after_the_departure_nothing(self):
        self.assertIsNone(chk(MON_7 + timedelta(minutes=5), s.Promise(MON_7, 100.0), 40.0, 28.0))


class DoneTests(unittest.TestCase):
    def test_ends(self):
        p = s.Promise(MON_7, 100.0)
        self.assertFalse(s.charge_now_done(MON_7 - timedelta(hours=1), p, 80.0, True))
        self.assertTrue(s.charge_now_done(MON_7 - timedelta(hours=1), p, 99.5, True))
        self.assertTrue(s.charge_now_done(MON_7, p, 80.0, True))
        self.assertTrue(s.charge_now_done(MON_7 - timedelta(hours=1), p, 80.0, False))
        self.assertTrue(s.charge_now_done(MON_7 - timedelta(hours=1), None, 80.0, True))


class TextTests(unittest.TestCase):
    def test_both_languages(self):
        a = s.Alarm("target_fell", 52.8, 100.0, 28.0, 2.5)
        title, msg = s.alarm_text("de", a, "Auto")
        self.assertIn("lädt jetzt", title)
        self.assertIn("2 h 30 min", msg)
        self.assertIn("52,8 kWh", msg)
        self.assertIn("Sicherheitsprüfung: das geplante", msg)
        title, msg = s.alarm_text("en", a, "Car")
        self.assertIn("charging now", title)


if __name__ == "__main__":
    unittest.main()
