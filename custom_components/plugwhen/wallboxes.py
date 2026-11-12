"""Several cars and several wallboxes (pure Python, no Home Assistant imports).

* A car may have more than one wallbox (at home and at work, or two at home): its energy counters are listed, the first one
  is the car's own field, more come from an optional field.
* A wallbox may be used by more than one car: its counter then counts for a car only in the hours in which that car's state
  of charge rose (the counter alone cannot tell who was plugged in).
* Which wallbox the car is at right now: the one whose counter rises while the car charges. Without a rise the last one
  found stays (a car is not moved to another wallbox by a quiet minute).
* Plans of several cars are made one after the other: the car that is plugged in first, then by departure. A later car
  sees what the earlier ones already planned: it eats their solar power and their room under the peak target, and at a
  wallbox they share it cannot charge in the same quarter hour.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Iterable, Mapping

MIN_RISE_KWH = 0.01         # a counter rise below this is noise
SOC_RISE_PCT = 1.0          # an hour in which the state of charge rose by at least this much: the car was charging


def wallbox_ids(first: Any, more: Any = None) -> list[str]:
    """The energy counters of a car: its own field first, then the optional further ones; no doubles, no empties."""
    out: list[str] = []
    for x in [first, *(more if isinstance(more, (list, tuple)) else [more])]:
        if isinstance(x, str) and x.strip() and x.strip() not in out:
            out.append(x.strip())
    return out


def shared(cars: Mapping[str, Iterable[str]]) -> set[str]:
    """Counters used by more than one car."""
    seen: dict[str, int] = {}
    for ids in cars.values():
        for i in set(ids):
            seen[i] = seen.get(i, 0) + 1
    return {i for i, n in seen.items() if n > 1}


def soc_rise_hours(soc: list[tuple[datetime, float | None]]) -> set[datetime]:
    """Hour starts in which the state of charge rose (from the hourly statistics, mean or state)."""
    out: set[datetime] = set()
    prev: float | None = None
    for t, s in soc:
        if s is None:
            continue
        if prev is not None and s - prev >= SOC_RISE_PCT:
            out.add(t)
        prev = s
    return out


def car_hourly(changes: Mapping[str, Mapping[datetime, float]], shared_ids: set[str], rise_hours: set[datetime]) -> dict[datetime, float]:
    """Energy per hour that went into this car from its wallboxes. A counter of its own counts fully; a shared one only in the
    hours the car's state of charge rose (that hour or the one after: the hourly mean of the state of charge lags behind)."""
    out: dict[datetime, float] = {}
    for wid, hours in changes.items():
        for t, kwh in hours.items():
            out.setdefault(t, 0.0)   # an hour the counter knows counts, also with nothing charged (a day without charging is 0, not unknown)
            if kwh is None or kwh <= 0:
                continue
            if wid in shared_ids and t not in rise_hours and (t + timedelta(hours=1)) not in rise_hours:
                continue
            out[t] = out.get(t, 0.0) + kwh
    return out


def cumulative(hourly: Mapping[datetime, float]) -> list[tuple[datetime, float]]:
    """An energy counter made from hourly energies (the value at the end of each hour), for the daily records."""
    total = 0.0
    out = []
    for t in sorted(hourly):
        total += hourly[t]
        out.append((t, round(total, 3)))
    return out


def active_wallbox(before: Mapping[str, float | None], now: Mapping[str, float | None], charging: bool, last: str | None) -> str | None:
    """The wallbox the car is at: the counter that rose most since the last look while the car charges; otherwise the last one
    found. A car with one wallbox is always at that one."""
    ids = list(now)
    if len(ids) == 1:
        return ids[0]
    if charging:
        rises = {i: (now[i] or 0.0) - (before.get(i) or 0.0) for i in ids if now.get(i) is not None and before.get(i) is not None}
        best = max(rises, key=lambda i: rises[i], default=None)
        if best is not None and rises[best] >= MIN_RISE_KWH:
            return best
    return last if last in ids else None


def plan_order(cars: list[dict[str, Any]]) -> list[str]:
    """Order in which the plans are made: plugged in first (it can charge now), then the earlier departure, then the name.
    `cars`: {id, plugged, departure (datetime or None), name}."""
    far = datetime.max.replace(tzinfo=None)

    def key(c: dict[str, Any]):
        dep = c.get("departure")
        return (0 if c.get("plugged") else 1, dep.replace(tzinfo=None) if isinstance(dep, datetime) else far, str(c.get("name") or ""))

    return [c["id"] for c in sorted(cars, key=key)]


def taken_by_others(plans: list[tuple[set[str], Mapping[datetime, float]]], mine: set[str]) -> tuple[dict[datetime, float], set[datetime]]:
    """What the cars planned before this one leave: their power per quarter hour (all of them: the same house, the same peak) and
    the quarter hours in which one of them charges at a wallbox this car shares (one plug, one car at a time).
    `plans`: (the wallboxes of an earlier car, its planned kW per quarter hour)."""
    power: dict[datetime, float] = {}
    blocked: set[datetime] = set()
    for ids, quarters in plans:
        same = bool(ids & mine)
        for t, kw in quarters.items():
            if kw and kw > 0:
                power[t] = power.get(t, 0.0) + kw
                if same:
                    blocked.add(t)
    return power, blocked
