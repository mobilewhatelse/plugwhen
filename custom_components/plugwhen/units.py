"""Checks of the sensors chosen in the dialogs (pure Python, no Home Assistant imports).

A sensor does not need a device class: a template sensor with the right unit is just as good, and many installations have exactly
that. What matters is the unit, because Plugwhen converts it. A sensor without any unit is accepted where Plugwhen assumes one
(kilometres, percent, kWh); a unit it cannot convert is refused with a clear message.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

DISTANCE_UNITS = ("km", "mi", "mile", "miles")
PERCENT_UNITS = ("%",)
ENERGY_UNITS = ("wh", "kwh", "mwh")


def unit_errors(
    get_state: Callable[[str], Any],
    values: Mapping[str, Any],
    specs: Mapping[str, tuple[tuple[str, ...], str]],
) -> dict[str, str]:
    """Field name -> error key for every chosen sensor whose unit is not one of the allowed ones.

    `specs`: field name -> (allowed units in lower case, error key). A sensor that is not loaded yet is not blocked, an empty field
    and a sensor without a unit are not either (the unit is assumed, see above)."""
    errors: dict[str, str] = {}
    for key, (units, error) in specs.items():
        entity_id = values.get(key)
        if not entity_id:
            continue
        state = get_state(entity_id)
        if state is None:
            continue
        unit = str(state.attributes.get("unit_of_measurement") or "").strip().lower()
        if unit and unit not in units:
            errors[key] = error
    return errors
