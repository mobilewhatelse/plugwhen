"""When to tell the driver that the car will not be ready tomorrow (pure Python, no Home Assistant imports).

`check_ready` compares the energy the next departure needs (`need.Need`) with what is going to happen and returns a
`Notice` or None. It only decides; the text and the sending (notify service) belong to the Home Assistant layer, which
also keeps `dedupe_key` to send each warning once.

Kinds, most urgent first:

* `not_reachable`: the target needs more than the battery or the allowed maximum can give, charging does not help.
* `too_late`: even charging at full power from now until departure is not enough.
* `plug_in`: the car is known not to be plugged in and is short of the target: plug it in (even if a plan exists:
  it cannot run without the car).
* `low`: short of the target, plug state unknown and nothing planned that covers it.

Nothing is sent if the shortfall is small, if the car is charging or (plugged in or unknown) a plan covers the shortfall.

A car known not to be plugged in gets one more reminder from the evening hour on, even if a warning for the same departure
went out earlier in the day (`reminder_key`): a warning at noon for a trip at 22:00 must not be the last word. For
`not_reachable` and `too_late` the plug state rides along (`plugged_out`), so the text can still ask to plug in.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

try:  # inside Home Assistant the module lives in a package, the tests import it flat
    from .need import Need
except ImportError:  # pragma: no cover
    from need import Need

MIN_SHORTFALL_KWH = 0.5      # below this the car counts as ready
PLAN_COVERS = 0.95           # a plan that delivers this share of the shortfall is enough


@dataclass(frozen=True)
class Notice:
    kind: str                # "not_reachable", "too_late", "plug_in" or "low"
    shortfall_kwh: float     # wallbox energy still missing for the target
    soc: float | None
    target_soc: float
    km: float
    hours_left: float | None
    max_possible_kwh: float | None  # most that can still be charged before departure (too_late)
    plugged_out: bool = False       # known not to be plugged in (also for not_reachable / too_late)


def check_ready(
    need: Need,
    soc: float | None,
    *,
    plugged: bool | None,
    charging: bool,
    hours_to_departure: float | None,
    charge_kw_max: float | None = None,
    planned_kwh: float | None = None,
) -> Notice | None:
    """`plugged` None = unknown. `planned_kwh` = wallbox energy a plan will deliver before departure (None = no plan)."""
    shortfall = need.charge_kwh
    if shortfall < MIN_SHORTFALL_KWH:
        return None

    def notice(kind: str, possible: float | None = None) -> Notice:
        return Notice(kind, round(shortfall, 1), soc, need.target_soc, need.km, hours_to_departure,
                      None if possible is None else round(possible, 1), plugged is False)

    if not need.reachable:
        return notice("not_reachable")
    possible = None
    if hours_to_departure is not None and charge_kw_max:
        possible = max(0.0, hours_to_departure) * charge_kw_max
        if shortfall > possible + 1e-9:
            return notice("too_late", possible)
    if plugged is False:
        return notice("plug_in")  # a plan means nothing while the car is not plugged in
    if charging or (planned_kwh is not None and planned_kwh >= PLAN_COVERS * shortfall):
        return None
    if plugged is None:
        return notice("low")
    return None  # plugged in, nothing charging yet and no plan: the charging itself is the plan's job, not a warning


@dataclass(frozen=True)
class Ahead:
    """The heads-up for the day after today: charging will be needed (`charge`) or charging with the sun in advance is recommended (`sun`)."""

    kind: str                      # "charge" or "sun"
    day: date                      # the day on which to charge (tomorrow)
    departure: datetime            # the departure the energy is for
    kwh: float                     # wallbox energy (charge: still from the grid, sun: to charge with the sun)
    latest_start: datetime | None  # at full power
    latest_start_pref: datetime | None  # at the preferred power
    sun_from: datetime | None = None
    sun_to: datetime | None = None


def _dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value)) if value else None
    except ValueError:
        return None


def check_ahead(horizon: dict[str, Any] | None, now: datetime, from_hour: float, min_kwh: float = 1.0) -> Ahead | None:
    """The heads-up of this evening for tomorrow, from the look-ahead (`horizon.horizon_plan`). Only from `from_hour` on, like the other
    warning. A recommended pre-charge with the sun tomorrow comes first, otherwise a departure that needs grid energy and whose home window
    begins tomorrow. Charging that has to happen today is the job of the plug-in warning, not of this one."""
    if not horizon or horizon.get("status") != "ok":
        return None
    if now.hour + now.minute / 60.0 < from_hour:
        return None
    tomorrow = (now + timedelta(days=1)).date()
    for p in horizon.get("precharge") or []:
        start, dep = _dt(p.get("sun_from")), _dt(p.get("for_departure"))
        if start is not None and dep is not None and start.date() == tomorrow and float(p.get("kwh") or 0) >= max(2.0, min_kwh):
            return Ahead("sun", tomorrow, dep, float(p["kwh"]), None, None, start, _dt(p.get("sun_to")))
    for d in horizon.get("days") or []:
        start, dep = _dt(d.get("window_start")), _dt(d.get("departure"))
        if start is not None and dep is not None and start.date() == tomorrow and float(d.get("grid_kwh") or 0) >= min_kwh:
            return Ahead("charge", tomorrow, dep, float(d["grid_kwh"]), _dt(d.get("latest_start")), _dt(d.get("latest_start_pref")))
    return None


def tip_ahead(horizon: dict[str, Any] | None, now: datetime) -> Ahead | None:
    """The same heads-up for the dashboard, at any hour: a pre-charge with the sun today whose window has not ended yet comes first
    (the notification of last evening is then still valid), otherwise what the evening notification says for tomorrow."""
    if not horizon or horizon.get("status") != "ok":
        return None
    today = now.date()
    for p in horizon.get("precharge") or []:
        start, end, dep = _dt(p.get("sun_from")), _dt(p.get("sun_to")), _dt(p.get("for_departure"))
        if (start is not None and dep is not None and start.date() == today and (end or start) > now
                and float(p.get("kwh") or 0) >= 2.0):
            return Ahead("sun", today, dep, float(p["kwh"]), None, None, start, end)
    return check_ahead(horizon, now, 0.0)


def ahead_key(a: Ahead) -> str:
    """Once per day of charging and kind."""
    return f"ahead:{a.day.isoformat()}:{a.kind}"


def dedupe_key(n: Notice, departure_day: date) -> str:
    """Send a warning once per departure day and kind (a worse kind is a new warning)."""
    return f"{departure_day.isoformat()}:{n.kind}"


def reminder_key(n: Notice, departure_day: date, now_hour: float, from_hour: float) -> str | None:
    """The one evening reminder to plug in (None = none due): only for a car known not to be plugged in, only from `from_hour`."""
    if not n.plugged_out or now_hour < from_hour:
        return None
    return f"{departure_day.isoformat()}:plug_evening"


ONCE_KEYS = frozenset({"switch_ready"})   # messages sent once per car, never again


def remember_sent(sent: list[str], key: str, keep: int) -> None:
    """Note a sent message: the last `keep` dated ones are kept (so a restart does not repeat them), the once-only ones for good.
    Before, "the learn mode is through" fell out after eight other messages and was sent again every week or two."""
    if key not in sent:
        sent.append(key)
    once = [k for k in sent if k in ONCE_KEYS]
    dated = [k for k in sent if k not in ONCE_KEYS][-keep:]
    sent[:] = once + dated


def should_check(now_hour: float, from_hour: float, hours_to_departure: float | None) -> bool:
    """Look from `from_hour` in the evening until the departure (False once it is past)."""
    if hours_to_departure is not None and hours_to_departure <= 0:
        return False
    return now_hour >= from_hour or (hours_to_departure is not None and hours_to_departure <= 12)
