"""Is a reading too old to be believed? (pure Python, no Home Assistant imports)

The state of charge of a car is written by the car's integration, and many cars say nothing for hours: a parked car
that sleeps is fine, its value is still true. But a car that is *charging* changes its state of charge all the time; if
no new value comes for a while, the value is not what the car has now. Plugwhen treats a stale state of charge like an
unknown one: no energy to charge, no plan, no warning.
"""

from __future__ import annotations

CHARGING_MAX_AGE_MIN = 90.0   # while the car is charging a value older than this is stale


def soc_is_stale(age_s: float | None, max_age_h: float, charging: bool, charging_max_min: float = CHARGING_MAX_AGE_MIN) -> bool:
    """`age_s`: seconds since the state of charge was written (None = unknown age, then it is not called stale).
    `max_age_h`: allowed age in hours, 0 = no limit. `charging`: the car is known to be charging."""
    if age_s is None:
        return False
    if max_age_h > 0 and age_s > max_age_h * 3600.0:
        return True
    return bool(charging) and age_s > charging_max_min * 60.0
