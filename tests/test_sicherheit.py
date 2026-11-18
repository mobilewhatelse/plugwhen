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


def chk(now, promise, planned, soc, charging=False, stalled=0.0, plugged=True, **more):
    return s.check(now, promise, planned, soc, plugged=plugged, charging=charging, stalled_min=stalled,
                   capacity_kwh=CAP, efficiency=EFF, max_kw=KW, **more)


def soc_missing(kwh: float, target: float = 100.0) -> float:
    """The state of charge at which `kwh` from the wallbox are missing to `target`."""
    return target - kwh * EFF / CAP * 100.0


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

    def test_a_later_departure_does_not_raise_or_move_the_promise(self):
        # review 16.11.: the later departure's target (e.g. the weekly 100 %) was taken into the promise of the earlier one
        tue = MON_7 + timedelta(days=1)
        p = s.update_promise(s.Promise(MON_7, 45.0), tue, 100.0, True, SUN_EVENING)
        self.assertEqual(p, s.Promise(MON_7, 45.0))

    def test_a_departure_the_user_took_away_takes_the_promise_with_it(self):
        # review 16.11.: a deleted calendar trip left "charge now" for a trip that no longer existed
        tue = MON_7 + timedelta(days=1)
        p = s.update_promise(s.Promise(MON_7, 100.0), tue, 55.0, True, SUN_EVENING, still_expected=False)
        self.assertEqual(p, s.Promise(tue, 55.0))


class StallTests(unittest.TestCase):
    def test_counts_only_a_wallbox_that_says_it_does_not_charge(self):
        t0 = MON_7 - timedelta(hours=2)
        self.assertEqual(s.stall_start(None, t0, True, True, True, False), t0)
        self.assertEqual(s.stall_start(t0, t0 + timedelta(minutes=5), True, True, True, False), t0)
        self.assertIsNone(s.stall_start(t0, t0, True, True, True, True))      # charging
        self.assertIsNone(s.stall_start(t0, t0, False, True, True, False))    # no window
        self.assertIsNone(s.stall_start(t0, t0, True, False, True, False))    # unplugged

    def test_an_unreachable_wallbox_is_no_stall(self):
        # review 16.11.: the nightly Wi-Fi restart made "unavailable" count as "does not charge"
        t0 = MON_7 - timedelta(hours=2)
        self.assertIsNone(s.stall_start(None, t0, True, None, False, False))
        self.assertIsNone(s.stall_start(t0 - timedelta(minutes=9), t0, True, None, False, False))


class CheckTests(unittest.TestCase):
    def test_weekly_full_booked_done_at_99_is_no_alarm(self):
        # review 16.11.: at 99 % the weekly full charge is done and its target falls back on purpose; 0.7 kWh "missing" to the
        # promised 100 % raised "target fell" in the last hours before every such departure
        self.assertIsNone(chk(MON_7 - timedelta(hours=1, minutes=30), s.Promise(MON_7, 100.0), 55.0, 99.0, charging=True))
        self.assertEqual(chk(MON_7 - timedelta(hours=1, minutes=30), s.Promise(MON_7, 100.0), 55.0, 98.0).reason, "target_fell")

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
        self.assertEqual(a.reason, "tight")   # charging, but "charge now" would be faster (e.g. the sun mode)

    def test_plenty_of_time_while_charging_is_fine(self):
        self.assertIsNone(chk(MON_7 - timedelta(hours=3), s.Promise(MON_7, 45.0), 45.0, 40.0, charging=True))

    def test_reached_or_unplugged_or_unknown_soc_no_alarm(self):
        self.assertIsNone(chk(MON_7 - timedelta(hours=1), s.Promise(MON_7, 100.0), 100.0, 99.6))
        self.assertIsNone(chk(MON_7 - timedelta(hours=1), s.Promise(MON_7, 100.0), 40.0, 28.0, plugged=False))
        self.assertIsNone(chk(MON_7 - timedelta(hours=1), s.Promise(MON_7, 100.0), 40.0, None))

    def test_after_the_departure_nothing(self):
        self.assertIsNone(chk(MON_7 + timedelta(minutes=5), s.Promise(MON_7, 100.0), 40.0, 28.0))


class NextTripTests(unittest.TestCase):
    """The night of 17./18.11.2026: Wattpilot in "Next Trip", 20.7 kWh missing, departure 07:00. The wallbox started by itself
    at 04:02 - and 13 seconds later the check switched it to "charge now" and sent a message. It charged all along."""

    AT = MON_7 - timedelta(hours=2, minutes=58)
    P = s.Promise(MON_7, 100.0)

    def test_that_night_charging_in_next_trip_nothing_happens(self):
        self.assertIsNone(chk(self.AT, self.P, 100.0, soc_missing(20.7), charging=True, can_speed_up=False, trip=True))

    def test_charging_as_fast_as_allowed_is_left_alone_however_tight(self):
        # throttled by a peak guard to 6 kW with 25 kWh missing in 2 h: switching would gain nothing, so nothing is told
        now = MON_7 - timedelta(hours=2)
        for trip in (True, False):
            self.assertIsNone(chk(now, s.Promise(MON_7, 100.0), 100.0, soc_missing(25.0), charging=True, can_speed_up=False, trip=trip))

    def test_charging_slowly_in_the_sun_mode_is_still_taken_over(self):
        now = MON_7 - timedelta(hours=2)
        a = chk(now, s.Promise(MON_7, 100.0), 100.0, soc_missing(20.0), charging=True, can_speed_up=True, trip=True)
        self.assertEqual(a.reason, "tight")

    def test_not_started_yet_is_no_alarm_at_three_hours(self):
        # "next trip" starts late on purpose: 20.7 kWh in 2 h 58 min at 11 kW is 63 % of the time left
        self.assertIsNone(chk(self.AT, self.P, 100.0, soc_missing(20.7), charging=False, can_speed_up=False, trip=True))

    def test_not_started_when_it_gets_really_tight_charges_now(self):
        now = MON_7 - timedelta(hours=2, minutes=15)   # 20.7 kWh of 24.75 possible = 84 %
        a = chk(now, self.P, 100.0, soc_missing(20.7), charging=False, can_speed_up=False, trip=True)
        self.assertEqual(a.reason, "tight")

    def test_other_wallboxes_keep_the_earlier_threshold(self):
        a = chk(self.AT, self.P, 100.0, soc_missing(20.7), charging=False, trip=False)
        self.assertEqual(a.reason, "tight")

    def test_a_plan_window_without_charging_is_no_stall_for_next_trip(self):
        now = MON_7 - timedelta(hours=2)
        self.assertIsNone(chk(now, s.Promise(MON_7, 45.0), 45.0, 40.0, charging=False, stalled=30, trip=True))
        self.assertEqual(chk(now, s.Promise(MON_7, 45.0), 45.0, 40.0, charging=False, stalled=30, trip=False).reason, "stalled")

    def test_a_fallen_target_is_caught_also_while_charging(self):
        # Plugwhen's own target fell: the wallbox was given too little energy and will stop early, charging or not
        a = chk(self.AT, self.P, 40.0, 28.0, charging=True, can_speed_up=False, trip=True)
        self.assertEqual(a.reason, "target_fell")


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

    def test_the_sentence_keeps_its_full_stop(self):
        _title, msg = s.alarm_text("de", s.Alarm("target_fell", 52.8, 100.0, 28.0, 2.5), "Auto")
        self.assertIn("zugesagt. Es fehlen noch 52,8 kWh", msg)

    def test_says_so_when_the_wallbox_was_not_switched(self):
        a = s.Alarm("tight", 20.0, 80.0, 50.0, 1.5)
        title, msg = s.alarm_text("de", a, "Auto", switched=False)
        self.assertIn("bitte Laden starten", title)
        self.assertIn("konnte die Wallbox nicht", msg)
        self.assertNotIn("hat auf", msg)
        title, msg = s.alarm_text("en", a, "Car", switched=False)
        self.assertIn("please start charging", title)
        self.assertIn("could not switch", msg)


if __name__ == "__main__":
    unittest.main()
