"""Tests for the quarter-hour add of the house (by load level, house only)."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

from calibrate import QuarterAddModel, quarter_add_samples  # noqa: E402
from potential import calculate  # noqa: E402

TZ = timezone(timedelta(hours=1))
T0 = datetime(2027, 1, 4, 0, 0, tzinfo=TZ)


def hours(n, kw_of_hour, spike_of_hour=lambda h: 0.0):
    """5-minute means for n hours: the first quarter of an hour is `spike` kW above the rest."""
    out = []
    for h in range(n):
        for i in range(12):
            out.append((T0 + timedelta(hours=h, minutes=5 * i), kw_of_hour(h) + (spike_of_hour(h) if i < 3 else 0.0)))
    return out


class SamplesTest(unittest.TestCase):
    def test_every_hour_is_a_sample(self):
        s = quarter_add_samples(hours(30, lambda h: 0.5))
        self.assertEqual(len(s), 30)
        self.assertTrue(all(abs(x[2]) < 1e-9 for x in s))

    def test_hours_with_wallbox_charging_are_left_out(self):
        wb = {T0 + timedelta(hours=h): (2.0 if 10 <= h < 14 else 0.0) for h in range(30)}
        s = quarter_add_samples(hours(30, lambda h: 0.5), wb)
        self.assertEqual(len(s), 26)
        self.assertNotIn((T0 + timedelta(hours=11)).isoformat(), [x[0] for x in s])

    def test_an_hour_the_wallbox_does_not_know_is_left_out_when_the_wallbox_is_known(self):
        wb = {T0 + timedelta(hours=h): 0.0 for h in range(10)}
        self.assertEqual(len(quarter_add_samples(hours(30, lambda h: 0.5), wb)), 10)

    def test_incomplete_hours_are_left_out(self):
        s = hours(5, lambda h: 1.0)[:-4]
        self.assertEqual(len(quarter_add_samples(s)), 4)


class ModelTest(unittest.TestCase):
    def model(self):
        m = QuarterAddModel()
        quiet = quarter_add_samples(hours(60, lambda h: 0.3, lambda h: 0.4))              # add about 0.3 kW at 0.4..0.7 kW
        loud = quarter_add_samples([(t + timedelta(days=5), kw) for t, kw in hours(30, lambda h: 4.0, lambda h: 2.0)])   # high hours
        m.merge(quiet + loud, house_only=True)
        return m

    def test_the_add_depends_on_the_load_level(self):
        m = self.model()
        low, high = m.value(0.5), m.value(4.0)
        self.assertIsNotNone(low)
        self.assertIsNotNone(high)
        self.assertGreater(high, low + 0.5)

    def test_a_level_without_enough_hours_has_no_value(self):
        m = self.model()
        self.assertIsNone(m.value(1.5))                       # no medium hours at all: the default applies there

    def test_the_summary_says_what_it_knows(self):
        s = self.model().summary()
        self.assertTrue(s["house_only"])
        self.assertEqual([x["level"] for x in s["levels"]], ["quiet", "medium", "high"])
        self.assertEqual(s["levels"][1]["add_kw"], None)

    def test_restore_and_damaged_data(self):
        m = self.model()
        again = QuarterAddModel(m.to_dict())
        self.assertEqual(again.value(4.0), m.value(4.0))
        QuarterAddModel({"samples": "kaputt"})
        QuarterAddModel({"samples": {"x": "y"}})

    def test_a_change_of_the_kind_of_measurement_starts_again(self):
        m = self.model()
        m.merge(quarter_add_samples(hours(20, lambda h: 0.5)), house_only=False)
        self.assertEqual(len(m.samples), 20)
        self.assertFalse(m.house_only)

    def test_old_hours_are_dropped(self):
        m = QuarterAddModel()
        m.merge([((T0 + timedelta(hours=h)).isoformat(), 0.5, 0.1) for h in range(2600)], house_only=True)
        self.assertEqual(len(m.samples), 2500)


class PotentialUsesTheFunction(unittest.TestCase):
    def test_a_function_of_the_house_load_is_accepted(self):
        from test_potential import AT, LATE, household
        grid, car, trips = household(days=21, charge_hours=(4, 5), kwh_per_hour=LATE)
        flat = calculate(grid, car, trips, prices=AT, quarter_add_kw=0.7)
        fn = calculate(grid, car, trips, prices=AT, quarter_add_kw=lambda house: 0.7)
        self.assertEqual(flat["peak_as_is_kw"], fn["peak_as_is_kw"])
        bigger = calculate(grid, car, trips, prices=AT, quarter_add_kw=lambda house: 0.7 + house)
        self.assertGreaterEqual(bigger["peak_as_is_kw"], flat["peak_as_is_kw"])


if __name__ == "__main__":
    unittest.main()
