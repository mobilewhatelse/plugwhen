"""Tests for the learn mode: decisions and the comparison with reality."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

from plan import make_plan  # noqa: E402
from shadow import Decision, ShadowLog, decide  # noqa: E402

TZ = timezone(timedelta(hours=1))
NOW = datetime(2027, 1, 12, 20, 5, tzinfo=TZ)
DEPART = datetime(2027, 1, 13, 7, 0, tzinfo=TZ)


def planned(**kw):
    args = dict(now=NOW, departure=DEPART, need_kwh=11.0, max_kw=11.0, min_kw=1.4, load=None, target_kw=None)
    args.update(kw)
    return make_plan(**args)


class DecideTest(unittest.TestCase):
    def test_in_a_window_it_charges_and_says_until_when(self):
        p = planned()
        t = next(iter(sorted(p["quarters"]))) + timedelta(minutes=3)
        d = decide(p, t, True, True)
        self.assertEqual((d.action, d.reason), ("charge", "in_window"))
        self.assertGreater(d.until, t)
        self.assertGreater(d.kw, 0)

    def test_between_windows_it_pauses_until_the_next_one(self):
        p = planned()
        d = decide(p, NOW, True, True)                         # the plan is spread, the first quarter is later
        first = min(p["quarters"])
        self.assertEqual((d.action, d.reason), ("pause", "waiting_for_window"))
        self.assertEqual(d.until, first)

    def test_after_the_last_window_the_plan_is_done(self):
        p = planned()
        d = decide(p, max(p["quarters"]) + timedelta(minutes=20), True, True)
        self.assertEqual((d.action, d.reason), ("pause", "plan_done"))

    def test_unknown_things_are_no_decision(self):
        p = planned()
        self.assertEqual(decide(p, NOW, True, False), Decision("none", "unknown_soc"))
        self.assertEqual(decide(p, NOW, False, True), Decision("none", "not_plugged"))
        self.assertEqual(decide(planned(need_kwh=0.0), NOW, True, True).reason, "not_needed")
        self.assertEqual(decide(planned(departure=NOW - timedelta(hours=1)), NOW, True, True).reason, "no_plan")
        self.assertEqual(decide(None, NOW, True, True).action, "none")

    def test_plug_state_unknown_still_decides(self):
        self.assertEqual(decide(planned(), NOW, None, True).action, "pause")

    def test_when_the_target_cannot_be_reached_it_charges_at_once(self):
        p = planned(need_kwh=200.0)
        d = decide(p, NOW, True, True)
        self.assertEqual((d.action, d.reason), ("charge", "cannot_reach_target"))


class ShadowLogTest(unittest.TestCase):
    def test_journal_notes_only_changes(self):
        log = ShadowLog()
        a = Decision("pause", "waiting_for_window")
        self.assertTrue(log.update(NOW, a, False, 100.0))
        log.update(NOW + timedelta(minutes=5), a, False, 100.0)
        log.update(NOW + timedelta(minutes=10), Decision("charge", "in_window", 2.0), True, 100.0)
        self.assertEqual([j["action"] for j in log.journal], ["pause", "charge"])

    def test_time_and_energy_go_to_the_previous_state(self):
        log = ShadowLog()
        log.update(NOW, Decision("pause", "waiting_for_window"), True, 100.0)               # would pause, but charging
        log.update(NOW + timedelta(minutes=10), Decision("pause", "waiting_for_window"), True, 101.5)
        s = log.summary(NOW + timedelta(minutes=10))
        self.assertAlmostEqual(s["pause_but_charging_h"], 0.2, places=1)
        self.assertEqual(s["kwh_in_pause"], 1.5)
        self.assertEqual(s["agree_pct"], 0)

    def test_agreement(self):
        log = ShadowLog()
        t = NOW
        log.update(t, Decision("pause", "waiting_for_window"), False, 0.0)
        t += timedelta(minutes=15)
        log.update(t, Decision("charge", "in_window", 3.0), True, 0.0)                      # 15 min pause and idle: agree
        t += timedelta(minutes=15)
        log.update(t, Decision("charge", "in_window", 3.0), True, 1.0)                      # 15 min charge and charging: agree
        t += timedelta(minutes=15)
        log.update(t, Decision("charge", "in_window", 3.0), False, 1.0)                     # 15 min charge, charging: agree
        s = log.summary(t)
        self.assertEqual(s["agree_pct"], 100)
        self.assertEqual(s["kwh_in_charge"], 1.0)

    def test_a_long_gap_is_not_attributed(self):
        log = ShadowLog()
        log.update(NOW, Decision("pause", "waiting_for_window"), True, 0.0)
        log.update(NOW + timedelta(hours=3), Decision("pause", "waiting_for_window"), True, 9.0)     # restart in between
        s = log.summary(NOW + timedelta(hours=3))
        self.assertEqual(s["pause_but_charging_h"], 0.0)
        self.assertEqual(s["kwh_in_pause"], 0.0)

    def test_no_decision_is_not_compared(self):
        log = ShadowLog()
        log.update(NOW, Decision("none", "not_plugged"), True, 0.0)
        log.update(NOW + timedelta(minutes=10), Decision("none", "not_plugged"), True, 5.0)
        s = log.summary(NOW + timedelta(minutes=10))
        self.assertIsNone(s["agree_pct"])
        self.assertEqual(s["kwh_in_pause"] + s["kwh_in_charge"], 0.0)

    def test_unknown_charging_state_still_counts_energy(self):
        log = ShadowLog()
        log.update(NOW, Decision("pause", "waiting_for_window"), None, 10.0)
        log.update(NOW + timedelta(minutes=10), Decision("pause", "waiting_for_window"), None, 12.0)
        s = log.summary(NOW + timedelta(minutes=10))
        self.assertEqual(s["kwh_in_pause"], 2.0)
        self.assertIsNone(s["agree_pct"])

    def test_counter_going_back_is_ignored(self):
        log = ShadowLog()
        log.update(NOW, Decision("charge", "in_window", 2.0), True, 50.0)
        log.update(NOW + timedelta(minutes=5), Decision("charge", "in_window", 2.0), True, 3.0)     # reset of the counter
        self.assertEqual(log.summary(NOW + timedelta(minutes=5))["kwh_in_charge"], 0.0)

    def test_saved_and_restored(self):
        log = ShadowLog()
        log.update(NOW, Decision("pause", "waiting_for_window"), True, 0.0)
        log.update(NOW + timedelta(minutes=5), Decision("pause", "waiting_for_window"), True, 1.0)
        again = ShadowLog(log.to_dict())
        self.assertEqual(again.summary(NOW + timedelta(minutes=5)), log.summary(NOW + timedelta(minutes=5)))
        self.assertEqual(again.journal, log.journal)
        ShadowLog({"journal": "kaputt", "days": {"x": 1}})       # damaged data must not break the start

    def test_energy_delivered_although_nothing_was_needed_is_recorded(self):
        log = ShadowLog()
        none = Decision("none", "not_needed")
        log.update(NOW, none, True, 100.0)                                          # plugged in, charging with the sun, nothing needed
        log.update(NOW + timedelta(minutes=10), none, True, 101.8)
        s = log.summary(NOW + timedelta(minutes=10))
        self.assertEqual(s["kwh_needless"], 1.8)
        self.assertAlmostEqual(s["needless_h"], 0.2, places=1)
        self.assertIsNone(s["agree_pct"])                                           # it does not count as agreement or disagreement
        self.assertEqual(s["kwh_in_pause"] + s["kwh_in_charge"], 0.0)

    def test_other_no_decisions_are_still_not_compared(self):
        log = ShadowLog()
        for reason in ("not_plugged", "unknown_soc", "no_plan"):
            log.update(NOW, Decision("none", reason), True, 10.0)
            log.update(NOW + timedelta(minutes=10), Decision("none", reason), True, 12.0)
        self.assertEqual(log.summary(NOW + timedelta(minutes=10))["kwh_needless"], 0.0)

    def test_old_saved_data_without_the_new_keys_still_loads(self):
        old = {"journal": [], "days": {NOW.date().isoformat(): {"charge_charging": 60.0, "pause_idle": 30.0, "kwh_charge": 1.0}}}
        s = ShadowLog(old).summary(NOW)
        self.assertEqual(s["kwh_needless"], 0.0)
        self.assertEqual(s["agree_pct"], 100)
    def test_old_days_are_dropped(self):
        log = ShadowLog()
        t = NOW
        for i in range(70):
            t = NOW + timedelta(days=i)
            log.update(t, Decision("pause", "waiting_for_window"), True, 0.0)
            log.update(t + timedelta(minutes=5), Decision("pause", "waiting_for_window"), True, 0.0)
        self.assertLessEqual(len(log.days), 60)


if __name__ == "__main__":
    unittest.main()
