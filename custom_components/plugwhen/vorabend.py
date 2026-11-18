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
MIN_HOURS = 2.0         # the first trip must be at least this far away (else the normal plan is at work)


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


def evening_before(now: datetime, horizon: dict | None, soc: float | None, capacity_kwh: float, efficiency: float,
                   plugged: bool | None, have_kwh: float = 0.0) -> EveningBefore | None:
    """The charge for tomorrow's later trip, or None. `horizon` = result of horizon.horizon_plan; `have_kwh` = what the plan
    for the next trip already charges (that part is not charged twice)."""
    if not horizon or soc is None or capacity_kwh <= 0 or plugged is False:
        return None
    need = horizon.get("first_need")
    by = _parse(horizon.get("lasts_until"))
    if not need or by is None or need.get("covered_by_sun"):
        return None   # the first trip is the next one (the normal plan), or the sun at home brings it
    start, dep = _parse(need.get("window_start")), _parse(need.get("departure"))
    kwh = float(need.get("need_kwh") or 0.0)
    if start is None or dep is None or kwh < MIN_KWH:
        return None
    if by - now < timedelta(hours=MIN_HOURS) or start.date() <= now.date():
        return None   # arises today or the first trip is imminent: nothing "before the evening" about it
    if start.date() > (now + timedelta(days=1)).date():
        return None   # only what is needed tomorrow, not the day after (that is the look-ahead's job)
    kwh = max(0.0, kwh - max(0.0, have_kwh))
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
    if dep is None or kwh < MIN_KWH or dep <= now + timedelta(hours=MIN_HOURS):
        return None
    if departure - dep < timedelta(hours=MIN_HOURS) or dep.date() > (now + timedelta(days=1)).date():
        return None
    target = min(100.0, soc + kwh * max(0.1, efficiency) / capacity_kwh * 100.0)
    if target <= soc + 0.05:
        return None
    return EveningBefore(round(kwh, 1), round(target, 1), dep, departure)
