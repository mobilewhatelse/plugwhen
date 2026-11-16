"""Mode 'direct': Plugwhen controls the wallbox itself (pure Python). What it does depends on what the wallbox can:

* **trip** - the wallbox has its own "next trip" mode (departure time + energy), e.g. the Fronius Wattpilot: Plugwhen only fills in
  the departure and the energy and switches to that mode when charging is needed for a departure within 24 hours. The wallbox keeps
  using the sun first and charges the rest in time. Afterwards the mode it had before is restored.
* **mode** - a mode select with a sun mode (eco) and a grid mode (default/standard): during Plugwhen's planned grid windows the grid
  mode, afterwards back to what it was.
* **buttons** - only start/stop: start at the beginning of a planned window, stop at its end.

The sun mode of the wallbox stays in charge; Plugwhen only fills the gap the sun leaves before a departure. Only what Plugwhen set
itself is ever changed back: if the user changes the wallbox in between, Plugwhen leaves it alone. The quarter-hour peak guard still
has the last word.

The capabilities are found on the wallbox's device (no settings needed): `detect` gets the entities of that device.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

TRIP_HORIZON = timedelta(hours=24)   # a wallbox's "next trip" is a time of day: only for a departure within 24 hours
MIN_KWH = 0.5
TRIP_RESEND_KWH = 1.5   # the energy is written again only if the need differs this much from what charging explains

_TRIP = re.compile(r"next.?trip|n(ä|ae)chste.?fahrt|abfahrt", re.IGNORECASE)
_SUN = re.compile(r"\beco\b|pv|sonne|solar|surplus|überschuss", re.IGNORECASE)
_GRID = re.compile(r"default|standard|normal|sofort|fast|immediate", re.IGNORECASE)


def detect(entities: list[dict[str, Any]]) -> dict[str, Any]:
    """What the wallbox offers. `entities` = [{"entity_id", "domain", "options", "unit"}] of the wallbox's device.
    Returns {"variant": "trip" | "mode" | "buttons" | None, and the entities and option names found}."""
    out: dict[str, Any] = {"variant": None}
    for e in entities:
        eid, dom, opts = e.get("entity_id", ""), e.get("domain"), [str(o) for o in e.get("options") or []]
        if dom == "select" and opts and "mode" not in out:
            trip = next((o for o in opts if _TRIP.search(o)), None)
            sun = next((o for o in opts if _SUN.search(o)), None)
            grid = next((o for o in opts if _GRID.search(o)), None)
            if sun and (trip or grid):
                out.update(mode=eid, mode_trip=trip, mode_sun=sun, mode_grid=grid)
        elif dom == "time" and _TRIP.search(eid) and "trip_time" not in out:
            out["trip_time"] = eid
        elif (dom == "number" and (e.get("unit") or "").lower() in ("wh", "kwh") and re.search(r"fahrt|trip|next", eid, re.IGNORECASE)
              and "trip_energy" not in out):
            out["trip_energy"], out["trip_energy_unit"] = eid, e.get("unit")
        elif dom == "button" and re.search(r"start", eid, re.IGNORECASE) and not re.search(r"neustart|restart|reboot", eid, re.IGNORECASE):
            out.setdefault("start", eid)
        elif dom == "button" and re.search(r"stop", eid, re.IGNORECASE):
            out.setdefault("stop", eid)
    if out.get("mode") and out.get("mode_trip") and out.get("trip_time") and out.get("trip_energy"):
        out["variant"] = "trip"
    elif out.get("mode") and out.get("mode_grid"):
        out["variant"] = "mode"
    elif out.get("start") and out.get("stop"):
        out["variant"] = "buttons"
    return out


def trip_settings(charge_kwh: float | None, departure: datetime | None, now: datetime, unit: str | None) -> dict[str, Any] | None:
    """What to write into the wallbox's next-trip settings, or None (nothing needed in the next 24 hours: back to the sun mode)."""
    if not charge_kwh or charge_kwh < MIN_KWH or departure is None or not (now < departure <= now + TRIP_HORIZON):
        return None
    energy = round(charge_kwh * 1000) if (unit or "").lower() == "wh" else round(charge_kwh, 1)
    return {"time": departure.strftime("%H:%M:00"), "energy": energy}


def trip_energy_due(new_kwh: float, written: dict[str, Any] | None, soc_now: float | None, capacity_kwh: float,
                    efficiency: float) -> bool:
    """Must the next-trip energy be written again?

    The need falls while the car charges. Every new value makes a wallbox like the Wattpilot stop and plan again (field test
    16.11.2026: ten stops in 80 minutes, a third of the time lost). So a lower value that the charging since the last write explains
    is not written; a real change of the need (a new departure, the weekly full charge starts or ends, the car was driven) is.
    `written` = {"kwh", "soc"} of the last write, or None."""
    if not written or written.get("kwh") is None:
        return True
    charged = 0.0
    if soc_now is not None and written.get("soc") is not None:
        charged = max(0.0, float(soc_now) - float(written["soc"])) / 100.0 * capacity_kwh / max(0.1, efficiency)
    expected = max(0.0, float(written["kwh"]) - charged)
    return abs(float(new_kwh) - expected) >= TRIP_RESEND_KWH


def in_grid_window(windows: list[dict[str, Any]] | None, now: datetime) -> bool:
    """True while a planned window takes energy from the grid (more energy planned than the sun brings)."""
    for w in windows or []:
        try:
            start, end = w["start"], w["end"]
        except (KeyError, TypeError):
            continue
        if start <= now < end and float(w.get("energy_kwh") or 0) - float(w.get("available_kwh") or 0) >= 0.1:
            return True
    return False


def next_action(current: Any, wanted: Any, set_by_us: Any, original: Any) -> tuple[str | None, Any]:
    """('set', value) | ('restore', original) | (None, reason). `wanted` None = Plugwhen wants nothing (give back).
    Only what Plugwhen set itself is changed: if the value is neither ours nor untouched, the user changed it - leave it."""
    if wanted is not None:
        if current == wanted:
            return None, "same"
        if set_by_us is None or current == set_by_us:
            return "set", wanted
        return None, "user_changed"
    if set_by_us is not None and current == set_by_us and original is not None and original != current:
        return "restore", original
    return None, "nothing"
