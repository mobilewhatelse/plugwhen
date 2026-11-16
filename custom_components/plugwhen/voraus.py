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
coming trips is left to the sun; only the rest of the comfort part is taken from the grid. Must is always charged in time. Without
a forecast nothing is left out. (The sun mode of the wallbox keeps charging surplus beyond that anyway.)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

try:  # inside Home Assistant the module lives in a package, the tests import it flat
    from .horizon import Trip, _sun_in, away_hours
except ImportError:  # pragma: no cover
    from horizon import Trip, _sun_in, away_hours

DEFAULT_DAYS = 3          # trips of this many days are charged at once (1 = every day on its own, as before)
MAX_DAYS = 7
DEFAULT_CAP = 80.0        # everyday limit of the comfort target in %
START_MARGIN = 0.5        # charging starts this many percent below must
DONE_MARGIN = 1.0         # the fill ends this many percent below comfort (cars often stop a little early)
SUN_TRUST = 0.7           # share of the forecast sun that is counted on (a forecast is no promise, and the car may come home later)


@dataclass(frozen=True)
class Ahead:
    target_soc: float        # what to charge to now, %
    filling: bool            # a fill to comfort is running
    must_soc: float
    comfort_soc: float       # before the sun is taken off
    sun_kwh: float           # wallbox energy left to the sun in the coming home windows
    trips: int               # trips counted for comfort
    days: int

    def as_dict(self) -> dict[str, Any]:
        return {"target_soc": self.target_soc, "filling": self.filling, "must_soc": self.must_soc, "comfort_soc": self.comfort_soc,
                "sun_kwh": self.sun_kwh, "trips": self.trips, "days": self.days}


def trips_ahead(trips: list[Trip], first: datetime, days: int) -> list[Trip]:
    """The trips counted for comfort: from the departure `first` on, within `days` days of it."""
    end = first + timedelta(days=max(1, days)) - timedelta(minutes=1)
    return sorted((t for t in trips if first - timedelta(minutes=1) <= t.departure <= end), key=lambda t: t.departure)


def comfort_km(ahead: list[Trip]) -> float:
    """The range to have at the first departure so that the last of these trips still starts with its own target: what the trips
    before it use (the high value where known, else the typical one) plus the last trip's target range."""
    if not ahead:
        return 0.0
    used = sum(max(float(t.km_typical or 0.0), float(getattr(t, "km_high", None) or 0.0)) for t in ahead[:-1])
    return used + float(ahead[-1].km_target)


def sun_later_kwh(now: datetime, ahead: list[Trip], sun_kw: dict[datetime, float] | None, max_kw: float) -> float:
    """Wallbox energy the forecast sun can deliver while the car stands at home between these trips (after the first one). The sun
    before the first departure is not counted here: the plan to that departure uses it itself."""
    total = 0.0
    for prev, nxt in zip(ahead, ahead[1:]):
        home_from = max(now, prev.departure + timedelta(hours=away_hours(float(prev.km_typical or 0.0))))
        total += _sun_in(home_from, nxt.departure, sun_kw, max_kw)[0]
    return total


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
               sun_kw: dict[datetime, float] | None = None, max_kw: float = 11.0) -> Ahead:
    """The target for now. `must_soc` = the target of the next departure as planned so far (with the weekly full charge, if any)."""
    days = max(1, min(MAX_DAYS, int(days)))
    ahead = trips_ahead(trips, first, days) if first is not None else []
    if days <= 1 or len(ahead) < 2 or capacity_kwh <= 0 or consumption <= 0:
        return Ahead(round(must_soc, 1), False, round(must_soc, 1), round(must_soc, 1), 0.0, len(ahead), days)
    comfort = min(max(cap_soc, must_soc), comfort_km(ahead) * consumption / capacity_kwh * 100.0)
    comfort = max(must_soc, comfort)
    sun = sun_later_kwh(now, ahead, sun_kw, max_kw) * SUN_TRUST
    with_sun = max(must_soc, comfort - sun * max(0.1, efficiency) / capacity_kwh * 100.0)
    target, filling = decide(soc, must_soc, with_sun, filling, plugged)
    return Ahead(round(target, 1), filling, round(must_soc, 1), round(comfort, 1), round(sun, 1), len(ahead), days)
