"""How much energy the car needs for the next day (pure Python, no Home Assistant imports).

Takes the learned weekday plan (`learning.WeekdayPlan`) and the settings of the car and returns the range to have at
departure, the state of charge that means and the energy to charge from the wallbox.

Rules (decided after testing with real data, see the design notes):

* The **reserve** (kilometres, a setting per car) is a *floor*: the car leaves with at least that range.
  On days that usually need more (`km_high` of the weekday) the learned value lifts it: `max(reserve, km_high)`.
  Mode `plus` instead adds the reserve to the learned value (more energy, the safest).
* A weekday on which the car is mostly charged **away from home** only gets the reserve at home: the trip is
  covered somewhere else.
* Without enough learned days, or with the switch *learn kilometres per weekday* off, the reserve alone counts.
* The energy follows from the consumption (kWh per km, learned or default) and a winter factor; charging losses
  are added for the energy that has to come from the wallbox.
"""

from __future__ import annotations

from dataclasses import dataclass

from learning import WeekdayPlan

MIN_SAMPLES = 3          # days needed before the learned value is trusted
AWAY_SHARE = 0.3         # below this share of home charging a weekday is an "away" day
DEFAULT_EFFICIENCY = 0.9  # share of the wallbox energy that reaches the battery
MODE_FLOOR = "floor"
MODE_PLUS = "plus"


@dataclass(frozen=True)
class Need:
    km: float             # range to have at departure
    kwh: float            # battery energy for that range
    target_soc: float     # state of charge at departure, % (limited by min_soc and max_soc)
    charge_kwh: float     # energy to take from the wallbox now (0 if the car is full enough)
    reachable: bool       # False if the range needs more than max_soc allows
    source: str           # "reserve", "learned", "away" or "plus"


def compute_need(
    plan: WeekdayPlan,
    reserve_km: float,
    soc: float | None,
    capacity_kwh: float,
    consumption_kwh_per_km: float,
    *,
    efficiency: float = DEFAULT_EFFICIENCY,
    max_soc: float = 100.0,
    min_soc: float = 20.0,
    winter_factor: float = 1.0,
    mode: str = MODE_FLOOR,
    learn_km: bool = True,
) -> Need:
    """Need for the departure the `plan` describes. `soc` None = unknown (the whole target is charged).
    `learn_km` False ignores what was learned about the kilometres: the reserve alone counts (switch in the settings)."""
    learned = plan.km_high if learn_km and plan.samples >= MIN_SAMPLES and plan.km_high is not None else None
    if learned is None:
        km, source = reserve_km, "reserve"
    elif plan.home_charge_share is not None and plan.home_charge_share < AWAY_SHARE:
        km, source = reserve_km, "away"
    elif mode == MODE_PLUS:
        km, source = reserve_km + learned, "plus"
    elif learned > reserve_km:
        km, source = learned, "learned"
    else:
        km, source = reserve_km, "reserve"
    kwh = km * consumption_kwh_per_km * winter_factor
    wanted_soc = kwh / capacity_kwh * 100.0 if capacity_kwh > 0 else 0.0
    target = min(max_soc, max(min_soc, wanted_soc))
    start = 0.0 if soc is None else soc
    charge = max(0.0, (target - start) / 100.0 * capacity_kwh) / max(0.1, efficiency)
    return Need(
        km=round(km, 1), kwh=round(kwh, 1), target_soc=round(target, 1), charge_kwh=round(charge, 1),
        reachable=wanted_soc <= max_soc + 1e-9, source=source,
    )
