"""Charging for several days at once (pure Python, no Home Assistant imports).

Wish of a user after the field test of November 2026: thinking from day to day charges a few kWh every night and makes a frequent
driver plug in every day. Replayed with 255 real days of one car: 5.6 charges a week of 13 kWh, a third of them below 8 kWh; with
three days ahead 3.2 charges a week of 26 kWh.

Two targets:

* **must** - the next trip (with the reserve, as chosen: left after the trip, or the least range at the departure). The warning,
  the promise and the safety check only know this one: nobody is told to plug in while the car has enough for the next trip.
* **comfort** - the trips of the next `days` days with the reserve, at most the everyday limit (e.g. 80 %; a need above it, a long
  trip or the weekly full charge, still counts). Charging goes up to here.

Charging **starts** only when the battery is below must, and then **fills** to comfort. Without that a car that is always plugged
in would again top up a few kWh every night.

**With a solar plant the sun comes first:** what the forecast says the sun can deliver while the car stands at home between the
coming trips - and is usually plugged in then, as learned from the plug-in times - is left to the sun; only the rest of the
comfort part is taken from the grid. Only what can be planned is counted. Must is always charged in time. Without a forecast
nothing is left out. Sun that comes while the car is plugged in is always used, plan or not: the wallbox's sun mode stays in
charge and Plugwhen never limits it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

try:  # inside Home Assistant the module lives in a package, the tests import it flat
    from .horizon import MIN_SUN_KW, QUARTER, QUARTER_H, Trip, away_hours
except ImportError:  # pragma: no cover
    from horizon import MIN_SUN_KW, QUARTER, QUARTER_H, Trip, away_hours

DEFAULT_DAYS = 3          # trips of this many days are charged at once (1 = every day on its own, as before)
MAX_DAYS = 7
DEFAULT_CAP = 80.0        # everyday limit of the comfort target in %
START_MARGIN = 0.5        # charging starts this many percent below must
DONE_MARGIN = 1.0         # the fill ends this many percent below comfort (cars often stop a little early)
HOLD_BAND = 5.0           # a running fill keeps its target while a newly computed one differs less than this (percent): the
                          # forecast, the weather and the learning move it a little all the time, and every new value makes a
                          # wallbox with a "next trip" mode stop and plan again
SUN_TRUST = 0.7           # share of the forecast sun that is counted on (a forecast is no promise, and the car may come home later)


@dataclass(frozen=True)
class Ahead:
    target_soc: float        # what to charge to now, %
    filling: bool            # a fill to comfort is running
    must_soc: float
    comfort_soc: float       # before the sun is taken off
    sun_kwh: float           # wallbox energy left to the sun in the coming home windows
    sun_basis: str | None          # "plug_times" (hours the car is usually plugged in) or "home" (no habit learned yet)
    trips: int               # trips counted for comfort
    days: int

    def as_dict(self) -> dict[str, Any]:
        return {"target_soc": self.target_soc, "filling": self.filling, "must_soc": self.must_soc, "comfort_soc": self.comfort_soc,
                "sun_kwh": self.sun_kwh, "sun_basis": self.sun_basis, "trips": self.trips, "days": self.days}


def trips_ahead(trips: list[Trip], first: datetime, days: int) -> list[Trip]:
    """The trips counted for comfort: from the departure `first` on, within `days` days of it."""
    end = first + timedelta(days=max(1, days)) - timedelta(minutes=1)
    return sorted((t for t in trips if first - timedelta(minutes=1) <= t.departure <= end), key=lambda t: t.departure)


def comfort_points(ahead: list[Trip]) -> list[float]:
    """For every one of these trips: the range to have at the first departure so that this trip still starts with its own
    target without charging in between - what the trips before it use (the high value where known, else the typical one)
    plus its target range."""
    out, used = [], 0.0
    for t in ahead:
        out.append(used + float(t.km_target))
        used += max(float(t.km_typical or 0.0), float(getattr(t, "km_high", None) or 0.0))
    return out


def comfort_km(ahead: list[Trip]) -> float:
    """The largest of them: usually the last trip decides, a long trip in the middle decides itself."""
    return max(comfort_points(ahead), default=0.0)


def sun_windows_kwh(now: datetime, ahead: list[Trip], sun_kw: dict[datetime, float] | None, max_kw: float,
                    plug_share: dict[tuple[int, int], float] | None = None) -> list[float]:
    """Wallbox energy the forecast sun can be planned to deliver in each home window between these trips (window k lies between
    trip k and trip k+1). Only what can be planned counts:

    * the car stands at home (between a trip's return and the next departure), and
    * it is usually plugged in at that weekday and hour (`plug_share`, learned from the recorded plug-in times: a car that
      comes home at three and is plugged in at six gets no sun between three and six). Without a learned habit (None) the
      time at home counts.

    The sun before the first departure is not counted here: the plan to that departure uses it itself. Sun that comes while
    the car happens to be plugged in is used anyway (the wallbox's sun mode), it is just not counted on in advance."""
    out: list[float] = []
    for prev, nxt in zip(ahead, ahead[1:]):
        total = 0.0
        if sun_kw:
            home_from = max(now, prev.departure + timedelta(hours=away_hours(float(prev.km_typical or 0.0))))
            t = home_from.replace(minute=(home_from.minute // 15) * 15, second=0, microsecond=0)
            while t < nxt.departure:
                end = t + QUARTER
                frac = (min(end, nxt.departure) - max(t, home_from)).total_seconds() / 900.0
                kw = min(max_kw, max(0.0, sun_kw.get(t, 0.0)))
                if frac > 0 and kw >= MIN_SUN_KW:
                    share = 1.0 if plug_share is None else plug_share.get((t.weekday(), t.hour), 0.0)
                    total += kw * QUARTER_H * frac * share
                t = end
        out.append(total)
    return out


def sun_later_kwh(now: datetime, ahead: list[Trip], sun_kw: dict[datetime, float] | None, max_kw: float,
                  plug_share: dict[tuple[int, int], float] | None = None) -> float:
    """All of it together."""
    return sum(sun_windows_kwh(now, ahead, sun_kw, max_kw, plug_share))


def decide(soc: float | None, must_soc: float, comfort_soc: float, filling: bool, plugged: bool | None) -> tuple[float, bool]:
    """(target now, fill running). Starts below must, fills to comfort, ends there or when the car is unplugged."""
    if soc is None or comfort_soc <= must_soc + START_MARGIN:
        return must_soc, False
    if soc < must_soc - START_MARGIN:
        filling = True
    elif plugged is False or soc >= comfort_soc - DONE_MARGIN:
        filling = False
    return (comfort_soc if filling else must_soc), filling


def look_ahead(now: datetime, trips: list[Trip], first: datetime | None, soc: float | None, must_soc: float, *, days: int,
               cap_soc: float, capacity_kwh: float, consumption: float, efficiency: float, filling: bool, plugged: bool | None,
               sun_kw: dict[datetime, float] | None = None, max_kw: float = 11.0, held_soc: float | None = None,
               plug_share: dict[tuple[int, int], float] | None = None) -> Ahead:
    """The target for now. `must_soc` = the target of the next departure as planned so far (with the weekly full charge, if any).
    `held_soc` = the target of the fill that is running (None = none). The result is never below `must_soc`."""
    days = max(1, min(MAX_DAYS, int(days)))
    ahead = trips_ahead(trips, first, days) if first is not None else []
    if days <= 1 or len(ahead) < 2 or capacity_kwh <= 0 or consumption <= 0:
        return Ahead(round(must_soc, 1), False, round(must_soc, 1), round(must_soc, 1), 0.0, None, len(ahead), days)
    limit = max(cap_soc, must_soc)
    points = [km * consumption / capacity_kwh * 100.0 for km in comfort_points(ahead)]
    comfort = max(must_soc, min(limit, max(points)))
    # the sun helps a trip only if it comes before that trip: for every trip its own need minus the sun of the home windows
    # before it, and the largest of these counts (sun after the long trip in the middle does not make that trip shorter)
    windows = [w * SUN_TRUST for w in sun_windows_kwh(now, ahead, sun_kw, max_kw, plug_share)]
    per_kwh = max(0.1, efficiency) / capacity_kwh * 100.0
    with_sun = max(must_soc, min(limit, max(pt - sum(windows[:k]) * per_kwh for k, pt in enumerate(points))))
    sun = sum(windows)
    if filling and held_soc is not None and abs(with_sun - held_soc) < HOLD_BAND:
        with_sun = max(must_soc, held_soc)   # the running fill keeps its target
    target, filling = decide(soc, must_soc, with_sun, filling, plugged)
    target = max(target, must_soc)
    return Ahead(round(target, 1), filling, round(must_soc, 1), round(comfort, 1), round(sun, 1),
                 ("plug_times" if plug_share is not None else "home") if sun_kw else None, len(ahead), days)
