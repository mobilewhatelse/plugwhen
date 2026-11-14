"""Tests for the daily records derived from hourly statistics."""

from __future__ import annotations

import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"))

from history import records_from_hourly, to_kwh, to_km  # noqa: E402

TZ = timezone(timedelta(hours=1))
D0 = datetime(2027, 1, 4, 0, 0, tzinfo=TZ)  # Monday 00:00


def hourly(values_by_hour: dict[int, float | None], day_offset=0):
    return [(D0 + timedelta(days=day_offset, hours=h), v) for h, v in sorted(values_by_hour.items())]


def flat_odometer(days: int, start=10000.0, trips: dict[int, tuple[int, float]] | None = None):
    """Odometer per hour; `trips[day] = (hour of the trip, km)`."""
    out, o = [], start
    for d in range(days):
        for h in range(24):
            if trips and d in trips and trips[d][0] == h:
                o += trips[d][1]
            out.append((D0 + timedelta(days=d, hours=h), o))
    return out


class MidnightTest(unittest.TestCase):
    def test_trip_over_midnight_is_not_a_departure_of_the_next_day(self):
        o, series = 10000.0, []
        for d in range(2):
            for h in range(24):
                if (d, h) in ((0, 23), (1, 0)):   # Saturday night home trip: 23:00 and 00:00
                    o += 30.0
                if (d, h) == (1, 13):             # the real Sunday trip
                    o += 20.0
                series.append((D0 + timedelta(days=d, hours=h), o))
        by = {r.day: r for r in records_from_hourly(series)}
        self.assertEqual(by[date(2027, 1, 5)].first_move_hour, 13.0)   # not 0
        self.assertEqual(by[date(2027, 1, 5)].km, 50.0)                # the kilometres still count for the day

    def test_trip_starting_after_midnight_counts(self):
        o, series = 10000.0, []
        for d in range(2):
            for h in range(24):
                if (d, h) == (1, 1):                # nothing at 23:00, a trip at 01:00 is a real departure
                    o += 30.0
                series.append((D0 + timedelta(days=d, hours=h), o))
        by = {r.day: r for r in records_from_hourly(series)}
        self.assertEqual(by[date(2027, 1, 5)].first_move_hour, 1.0)

    def test_running_trip_without_a_later_one_gives_no_departure(self):
        o, series = 10000.0, []
        for d in range(2):
            for h in range(24):
                if (d, h) in ((0, 23), (1, 0), (1, 1)):
                    o += 30.0
                series.append((D0 + timedelta(days=d, hours=h), o))
        by = {r.day: r for r in records_from_hourly(series)}
        self.assertIsNone(by[date(2027, 1, 5)].first_move_hour)


class KmTest(unittest.TestCase):
    def test_km_per_day_and_first_trip_hour(self):
        recs = records_from_hourly(flat_odometer(4, trips={1: (7, 40.0), 2: (13, 5.0)}))
        by = {r.day: r for r in recs}
        self.assertEqual(by[date(2027, 1, 5)].km, 40.0)
        self.assertEqual(by[date(2027, 1, 5)].first_move_hour, 7.0)
        self.assertEqual(by[date(2027, 1, 6)].km, 5.0)
        self.assertEqual(by[date(2027, 1, 6)].first_move_hour, 13.0)
        self.assertEqual(by[date(2027, 1, 7)].km, 0.0)
        self.assertIsNone(by[date(2027, 1, 7)].first_move_hour)

    def test_first_day_has_no_km_and_is_dropped(self):
        recs = records_from_hourly(flat_odometer(3))
        self.assertEqual([r.day for r in recs], [date(2027, 1, 5), date(2027, 1, 6)])

    def test_glitch_is_no_trip_start(self):
        o = flat_odometer(3, trips={1: (3, 900.0), 2: (8, 30.0)})
        by = {r.day: r for r in records_from_hourly(o)}
        self.assertIsNone(by[date(2027, 1, 5)].first_move_hour)     # 900 km in one hour: ignored as a start
        self.assertEqual(by[date(2027, 1, 5)].clean_km(), 900.0)     # the learning refuses it as a daily value anyway
        self.assertEqual(by[date(2027, 1, 6)].first_move_hour, 8.0)

    def test_gaps_in_the_series_keep_the_last_value(self):
        o = flat_odometer(3, trips={1: (7, 40.0)})
        o = [(t, v) for t, v in o if not (t.date() == date(2027, 1, 6))]  # a whole day without statistics
        recs = records_from_hourly(o)
        self.assertEqual({r.day: r.km for r in recs}, {date(2027, 1, 5): 40.0})


class ChargingTest(unittest.TestCase):
    def setUp(self):
        self.odo = flat_odometer(4, trips={1: (7, 40.0), 2: (7, 40.0)})

    def wallbox(self, kwh_by_day):
        """Counter: value at the end of each day (every hour of the day carries the end value, enough for the test)."""
        out, c = [], 100.0
        for d in range(4):
            c += kwh_by_day.get(d, 0.0)
            out += [(D0 + timedelta(days=d, hours=h), c) for h in range(24)]
        return out

    def soc(self, rises_by_day):
        out, s = [], 50.0
        for d in range(4):
            for h in range(24):
                if h == 2:
                    s += rises_by_day.get(d, 0.0)
                out.append((D0 + timedelta(days=d, hours=h), s))
        return out

    def test_home_energy_is_the_counter_difference(self):
        recs = records_from_hourly(self.odo, wallbox_kwh=self.wallbox({1: 12.0, 2: 5.0}))
        by = {r.day: r for r in recs}
        self.assertEqual(by[date(2027, 1, 5)].home_kwh, 12.0)
        self.assertEqual(by[date(2027, 1, 6)].home_kwh, 5.0)

    def test_away_energy_is_what_the_wallbox_did_not_deliver(self):
        # state of charge rises by 30 % of 60 kWh = 18 kWh; the wallbox gave 10 kWh of which 9 reached the battery
        recs = records_from_hourly(self.odo, soc_pct=self.soc({1: 30.0}), wallbox_kwh=self.wallbox({1: 10.0}), capacity_kwh=60.0)
        r = {x.day: x for x in recs}[date(2027, 1, 5)]
        self.assertEqual(r.home_kwh, 10.0)
        self.assertAlmostEqual(r.away_kwh, 9.0, places=2)

    def test_pure_home_charging_has_no_away_energy(self):
        recs = records_from_hourly(self.odo, soc_pct=self.soc({1: 15.0}), wallbox_kwh=self.wallbox({1: 10.0}), capacity_kwh=60.0)
        self.assertEqual({x.day: x for x in recs}[date(2027, 1, 5)].away_kwh, 0.0)

    def test_small_rises_are_noise(self):
        recs = records_from_hourly(self.odo, soc_pct=self.soc({1: 1.0}), wallbox_kwh=self.wallbox({1: 0.0}), capacity_kwh=60.0)
        self.assertEqual({x.day: x for x in recs}[date(2027, 1, 5)].away_kwh, 0.0)

    def test_without_wallbox_counter_the_place_is_unknown(self):
        recs = records_from_hourly(self.odo, soc_pct=self.soc({1: 30.0}), capacity_kwh=60.0)
        r = {x.day: x for x in recs}[date(2027, 1, 5)]
        self.assertIsNone(r.home_kwh)
        self.assertIsNone(r.away_kwh)

    def test_without_capacity_away_is_unknown(self):
        recs = records_from_hourly(self.odo, soc_pct=self.soc({1: 30.0}), wallbox_kwh=self.wallbox({1: 10.0}))
        self.assertIsNone({x.day: x for x in recs}[date(2027, 1, 5)].away_kwh)


class UnitTest(unittest.TestCase):
    def test_miles_and_energy_units(self):
        self.assertAlmostEqual(to_km(100.0, "mi"), 160.9344)
        self.assertEqual(to_km(100.0, "km"), 100.0)
        self.assertIsNone(to_km(None, "km"))
        self.assertEqual(to_kwh(5000.0, "Wh"), 5.0)
        self.assertEqual(to_kwh(2.0, "MWh"), 2000.0)
        self.assertEqual(to_kwh(3.0, None), 3.0)


if __name__ == "__main__":
    unittest.main()


class ParkedDropTest(unittest.TestCase):
    def soc(self, per_day):
        """State of charge per hour: each day falls evenly from its start to its end value."""
        out = []
        for d, (a, b) in enumerate(per_day):
            for h in range(24):
                out.append((D0 + timedelta(days=d, hours=h), a + (b - a) * h / 23))
        return out

    def test_whole_day_parked_gives_the_fall(self):
        recs = records_from_hourly(flat_odometer(3), self.soc([(80, 80), (80, 79.2), (79.2, 78.0)]), capacity_kwh=60)
        by = {r.day: r.parked_drop_pct for r in recs}
        self.assertNotIn(date(2027, 1, 4), by)             # no day before: no record at all
        self.assertEqual(by[date(2027, 1, 5)], 1.0)        # 0.8 rounded to 0.5 steps
        self.assertEqual(by[date(2027, 1, 6)], 1.0)

    def test_not_on_days_with_a_trip_or_charging(self):
        recs = records_from_hourly(flat_odometer(3, trips={1: (8, 20.0)}), self.soc([(80, 80), (80, 75), (75, 90)]),
                                   capacity_kwh=60)
        by = {r.day: r.parked_drop_pct for r in recs}
        self.assertIsNone(by[date(2027, 1, 5)])            # driven
        self.assertIsNone(by[date(2027, 1, 6)])            # charged

    def test_a_large_fall_is_not_taken(self):
        recs = records_from_hourly(flat_odometer(2), self.soc([(80, 80), (80, 60)]), capacity_kwh=60)
        self.assertIsNone(recs[-1].parked_drop_pct)
