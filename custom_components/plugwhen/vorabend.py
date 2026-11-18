"""Charge the evening before (pure Python, no Home Assistant imports).

The car leaves tomorrow, comes home and leaves again (a second trip in the evening): the charge reaches the first trip, but after
it a few kWh are missing for the second one. Wish of a user (18.11.2026): everything needed for the next day is charged in the
standing time, best the evening before, not "at the latest" the next afternoon (that fails if the car is not plugged in then).

The everyday limit ("limit for several days") only limits charging that nobody needs; it never cuts this need.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

MIN_KWH = 0.5           # smaller gaps are not worth a charge
SAME_TRIP = timedelta(hours=2)   # an expected departure this close before the plan's is the same trip (horizon.SAME_TRIP_WINDOW)


@dataclass(frozen=True)
class EveningBefore:
    kwh: float              # wallbox energy to charge now
    target_soc: float       # state of charge to reach, %
    by: datetime            # done by the first departure, until when the charge lasts
    for_departure: datetime  # the later departure the energy is for

    def as_dict(self) -> dict[str, Any]:
        return {"kwh": self.kwh, "target_soc": self.target_soc, "by": self.by.isoformat(),
                "for_departure": self.for_departure.isoformat()}


def _parse(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value)) if value else None
    except ValueError:
        return None


def _same_day(now: datetime, days: list[dict]) -> tuple[datetime, datetime, float] | None:
    """From the look-ahead's rows: the first departure, the last later departure of the SAME day that needs energy, and the wallbox
    energy for all of them (the first trip's own need included; the caller takes off what the plan charges anyway).

    Only trips of the same day: the window before a trip of another day is a night at home (normal charging, or the look-ahead with
    its everyday limit); without this the charge rolled on night after night and filled the battery to 95-100 % for trips two days
    later (week replay 18.11.2026). All later trips of the day count, also when the first one needs a little itself: a first need of
    0.2 kWh hid the evening trip, the car left in the evening with 40 % instead of 62 % (week replay 18.11.2026)."""
    by = _parse(days[0].get("departure"))
    if by is None or by <= now or by.date() > (now + timedelta(days=1)).date():
        return None   # the first trip is past, or not tomorrow yet (that is the look-ahead's job)
    total, grid, last = float(days[0].get("need_kwh") or 0.0), 0.0, None
    for d in days[1:]:
        dep = _parse(d.get("departure"))
        if dep is None or dep.date() != by.date():
            break
        k = float(d.get("need_kwh") or 0.0)
        total += k
        grid += float(d.get("grid_kwh") if d.get("grid_kwh") is not None else k)
        if k > 0:
            last = dep
    if last is None or grid < MIN_KWH:
        return None   # nothing later that day, or the sun at home brings it
    return by, last, total


def evening_before(now: datetime, horizon: dict | None, soc: float | None, capacity_kwh: float, efficiency: float,
                   plugged: bool | None, have_kwh: float = 0.0) -> EveningBefore | None:
    """The charge for tomorrow's later trip, or None. `horizon` = result of horizon.horizon_plan; `have_kwh` = what the plan
    for the next trip already charges (that part is not charged twice)."""
    if not horizon or soc is None or capacity_kwh <= 0 or plugged is False:
        return None
    days = horizon.get("days") or []
    if days:
        found = _same_day(now, days)
        if found is None:
            return None
        by, dep, kwh = found
    else:   # an older look-ahead without its rows: the first need only
        need = horizon.get("first_need")
        by = _parse(horizon.get("lasts_until"))
        if not need or by is None or need.get("covered_by_sun"):
            return None
        start, dep = _parse(need.get("window_start")), _parse(need.get("departure"))
        kwh = float(need.get("need_kwh") or 0.0)
        if (start is None or dep is None or by <= now or dep <= by or dep.date() != by.date()
                or start.date() > (now + timedelta(days=1)).date()):
            return None
    # never more than the battery takes before the first trip: a later trip that needs it full again cannot be charged ahead
    room = max(0.0, 100.0 - soc) / 100.0 * capacity_kwh / max(0.1, efficiency)
    kwh = min(kwh, room) - max(0.0, have_kwh)
    if kwh < MIN_KWH:
        return None
    target = min(100.0, soc + kwh * max(0.1, efficiency) / capacity_kwh * 100.0)
    if target <= soc + 0.05:
        return None
    return EveningBefore(round(kwh, 1), round(target, 1), by, dep)


def earlier_departure(now: datetime, horizon: dict | None, departure: datetime | None, soc: float | None, capacity_kwh: float,
                      efficiency: float, plugged: bool | None) -> EveningBefore | None:
    """The look-ahead expects an earlier departure than the plan's (a learned morning trip before a calendar trip in the evening)
    and the charge is needed already for it: the plan is made for that departure, i.e. charged in the standing time before it,
    not in a window that exists only if the car is at home after it."""
    if not horizon or soc is None or capacity_kwh <= 0 or departure is None or plugged is False:
        return None
    need = horizon.get("first_need")
    if not need or need.get("covered_by_sun"):
        return None
    dep, kwh = _parse(need.get("departure")), float(need.get("need_kwh") or 0.0)
    if dep is None or kwh < MIN_KWH or dep <= now:
        return None   # kept until that departure itself: a deadline that jumps back shortly before it moves the charge away
    if departure - dep < SAME_TRIP or dep.date() > (now + timedelta(days=1)).date():
        return None
    target = min(100.0, soc + kwh * max(0.1, efficiency) / capacity_kwh * 100.0)
    if target <= soc + 0.05:
        return None
    return EveningBefore(round(kwh, 1), round(target, 1), dep, departure)
