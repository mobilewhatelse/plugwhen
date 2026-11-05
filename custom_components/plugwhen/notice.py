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
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

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
                      None if possible is None else round(possible, 1))

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


def dedupe_key(n: Notice, departure_day: date) -> str:
    """Send a warning once per departure day and kind (a worse kind is a new warning)."""
    return f"{departure_day.isoformat()}:{n.kind}"


def should_check(now_hour: float, from_hour: float, hours_to_departure: float | None) -> bool:
    """Look from `from_hour` in the evening until the departure (False once it is past)."""
    if hours_to_departure is not None and hours_to_departure <= 0:
        return False
    return now_hour >= from_hour or (hours_to_departure is not None and hours_to_departure <= 12)
