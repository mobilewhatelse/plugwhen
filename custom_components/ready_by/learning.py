"""Learning how a car is used, per weekday (pure Python, no Home Assistant imports).

Input are *daily records* of one car (what the adapter derives from the long-term statistics of the odometer, the state of
charge and the wallbox energy):

    DayRecord(day, km, first_move_hour, home_kwh, away_kwh, consumption)

Per weekday the model keeps the last `MAX_DAYS` records and answers:

* `km_typical` (median) and `km_high` (80th percentile, nearest rank) of the kilometres,
* `drive_share`: on how many of these days the car was used at all,
* `departure_hour`: the usual hour of the first trip (median over the days it was used),
* `home_charge_share`: of the energy charged on days with charging, the share that came from the home wallbox
  (the car also sees charging the wallbox does not),
* the consumption in kWh per km (median of the last `MAX_CONSUMPTION` values, a default without data).

A plain weekday median covers only about half of the days, so the model gives the **high** value as well; how much
reserve to add on top is decided elsewhere (setting per car). Nothing here controls anything.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from statistics import median
from typing import Any

MAX_DAYS = 8                 # records kept per weekday
MAX_CONSUMPTION = 20         # consumption values kept
MIN_DRIVE_KM = 2.0           # below this the car did not really move
MAX_PLAUSIBLE_KM_DAY = 1500.0  # larger daily values are odometer glitches
MIN_CHARGE_KWH = 1.0         # charging below this does not say where the car is charged
MIN_PLAUSIBLE_CONSUMPTION = 0.08   # kWh per km
MAX_PLAUSIBLE_CONSUMPTION = 0.60
DEFAULT_CONSUMPTION = 0.20   # kWh per km, used until the car's own values are known
MIN_DEPARTURE_DAYS = 2
MIN_CHARGE_DAYS = 2
HIGH_QUANTILE = 0.8


@dataclass(frozen=True)
class DayRecord:
    day: date
    km: float | None = None              # driven that day, None = unknown (no data)
    first_move_hour: float | None = None  # local hour of the first trip, e.g. 7.0 (None if no trip)
    home_kwh: float | None = None        # energy charged at the home wallbox (None = unknown)
    away_kwh: float | None = None        # energy charged elsewhere (None = unknown)
    consumption: float | None = None     # kWh per km on that day, if known

    def clean_km(self) -> float | None:
        if self.km is None or self.km < 0 or self.km > MAX_PLAUSIBLE_KM_DAY:
            return None
        return float(self.km)


@dataclass(frozen=True)
class WeekdayPlan:
    weekday: int                     # 0 = Monday
    samples: int                     # days with a usable kilometre value
    km_typical: float | None
    km_high: float | None
    drive_share: float | None        # 0..1
    departure_hour: float | None
    home_charge_share: float | None  # 0..1, None = not enough days with charging


def quantile_high(values: list[float], q: float = HIGH_QUANTILE) -> float:
    """Nearest-rank quantile; with fewer than four values the largest one (as the load forecast does)."""
    s = sorted(values)
    if len(s) < 4:
        return s[-1]
    return s[max(0, math.ceil(q * len(s)) - 1)]


class MobilityModel:
    def __init__(self) -> None:
        self.days: dict[int, list[DayRecord]] = {}
        self.consumption: list[float] = []

    # ---------- learning ----------

    def add_day(self, rec: DayRecord) -> None:
        """Add or replace the record of a date (the adapter may send a day again once it is complete)."""
        lst = self.days.setdefault(rec.day.weekday(), [])
        lst[:] = [r for r in lst if r.day != rec.day]
        lst.append(rec)
        lst.sort(key=lambda r: r.day)
        del lst[:-MAX_DAYS]
        self._rebuild_consumption()

    def _rebuild_consumption(self) -> None:
        recs = sorted((r for lst in self.days.values() for r in lst), key=lambda r: r.day)
        vals = [r.consumption for r in recs
                if r.consumption is not None and MIN_PLAUSIBLE_CONSUMPTION <= r.consumption <= MAX_PLAUSIBLE_CONSUMPTION]
        self.consumption = vals[-MAX_CONSUMPTION:]

    @property
    def total_days(self) -> int:
        return sum(len(v) for v in self.days.values())

    # ---------- answering ----------

    def plan(self, weekday: int) -> WeekdayPlan:
        recs = self.days.get(weekday, [])
        kms = [k for k in (r.clean_km() for r in recs) if k is not None]
        if not kms:
            return WeekdayPlan(weekday, 0, None, None, None, None, None)
        used = [r for r in recs if (r.clean_km() or 0.0) >= MIN_DRIVE_KM]
        hours = [r.first_move_hour for r in used if r.first_move_hour is not None]
        shares = []
        for r in recs:
            if r.home_kwh is None or r.away_kwh is None:
                continue  # unknown where it was charged: no statement
            total = r.home_kwh + r.away_kwh
            if total >= MIN_CHARGE_KWH:
                shares.append(r.home_kwh / total)
        return WeekdayPlan(
            weekday=weekday,
            samples=len(kms),
            km_typical=round(median(kms), 1),
            km_high=round(quantile_high(kms), 1),
            drive_share=round(sum(1 for k in kms if k >= MIN_DRIVE_KM) / len(kms), 2),
            departure_hour=round(median(hours), 1) if len(hours) >= MIN_DEPARTURE_DAYS else None,
            home_charge_share=round(sum(shares) / len(shares), 2) if len(shares) >= MIN_CHARGE_DAYS else None,
        )

    def week(self) -> list[WeekdayPlan]:
        return [self.plan(wd) for wd in range(7)]

    @property
    def consumption_known(self) -> bool:
        return len(self.consumption) >= 3

    def consumption_kwh_per_km(self) -> float:
        return round(median(self.consumption), 3) if self.consumption_known else DEFAULT_CONSUMPTION

    # ---------- persistence ----------

    def to_dict(self) -> dict[str, Any]:
        return {"days": {str(wd): [[r.day.isoformat(), r.km, r.first_move_hour, r.home_kwh, r.away_kwh, r.consumption]
                                   for r in lst] for wd, lst in self.days.items() if lst}}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MobilityModel:
        m = cls()
        for _, rows in (d.get("days") or {}).items():
            for row in rows:
                try:
                    m.add_day(DayRecord(date.fromisoformat(row[0]), *[None if x is None else float(x) for x in row[1:6]]))
                except (TypeError, ValueError, IndexError):
                    continue
        return m


# ---------- checking the idea against a history ----------

def backtest(records: list[DayRecord], reserve_km: float, warmup_days: int = 28) -> dict[str, float]:
    """Walk through the history day by day: before each day the model only knows the days before it. Returns the share of
    days (after `warmup_days`) whose real kilometres the plan covers:

    * `typical`: the weekday median alone,
    * `high`: the weekday's 80th percentile,
    * `reserve`: the fixed reserve alone (what a car without learning would keep),
    * `reserve_or_high`: the larger of reserve and high.
    """
    model = MobilityModel()
    hits = {"typical": 0, "high": 0, "reserve": 0, "reserve_or_high": 0}
    n = 0
    for i, rec in enumerate(sorted(records, key=lambda r: r.day)):
        km = rec.clean_km()
        if i >= warmup_days and km is not None:
            p = model.plan(rec.day.weekday())
            if p.km_typical is not None and p.km_high is not None:
                n += 1
                hits["typical"] += km <= p.km_typical
                hits["high"] += km <= p.km_high
                hits["reserve"] += km <= reserve_km
                hits["reserve_or_high"] += km <= max(reserve_km, p.km_high)
        model.add_day(rec)
    return {k: round(v / n, 3) if n else 0.0 for k, v in hits.items()} | {"days": float(n)}
