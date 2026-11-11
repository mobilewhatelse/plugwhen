"""Consumption per km: learned from the history and depending on the outdoor temperature (only if there is one)."""

from __future__ import annotations

import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

from history import records_from_hourly  # noqa: E402
from learning import DayRecord, MobilityModel, cold_factor  # noqa: E402

TZ = timezone(timedelta(hours=1))
D0 = datetime(2027, 1, 4, 0, 0, tzinfo=TZ)  # Monday 00:00


def day_series(days: int, km: float, soc_fall: float, temp: float | None = None):
    """Odometer, state of charge and temperature per hour: one trip of `km` at 07:00 that costs `soc_fall` percent,
    charged back at 22:00."""
    odo, soc, tmp, o = [], [], [], 10000.0
    for d in range(days):
        s = 80.0
        for h in range(24):
            t = D0 + timedelta(days=d, hours=h)
            if h == 7:
                o += km
                s -= soc_fall
            if h == 22:
                s = 80.0
            odo.append((t, o))
            soc.append((t, s))
            if temp is not None:
                tmp.append((t, temp))
    return odo, soc, tmp or None


class HistoryConsumptionTest(unittest.TestCase):
    def test_consumption_follows_from_the_fall_of_the_state_of_charge(self):
        odo, soc, _ = day_series(3, 50.0, 15.0)
        recs = records_from_hourly(odo, soc, None, 60.0)
        # 15 % of 60 kWh = 9 kWh on 50 km
        self.assertAlmostEqual(recs[-1].consumption, 0.18, places=3)
        self.assertIsNone(recs[-1].temp_c)

    def test_short_days_give_no_consumption(self):
        odo, soc, _ = day_series(3, 12.0, 4.0)
        self.assertIsNone(records_from_hourly(odo, soc, None, 60.0)[-1].consumption)

    def test_without_capacity_no_consumption(self):
        odo, soc, _ = day_series(3, 50.0, 15.0)
        self.assertIsNone(records_from_hourly(odo, soc, None, None)[-1].consumption)

    def test_the_day_gets_the_mean_temperature(self):
        odo, soc, tmp = day_series(3, 50.0, 15.0, temp=-3.0)
        self.assertEqual(records_from_hourly(odo, soc, None, 60.0, temp_c=tmp)[-1].temp_c, -3.0)


def model_with(pairs: list[tuple[float, float | None]]) -> MobilityModel:
    m = MobilityModel()
    for i, (c, t) in enumerate(pairs):
        m.add_day(DayRecord(date(2026, 9, 1) + timedelta(days=i), km=50.0, consumption=c, temp_c=t))
    return m


class ConsumptionAtTest(unittest.TestCase):
    def test_without_temperature_everything_stays_as_before(self):
        m = model_with([(0.18, None), (0.20, None), (0.19, None)])
        self.assertEqual(m.consumption_at(None, 0.25), (0.19, "learned"))
        self.assertEqual(m.consumption_at(-5.0, 0.25), (0.19, "learned"))   # no temperatures learned: no correction

    def test_without_anything_learned_the_typed_in_value(self):
        self.assertEqual(MobilityModel().consumption_at(None, 0.22), (0.22, "config"))

    def test_typed_in_value_gets_more_in_the_cold_and_never_less_in_the_warm(self):
        m = MobilityModel()
        cold, src = m.consumption_at(-5.0, 0.20)
        self.assertEqual(src, "rule_config")
        self.assertAlmostEqual(cold, round(0.20 * cold_factor(-5.0) / cold_factor(15.0), 3))
        self.assertGreater(cold, 0.20)
        self.assertEqual(m.consumption_at(25.0, 0.20)[0], 0.20)

    def test_a_cold_morning_after_a_mild_week_needs_more(self):
        m = model_with([(0.18, 12.0), (0.19, 11.0), (0.18, 13.0)])
        value, src = m.consumption_at(-4.0, 0.25)
        self.assertEqual(src, "rule")
        self.assertGreater(value, 0.18 * 1.1)

    def test_own_curve_once_enough_days_over_enough_temperatures(self):
        pairs = [(0.16 + 0.004 * (20 - t), float(t)) for t in (20, 16, 12, 8, 4, 0, 18, 10)]
        value, src = model_with(pairs).consumption_at(-2.0, 0.25)
        self.assertEqual(src, "curve")
        self.assertAlmostEqual(value, 0.16 + 0.004 * 22, places=2)

    def test_colder_never_costs_less_even_with_odd_days(self):
        pairs = [(0.24 - 0.004 * (20 - t), float(t)) for t in (20, 16, 12, 8, 4, 0, 18, 10)]   # learned: cold = less
        m = model_with(pairs)
        self.assertGreaterEqual(m.consumption_at(-5.0, 0.25)[0], m.consumption_at(20.0, 0.25)[0])

    def test_the_curve_does_not_run_away_far_outside_what_was_learned(self):
        pairs = [(0.16 + 0.004 * (20 - t), float(t)) for t in (20, 18, 16, 14, 12, 10, 15, 11)]
        m = model_with(pairs)
        self.assertEqual(m.consumption_at(-30.0, 0.25), m.consumption_at(5.0, 0.25))   # 10 deg C - 5 K is the limit

    def test_the_temperature_survives_saving(self):
        m = model_with([(0.18, 2.0), (0.19, 3.0), (0.2, 1.0)])
        again = MobilityModel.from_dict(m.to_dict())
        self.assertEqual(again.consumption_temp, m.consumption_temp)

    def test_old_saved_rows_without_temperature_still_load(self):
        m = MobilityModel.from_dict({"days": {"0": [["2026-11-02", 40.0, 7.0, None, None, 0.2, None]]}})
        self.assertEqual(m.total_days, 1)
        self.assertEqual(m.consumption_temp, [])


if __name__ == "__main__":
    unittest.main()
