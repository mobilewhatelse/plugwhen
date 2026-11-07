"""Daily records from hourly statistics (pure Python, no Home Assistant imports).

The adapter reads the hourly long-term statistics of the odometer, the state of charge and (optionally) the energy counter
of the wallbox and hands them over as lists of `(local hour start, value)`. This module turns them into one
`learning.DayRecord` per day:

* **km** = odometer at the end of the day minus the odometer at the end of the previous day,
* **first_move_hour** = the first hour of the day in which the odometer rose (a trip started in that hour),
* **home_kwh** = wallbox energy counter difference of the day (None without a counter or before it existed),
* **away_kwh** = energy that raised the state of charge beyond what the wallbox delivered: the sum of the rises of
  the state of charge (steps of at least `MIN_RISE_PCT`) times the capacity, minus the wallbox energy that reached
  the battery. The car sees charging the wallbox does not, so this is an estimate. None if the home energy is unknown.

Nothing is invented: a day without an odometer value has no km (None), a day before the first reading is skipped.
"""

from __future__ import annotations

from datetime import date, datetime

try:  # inside Home Assistant the module lives in a package, the tests import it flat
    from .learning import DayRecord
except ImportError:  # pragma: no cover
    from learning import DayRecord

MIN_RISE_PCT = 1.5          # smaller rises of the state of charge are noise
MAX_HOURLY_KM = 400.0       # an hourly odometer jump larger than this is a glitch, no trip start
MIN_STEP_KM = 0.5           # an hour with fewer kilometres is not a trip start
DEFAULT_EFFICIENCY = 0.9    # share of the wallbox energy that reaches the battery

Series = list[tuple[datetime, float | None]]


def records_from_hourly(
    odometer_km: Series,
    soc_pct: Series | None = None,
    wallbox_kwh: Series | None = None,
    capacity_kwh: float | None = None,
    efficiency: float = DEFAULT_EFFICIENCY,
) -> list[DayRecord]:
    """One record per local day covered by the odometer series. Series must be sorted by time."""
    days: dict[date, dict] = {}
    prev_o: float | None = None
    for t, o in odometer_km:
        rec = days.setdefault(t.date(), {"last_o": None, "first_move": None, "rise": 0.0, "prev_soc": None, "wb_last": None})
        if o is None:
            continue
        if prev_o is not None and MIN_STEP_KM < o - prev_o < MAX_HOURLY_KM and rec["first_move"] is None:
            rec["first_move"] = float(t.hour)
        rec["last_o"] = o
        prev_o = o
    soc_prev: float | None = None
    for t, s in soc_pct or []:
        rec = days.get(t.date())
        if rec is None or s is None:
            continue
        if soc_prev is not None and s - soc_prev >= MIN_RISE_PCT:
            rec["rise"] += s - soc_prev
        soc_prev = s
    for t, w in wallbox_kwh or []:
        rec = days.get(t.date())
        if rec is not None and w is not None:
            rec["wb_last"] = w

    out: list[DayRecord] = []
    prev_last: float | None = None
    prev_wb: float | None = None
    for d in sorted(days):
        r = days[d]
        km = None
        if r["last_o"] is not None:
            if prev_last is not None:
                km = r["last_o"] - prev_last
            prev_last = r["last_o"]
        elif prev_last is None:
            continue  # nothing known yet
        home = away = charged = None
        if r["wb_last"] is not None:
            if prev_wb is not None:
                home = max(0.0, r["wb_last"] - prev_wb)
            prev_wb = r["wb_last"]
        if capacity_kwh:
            charged = round(r["rise"] / 100.0 * capacity_kwh, 2)
        if home is not None and capacity_kwh:
            away = max(0.0, r["rise"] / 100.0 * capacity_kwh - home * efficiency)
        out.append(DayRecord(d, km=km, first_move_hour=r["first_move"] if km is not None and km >= 2.0 else None,
                             home_kwh=home, away_kwh=away, charged_kwh=charged))
    return [r for r in out if r.km is not None or r.home_kwh is not None]


def to_km(value: float | None, unit: str | None) -> float | None:
    """Odometer value in kilometres (miles are converted)."""
    if value is None:
        return None
    u = (unit or "km").strip().lower()
    return value * 1.609344 if u in ("mi", "mile", "miles") else value


def to_kwh(value: float | None, unit: str | None) -> float | None:
    if value is None:
        return None
    return value * {"wh": 0.001, "kwh": 1.0, "mwh": 1000.0}.get((unit or "kWh").strip().lower(), 1.0)
