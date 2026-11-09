"""Taking over what the quarter-hour peak guard already knows (pure Python, no Home Assistant imports).

When a vehicle is added and the guard is installed, the form is filled in with the guard's vehicle and wallbox, so only
what the guard does not know is left (mostly the odometer). The values are copied once: Plugwhen keeps working when the
guard is removed later. Settings that change now and then (grid energy counter, demand charge, limit, load forecast) are
not copied here, Plugwhen reads them from the guard at run time.

Not taken over on purpose: the departure entity of the guard. In Plugwhen an entity departure replaces the learned one,
and a wallbox's "next departure" is often a fixed time that would switch the learning off.
"""

from __future__ import annotations

from typing import Any

VEHICLE = "vehicle"
WALLBOX_KINDS = ("wallbox", "evcc")
VOLTAGE = 230.0

# Plugwhen key <- guard key of the vehicle device
_FROM_VEHICLE = {
    "name": "name",
    "soc_entity": "soc_entity",
    "capacity_kwh": "capacity_kwh",
    "charge_kw_max": "charge_kw_max",
    "charge_kw_min": "charge_kw_min",
    "plugged_entity": "connected_entity",
}


def guard_vehicles(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The vehicle devices of the guard, in the order given."""
    return [d for d in devices if d.get("kind") == VEHICLE]


def guard_wallbox(devices: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The first wallbox of the guard (direct or behind evcc), or None."""
    for d in devices:
        if d.get("kind") in WALLBOX_KINDS:
            return d
    return None


def wallbox_kw(wallbox: dict[str, Any] | None, voltage: float = VOLTAGE) -> tuple[float, float] | None:
    """(lowest, highest) charging power in kW from the currents of a guard wallbox. The highest is three phases; the lowest
    is one phase when the wallbox may switch to one phase, else three. None if the currents are missing."""
    if not wallbox:
        return None
    try:
        lo_a, hi_a = float(wallbox.get("min_current") or 0), float(wallbox.get("max_current") or 0)
    except (TypeError, ValueError):
        return None
    if lo_a <= 0 or hi_a <= 0 or lo_a > hi_a:
        return None
    one_phase = bool(wallbox.get("one_phase_option") or wallbox.get("phase_entity") or wallbox.get("evcc_one_phase"))
    lo = lo_a * voltage * (1 if one_phase else 3) / 1000.0
    hi = hi_a * voltage * 3 / 1000.0
    return round(lo, 1), round(hi, 1)


def next_vehicle(devices: list[dict[str, Any]], taken_soc: set[str]) -> dict[str, Any] | None:
    """The first guard vehicle that Plugwhen does not have yet (compared by the state of charge sensor)."""
    for v in guard_vehicles(devices):
        if v.get("soc_entity") and v["soc_entity"] not in taken_soc:
            return v
    return None


def vehicle_from_guard(vehicle: dict[str, Any], devices: list[dict[str, Any]], notify: str | None = None) -> dict[str, Any]:
    """Plugwhen vehicle settings from a guard vehicle. The car's own powers win over those computed from the wallbox.
    Only keys with a value are returned, so the form keeps its defaults for the rest."""
    out: dict[str, Any] = {}
    for mine, theirs in _FROM_VEHICLE.items():
        if vehicle.get(theirs) not in (None, ""):
            out[mine] = vehicle[theirs]
    kw = wallbox_kw(guard_wallbox(devices))
    if kw is not None:
        out.setdefault("charge_kw_min", kw[0])
        out.setdefault("charge_kw_max", kw[1])
    if notify and str(notify).strip():
        out["notify_service"] = ", ".join(x.strip() for x in str(notify).split(",") if "." in x)
        if not out["notify_service"]:
            del out["notify_service"]
    return out


COUNTERS = ("total_increasing", "total")


def pick_by_unit(candidates: list[tuple[str, str | None, str | None]], units: tuple[str, ...],
                 exclude: set[str] | None = None) -> str | None:
    """A counter on the same device, e.g. the odometer next to the state of charge, or the energy counter next to the
    wallbox power. `candidates` are (entity_id, unit, state_class). The unit must be one of `units` (case-insensitive);
    a counter (state class total_increasing or total) wins over a measurement such as the range, then the id decides."""
    want = {u.lower() for u in units}
    fit = [(sc not in COUNTERS, eid) for eid, unit, sc in candidates
           if eid not in (exclude or set()) and unit and unit.strip().lower() in want]
    return min(fit)[1] if fit else None
