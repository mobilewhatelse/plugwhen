"""Where each value of a car comes from (pure Python): shown on the dashboard so it is clear what is measured, what comes from evcc
and what Plugwhen only recommends. Kept small on purpose: when the plan is written to evcc later, `plan` simply says "evcc"."""

from __future__ import annotations

from typing import Any


def _src(entity: str | None, evcc_known: bool) -> dict[str, Any]:
    if entity:
        return {"from": "sensor", "entity": entity}
    if evcc_known:
        return {"from": "evcc"}
    return {"from": None}


def data_sources(cfg: dict[str, Any], evcc_known: bool, evcc_info: dict[str, Any] | None, executed: bool = False) -> dict[str, Any]:
    """{soc, odometer, plugged, charging, wallbox_energy, departure, plan, evcc, taken_from}. `evcc_known`: evcc has this car at a
    loadpoint right now. `executed`: Plugwhen (or evcc on its behalf) switches by the plan; False = a recommendation only."""
    info = evcc_info or {}
    evcc = None
    if info.get("source"):
        evcc = {"address": info["source"],                        # "own" or "guard"
                "vehicle": cfg.get("evcc_vehicle"),
                "ok": info.get("ok") if info.get("used") else None,  # None = not asked (no car named in evcc)
                "error": info.get("error")}
    return {
        "soc": _src(cfg.get("soc_entity"), False),
        "odometer": _src(cfg.get("odometer_entity"), False),
        "plugged": _src(cfg.get("plugged_entity"), evcc_known),
        "charging": _src(cfg.get("charging_entity"), evcc_known),
        "wallbox_energy": _src(cfg.get("wallbox_energy_entity"), False),
        "departure": {"from": "sensor", "entity": cfg["departure_entity"]} if cfg.get("departure_entity") else {"from": "learned"},
        "plan": "executed" if executed else "recommendation",
        "evcc": evcc,
        "taken_from": list(cfg.get("taken_from") or []),
    }
