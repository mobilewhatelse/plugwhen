"""House-specific numbers learned from the own data instead of set (pure Python, no Home Assistant imports).

Every number here has a default that works everywhere and an override in the settings. What is learned:

* `QuarterAddModel`: how far the highest quarter hour of an hour lies above the hour's mean, **for the house alone** (hours in which the
  wallbox delivered no energy) and **by load level** (quiet, medium, high hours). A single value is wrong: quiet hours need about 0.1 kW,
  loaded hours several. The hours are collected for good (the recorder keeps 5-minute values for about ten days).
* (older) `quarter_add_kw`: how far the highest quarter hour of an hour lies above the hour's mean. From the 5-minute means of the
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

ADD_BINS = (0.8, 2.5)              # hourly house mean (kW): quiet below the first, medium below the second, else high
MIN_BIN_HOURS = 12               # hours a load level needs before its value is trusted (else the default applies there)
HOUSE_ONLY_MAX_KWH = 0.05        # an hour with at most this wallbox energy counts as house only
MAX_ADD_SAMPLES = 2500           # about 100 days of hours
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


def quarter_add_samples(series: list[tuple[datetime, float | None]], wallbox_hourly: dict[datetime, float] | None = None) -> list[tuple[str, float, float]]:
    """Per full hour `(hour, mean kW, add kW)` from 5-minute means (kW). With `wallbox_hourly` (kWh per local hour start) only hours in
    which the wallbox delivered next to nothing count (house only); an hour the wallbox does not know is left out. Without it
    every hour counts (the add then includes the car; the model says so)."""
    by_hour: dict[datetime, list[float]] = defaultdict(list)
    for t, kw in sorted(series, key=lambda x: x[0]):
        if kw is not None:
            by_hour[t.replace(minute=0, second=0, microsecond=0)].append(max(0.0, float(kw)))
    out = []
    for hour, vals in sorted(by_hour.items()):
        if len(vals) < 9:
            continue
        if wallbox_hourly is not None:
            wb = wallbox_hourly.get(hour)
            if wb is None or wb > HOUSE_ONLY_MAX_KWH:
                continue
        mean = sum(vals) / len(vals)
        quarters = [sum(vals[i:i + 3]) / len(vals[i:i + 3]) for i in range(0, len(vals), 3) if vals[i:i + 3]]
        out.append((hour.isoformat(), round(mean, 3), round(max(quarters) - mean, 3)))
    return out


class QuarterAddModel:
    """Collected hours (mean, add) of the house; `value(house_kw)` is the add for that load level or None until the level has enough hours."""

    def __init__(self, data: dict[str, Any] | None = None) -> None:
        d = data if isinstance(data, dict) else {}
        self.samples: dict[str, list[float]] = {}
        raw = d.get("samples") if isinstance(d.get("samples"), dict) else {}
        for k, v in raw.items():
            try:
                self.samples[str(k)] = [float(v[0]), float(v[1])]
            except (TypeError, ValueError, IndexError):
                continue
        self.house_only = bool(d.get("house_only", False))

    def to_dict(self) -> dict[str, Any]:
        return {"samples": self.samples, "house_only": self.house_only}

    def merge(self, samples: list[tuple[str, float, float]], house_only: bool) -> None:
        if self.samples and house_only != self.house_only:
            self.samples = {}                       # the kind of measurement changed (a wallbox energy entity was added): start again
        self.house_only = house_only
        for iso, mean, add in samples:
            self.samples[iso] = [mean, add]
        for old in sorted(self.samples)[:-MAX_ADD_SAMPLES]:
            del self.samples[old]

    @staticmethod
    def _level(mean_kw: float) -> int:
        return 0 if mean_kw < ADD_BINS[0] else 1 if mean_kw < ADD_BINS[1] else 2

    def value(self, house_kw: float) -> float | None:
        level = self._level(house_kw)
        adds = [a for m, a in self.samples.values() if self._level(m) == level]
        if len(adds) < MIN_BIN_HOURS:
            return None
        return round(min(4.0, max(0.0, quantile_high(adds))), 2)

    def summary(self) -> dict[str, Any]:
        names = ("quiet", "medium", "high")
        levels = []
        for i, name in enumerate(names):
            adds = [a for m, a in self.samples.values() if self._level(m) == i]
            levels.append({"level": name, "hours": len(adds), "add_kw": self.value((0.0, ADD_BINS[0], ADD_BINS[1])[i])})
        return {"hours": len(self.samples), "house_only": self.house_only, "levels": levels}
