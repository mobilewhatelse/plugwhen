"""House-specific numbers learned from the own data instead of set (pure Python, no Home Assistant imports).

Every number here has a default that works everywhere and an override in the settings. What is learned:

* `quarter_add_kw`: how far the highest quarter hour of an hour lies above the hour's mean. From the 5-minute means of the
  grid import (short-term statistics, about 10 days). Used by the potential calculator instead of a fixed 0.7 kW.
* `base_load_kw`: the night-time base load of the house (median of the hours 1 to 5). Taken off the solar forecast instead of a
  fixed 0.5 kW: what the house itself uses before the car can have the surplus.
* `efficiency`: the share of the wallbox energy that reaches the battery, from days with home charging only (state of charge
  rise times capacity divided by the wallbox energy).
* `SolarAccuracy`: how good the solar forecast is in this place: per day the predicted energy against the measured one, the
  median ratio of the last days becomes a factor on the forecast (0.5 to 1.5).

Nothing is invented: with too few data each function returns None and the caller keeps its default.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from statistics import median
from typing import Any

try:  # inside Home Assistant the module lives in a package, the tests import it flat
    from .learning import DayRecord, quantile_high
except ImportError:  # pragma: no cover
    from learning import DayRecord, quantile_high

MIN_HOURS_QUARTER = 48           # hours with complete 5-minute data before the quarter add is trusted
MIN_DAYS_BASE = 5
MIN_DAYS_EFFICIENCY = 5
MIN_DAYS_SOLAR = 5
SOLAR_KEEP = 30
BASE_HOURS = (1, 2, 3, 4, 5)     # local hours used for the night-time base load
MIN_HOME_KWH = 3.0               # a day with less home charging says little about the losses


def quarter_add_from_5min(series: list[tuple[datetime, float | None]]) -> float | None:
    """Highest quarter-hour mean minus the hour mean, 80th percentile over the hours (kW). Values in kW; 9 or more of the 12
    five-minute means of an hour are needed."""
    by_hour: dict[datetime, list[float]] = defaultdict(list)
    for t, kw in series:
        if kw is None:
            continue
        by_hour[t.replace(minute=0, second=0, microsecond=0)].append(max(0.0, float(kw)))
    adds = []
    for vals in by_hour.values():
        if len(vals) < 9:
            continue
        hour_mean = sum(vals) / len(vals)
        quarters = [sum(vals[i:i + 3]) / len(vals[i:i + 3]) for i in range(0, len(vals), 3) if vals[i:i + 3]]
        adds.append(max(quarters) - hour_mean)
    if len(adds) < MIN_HOURS_QUARTER:
        return None
    return round(min(3.0, max(0.0, quantile_high(adds))), 2)


def base_load_from_hourly(hourly_kwh: dict[datetime, float]) -> float | None:
    """Median import of the night hours (kWh per hour = kW), the house's base load."""
    per_day: dict[date, list[float]] = defaultdict(list)
    for t, kwh in hourly_kwh.items():
        if t.hour in BASE_HOURS and kwh is not None and kwh >= 0:
            per_day[t.date()].append(float(kwh))
    days = [median(v) for v in per_day.values() if len(v) >= 3]
    if len(days) < MIN_DAYS_BASE:
        return None
    return round(min(3.0, max(0.1, median(days))), 2)


def efficiency_from_records(records: list[DayRecord]) -> float | None:
    """Share of the wallbox energy that reached the battery: days with at least `MIN_HOME_KWH` at home and a known rise of the
    state of charge. Ratios above 1.02 mean charging elsewhere on that day and are left out."""
    ratios = []
    for r in records:
        if r.home_kwh is None or r.charged_kwh is None or r.home_kwh < MIN_HOME_KWH:
            continue
        ratio = r.charged_kwh / r.home_kwh
        if 0.6 <= ratio <= 1.02:
            ratios.append(ratio)
    if len(ratios) < MIN_DAYS_EFFICIENCY:
        return None
    return round(min(0.98, max(0.75, median(ratios))), 3)


class SolarAccuracy:
    """Predicted against measured solar energy per day; the factor scales the forecast."""

    def __init__(self, data: dict[str, Any] | None = None) -> None:
        d = data if isinstance(data, dict) else {}
        self.days: dict[str, list[float]] = {}
        days = d.get("days") if isinstance(d.get("days"), dict) else {}
        for k, v in days.items():
            try:
                self.days[str(k)] = [float(v[0]), float(v[1])]
            except (TypeError, ValueError, IndexError):
                continue
        self.pending: dict[str, float] = {}
        pending = d.get("pending") if isinstance(d.get("pending"), dict) else {}
        for k, v in pending.items():
            try:
                self.pending[str(k)] = float(v)
            except (TypeError, ValueError):
                continue

    def to_dict(self) -> dict[str, Any]:
        return {"days": self.days, "pending": self.pending}

    def predict(self, day: date, kwh: float) -> None:
        """Remember what the forecast says for `day` (the last value before the day is used)."""
        self.pending[day.isoformat()] = round(float(kwh), 2)

    def measured(self, day: date, kwh: float) -> bool:
        """The measured energy of a past day; pairs it with the prediction. True if a pair was added."""
        key = day.isoformat()
        pred = self.pending.pop(key, None)
        if pred is None:
            return False
        self.days[key] = [pred, round(float(kwh), 2)]
        for old in sorted(self.days)[:-SOLAR_KEEP]:
            del self.days[old]
        return True

    def factor(self) -> float | None:
        ratios = [m / p for p, m in self.days.values() if p >= 0.5]
        if len(ratios) < MIN_DAYS_SOLAR:
            return None
        return round(min(1.5, max(0.5, median(ratios))), 2)

    def summary(self) -> dict[str, Any]:
        return {"days": len(self.days), "factor": self.factor(),
                "last": [{"day": k, "predicted_kwh": v[0], "measured_kwh": v[1]} for k, v in sorted(self.days.items())[-7:]]}
