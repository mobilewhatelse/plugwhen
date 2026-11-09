"""What Plugwhen WOULD write into evcc as a charging plan (pure Python). Nothing is written yet: this is shown in learn mode so the
plan can be compared with evcc's own plan before Plugwhen is ever allowed to set it.

evcc's plan of a vehicle is a target state of charge and a time (`POST /api/vehicles/<name>/plan/soc/<soc>/<time>` sets it, `GET /api/state`
shows it under `vehicles.<key>.plan`). Plugwhen's proposal is its own target for the coming departure. Rule for later, visible now:
a plan that is already set in evcc and differs is the user's own plan and would never be overwritten.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

SAME_SOC_PCT = 1.0        # targets within this are the same
SAME_TIME_MIN = 15.0      # times within this are the same


def _parse(t: Any) -> datetime | None:
    if isinstance(t, datetime):
        return t
    try:
        d = datetime.fromisoformat(str(t).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return d if d.tzinfo is not None else None


def current_plan(state: dict[str, Any] | None, key: str) -> dict[str, Any] | None:
    """evcc's plan of vehicle `key`: {"soc", "time"} or None (no plan, or a plan without a time)."""
    v = ((state or {}).get("vehicles") or {}).get(key)
    p = v.get("plan") if isinstance(v, dict) else None
    if not isinstance(p, dict):
        return None
    t = _parse(p.get("time"))
    try:
        soc = float(p.get("soc"))
    except (TypeError, ValueError):
        return None
    if t is None or soc <= 0:
        return None
    return {"soc": round(soc), "time": t.isoformat()}


def proposal(target_soc: float | None, soc: float | None, departure: datetime | None, now: datetime) -> tuple[dict[str, Any] | None, str]:
    """(plan to write or None, reason). The plan is the target rounded up to a whole percent at the departure."""
    if departure is None or departure <= now:
        return None, "no_departure"
    if soc is None:
        return None, "unknown_soc"
    if target_soc is None:
        return None, "no_target"
    if target_soc <= soc:
        return None, "not_needed"
    return {"soc": min(100, int(math.ceil(target_soc - 1e-9))), "time": departure.isoformat()}, "planned"


def same(a: dict[str, Any] | None, b: dict[str, Any] | None) -> bool:
    if not a or not b:
        return False
    ta, tb = _parse(a.get("time")), _parse(b.get("time"))
    if ta is None or tb is None:
        return False
    return abs(float(a["soc"]) - float(b["soc"])) <= SAME_SOC_PCT and abs((ta - tb).total_seconds()) <= SAME_TIME_MIN * 60


def evcc_plan(state: dict[str, Any] | None, key: str | None, target_soc: float | None, soc: float | None,
              departure: datetime | None, now: datetime, written: bool = False) -> dict[str, Any] | None:
    """The comparison for the dashboard, or None without an evcc car. `own_plan`: evcc already has a different plan (set by hand
    or by evcc itself); Plugwhen would leave it alone. `written` stays False until Plugwhen may write (not in learn mode)."""
    if not key:
        return None
    would, reason = proposal(target_soc, soc, departure, now)
    cur = current_plan(state, key) if state is not None else None
    match = same(would, cur)
    return {
        "would_write": would,
        "reason": reason,
        "current": cur,
        "evcc_known": state is not None,
        "same": match,
        "own_plan": bool(cur) and not match,
        "written": bool(written),
    }
