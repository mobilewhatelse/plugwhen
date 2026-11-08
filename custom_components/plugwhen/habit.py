"""When is the car charged? (pure Python, no Home Assistant imports)

From the hourly energy of the wallbox the charging habit per weekday is worked out: how much energy goes into the car on an
average Monday, Tuesday and so on, and when: **during the day** (9 to 17 h, where the sun is), **at night** (20 to 7 h, from the
grid unless there is a home battery) or in between. This is the evidence for where charging could move: a weekday with much
night charging is where a peak and grid energy come from.

Nothing is invented: too few days give `too_little_data`.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

DAY_FROM, DAY_TO = 9, 17          # local hours counted as "during the day"
NIGHT_FROM, NIGHT_TO = 20, 7      # local hours counted as "at night" (from 20:00 until 07:00)
MIN_DAYS = 28
MIN_TOTAL_KWH = 20.0
CHARGE_DAY_KWH = 3.0              # a day with more than this counts as a charging day


def _bucket(hour: int) -> str:
    if DAY_FROM <= hour < DAY_TO:
        return "day"
    if hour >= NIGHT_FROM or hour < NIGHT_TO:
        return "night"
    return "rest"


def charging_habit(hourly_kwh: dict[datetime, float], now: datetime, days: int = 90) -> dict[str, Any]:
    """`hourly_kwh`: wallbox energy per local hour start (kWh)."""
    since = now - timedelta(days=days)
    energy = {wd: {"day": 0.0, "night": 0.0, "rest": 0.0} for wd in range(7)}
    dates: dict[int, set] = {wd: set() for wd in range(7)}
    per_date: dict[int, dict] = {wd: defaultdict(float) for wd in range(7)}
    for t, kwh in hourly_kwh.items():
        if kwh is None or t < since or t > now:
            continue
        wd = t.weekday()
        dates[wd].add(t.date())
        if kwh > 0:
            energy[wd][_bucket(t.hour)] += kwh
            per_date[wd][t.date()] += kwh
    n_days = sum(len(v) for v in dates.values())
    total = sum(sum(e.values()) for e in energy.values())
    result: dict[str, Any] = {"status": "ok", "days": n_days, "total_kwh": round(total, 1), "weekday": []}
    if n_days < MIN_DAYS or total < MIN_TOTAL_KWH:
        result["status"] = "too_little_data"
        return result
    for wd in range(7):
        n = len(dates[wd])
        e = energy[wd]
        result["weekday"].append({
            "weekday": wd, "days": n,
            "kwh_per_day": round(sum(e.values()) / n, 1) if n else 0.0,
            "day_kwh_per_day": round(e["day"] / n, 1) if n else 0.0,
            "night_kwh_per_day": round(e["night"] / n, 1) if n else 0.0,
            "rest_kwh_per_day": round(e["rest"] / n, 1) if n else 0.0,
            "charge_days": sum(1 for v in per_date[wd].values() if v > CHARGE_DAY_KWH),
        })
    day = sum(e["day"] for e in energy.values())
    night = sum(e["night"] for e in energy.values())
    weekend = sum(sum(energy[wd].values()) for wd in (5, 6))
    mon_fri_night = sum(energy[wd]["night"] for wd in range(5))
    mon_fri = sum(sum(energy[wd].values()) for wd in range(5))
    result.update({
        "day_share_pct": round(100 * day / total), "night_share_pct": round(100 * night / total),
        "weekend_share_pct": round(100 * weekend / total),
        "weekdays_night_share_pct": round(100 * mon_fri_night / mon_fri) if mon_fri > 0 else None,
    })
    return result
