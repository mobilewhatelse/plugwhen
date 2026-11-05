"""Reading the optional inputs of the planner (pure Python, no Home Assistant imports).

The adapter hands over the attributes of the chosen entities as plain data; this module turns them into what `plan.make_plan`
needs.

* **Load forecast** (for example the one of the quarter-hour peak guard): a list of hours `{t, typical, high}` and a peak
  target `target_kw`. Every hour is expanded to its four quarter hours.
* **Availability interface** (anything that knows when power is cheap or free for this household: own solar forecast,
  an energy community, a tariff signal). Attributes: `schema` (1), `valid_until` (ISO time, after it the data is ignored),
  `forecast`: list of `{start, end, kw}` (kW usable for charging, already net of the house load).
* **Departure by hand**: a time (`07:00`) or a date and time (`2026-11-12T07:00:00+01:00`).
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any

QUARTER = timedelta(minutes=15)
MAX_QUARTERS = 4 * 24 * 3     # three days at most; longer lists are cut


def _parse(value: Any, tz) -> datetime | None:
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value))
        except (TypeError, ValueError):
            return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=tz)


def floor_quarter(t: datetime) -> datetime:
    return t.replace(minute=(t.minute // 15) * 15, second=0, microsecond=0)


def load_from_hours(hours: Any, tz) -> list[dict[str, Any]]:
    """Quarter hours `{t, typical, high, n}` from a list of hours `{t, typical, high}`; broken entries are skipped."""
    out: list[dict[str, Any]] = []
    if not isinstance(hours, list):
        return out
    for h in hours:
        if not isinstance(h, dict):
            continue
        t = _parse(h.get("t"), tz)
        typical, high = h.get("typical"), h.get("high")
        if t is None or high is None:
            continue
        try:
            typical = float(typical) if typical is not None else float(high) / 2
            high = float(high)
        except (TypeError, ValueError):
            continue
        for q in range(4):
            out.append({"t": t + q * QUARTER, "typical": typical, "high": high, "n": 4})
    return out


def availability_from_attributes(attrs: dict[str, Any], now: datetime) -> dict[datetime, float] | None:
    """Usable power per quarter-hour start, or None if the interface delivers nothing usable (missing, expired, wrong schema)."""
    if not isinstance(attrs, dict):
        return None
    if attrs.get("schema") not in (None, 1, "1"):
        return None
    until = attrs.get("valid_until")
    if until is not None:
        u = _parse(until, now.tzinfo)
        if u is None or u <= now:
            return None
    items = attrs.get("forecast")
    if not isinstance(items, list):
        return None
    out: dict[datetime, float] = {}
    for it in items:
        if not isinstance(it, dict):
            continue
        start, end = _parse(it.get("start"), now.tzinfo), _parse(it.get("end"), now.tzinfo)
        try:
            kw = float(it.get("kw"))
        except (TypeError, ValueError):
            continue
        if start is None or end is None or end <= start or kw <= 0:
            continue
        t = floor_quarter(start)
        while t < end and len(out) < MAX_QUARTERS:
            out[t] = max(out.get(t, 0.0), kw)
            t += QUARTER
    return out or None


def departure_from_state(value: Any, now: datetime) -> datetime | None:
    """The next departure from the state of a time or date-time entity (never in the past: a time already gone means tomorrow)."""
    text = str(value or "").strip()
    if not text or text in ("unknown", "unavailable", "none", "None"):
        return None
    if ":" in text and "-" not in text and "T" not in text:  # a plain time
        try:
            parts = [int(p) for p in text.split(":")[:3]]
            t = time(*parts)
        except (TypeError, ValueError):
            return None
        dep = datetime.combine(now.date(), t, tzinfo=now.tzinfo)
        return dep if dep > now else dep + timedelta(days=1)
    dep = _parse(text.replace(" ", "T", 1), now.tzinfo)
    return dep if dep is not None and dep > now else None
