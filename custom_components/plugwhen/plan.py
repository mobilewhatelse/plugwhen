"""Charging plan: in which quarter hours to charge (pure Python, no Home Assistant imports).

Input is the energy still to take from the wallbox (`need_kwh`, from `need.compute_need`), the departure, what the
wallbox can deliver and two optional curves per quarter hour:

* `available_kw`: power that is cheap or free for this household in that quarter hour, already net of the house load.
  It can come from anywhere (own solar forecast, an energy community, a tariff signal) through the availability
  interface; the planner does not care where.
* `load`: the expected grid import of the house (`typical`, `high`) together with the peak target `target_kw`; the
  planner then keeps the car's grid draw below the target.

Order of choice:

1. Quarter hours with available power come first (the one with most available power first).
2. The rest goes to the quietest quarter hours (lowest expected import) that still stay under the peak target.
   Without a peak target all quarter hours count equally, and among equals the later one wins (the battery waits
   less time at a high state of charge before it is used).
3. If the energy cannot be delivered by departure the plan says so and how much is missing; it never pretends.

The plan is advice. Carrying it out is a separate, optional step.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

QUARTER_H = 0.25
DEFAULT_HIGH_KW = 1.0  # expected import for a quarter hour without learned data


def make_plan(
    now: datetime,
    departure: datetime,
    need_kwh: float,
    max_kw: float,
    min_kw: float,
    *,
    load: list[dict[str, Any]] | None = None,
    target_kw: float | None = None,
    available_kw: dict[datetime, float] | None = None,
) -> dict[str, Any]:
    """Return the plan. `load` is a list of quarter hours {t, typical, high, n}; quarter hours not listed there count as
    unknown (`DEFAULT_HIGH_KW`). `available_kw` maps a quarter-hour start to the usable available power in kW."""
    result: dict[str, Any] = {
        "status": "planned", "needed_kwh": round(need_kwh, 2), "planned_kwh": 0.0, "available_kwh": 0.0, "grid_kwh": 0.0,
        "shortfall_kwh": 0.0, "windows": [], "quarters": {}, "ready_at": None, "latest_start": None,
        "availability_used": available_kw is not None, "departure": departure,
    }
    if departure <= now:
        result["status"] = "no_departure"
        return result
    if need_kwh < 0.05:
        result["status"] = "not_needed"
        return result
    if max_kw <= 0:
        result["status"] = "infeasible"
        result["shortfall_kwh"] = round(need_kwh, 2)
        return result
    result["latest_start"] = departure - timedelta(hours=need_kwh / max_kw)

    known = {q["t"]: q for q in (load or [])}
    first = now.replace(minute=(now.minute // 15) * 15, second=0, microsecond=0)
    quarters = []
    t = first
    while t < departure:
        end = t + timedelta(minutes=15)
        frac = (min(end, departure) - max(t, now)).total_seconds() / 900.0
        if frac > 0.05:
            q = known.get(t)
            high = q["high"] if q is not None and q.get("high") is not None else DEFAULT_HIGH_KW
            avail = max(0.0, available_kw.get(t, 0.0)) if available_kw is not None else 0.0
            quarters.append({"t": t, "frac": frac, "high": high, "avail": avail})
        t = end

    plan: dict[datetime, dict[str, float]] = {}
    remaining = need_kwh

    def put(q: dict[str, Any], p: float) -> None:
        nonlocal remaining
        plan[q["t"]] = {"kw": p, "avail": min(p, q["avail"]), "frac": q["frac"], "grid": max(0.0, p - q["avail"])}
        remaining -= p * QUARTER_H * q["frac"]

    # 1. available power first
    for q in sorted(quarters, key=lambda x: -x["avail"]):
        if remaining < 0.05 or q["avail"] < min_kw:
            continue
        put(q, max(min_kw, min(max_kw, q["avail"], remaining / (QUARTER_H * q["frac"]))))

    # 2. the quietest quarter hours that stay under the peak target; among equals the later one
    for q in sorted(quarters, key=lambda x: (x["high"], -x["t"].timestamp())):
        if remaining < 0.05:
            break
        if q["t"] in plan:
            continue
        room = max_kw if target_kw is None else target_kw - q["high"] + q["avail"]
        if room < min_kw:
            continue
        put(q, max(min_kw, min(max_kw, room, remaining / (QUARTER_H * q["frac"]))))

    total = sum(v["kw"] * QUARTER_H * v["frac"] for v in plan.values())
    avail = sum(v["avail"] * QUARTER_H * v["frac"] for v in plan.values())
    result.update({
        "planned_kwh": round(total, 2), "available_kwh": round(avail, 2), "grid_kwh": round(max(0.0, total - avail), 2),
        "shortfall_kwh": round(max(0.0, remaining), 2),
        "quarters": {t: round(v["kw"], 2) for t, v in plan.items()},
    })
    if remaining > 0.1:
        result["status"] = "infeasible"

    cur: dict[str, Any] | None = None
    for t in sorted(plan):
        v = plan[t]
        end = t + timedelta(minutes=15)
        e, a = v["kw"] * QUARTER_H * v["frac"], v["avail"] * QUARTER_H * v["frac"]
        if cur is not None and cur["end"] == t:
            cur["end"] = end
            cur["energy_kwh"] += e
            cur["available_kwh"] += a
            cur["peak_kw"] = max(cur["peak_kw"], v["kw"])
        else:
            cur = {"start": t, "end": end, "energy_kwh": e, "available_kwh": a, "peak_kw": v["kw"]}
            result["windows"].append(cur)
    for w in result["windows"]:
        for k in ("energy_kwh", "available_kwh", "peak_kw"):
            w[k] = round(w[k], 2)
    if result["windows"]:
        result["ready_at"] = result["windows"][-1]["end"]
    return result


def charging_allowed(plan: dict[str, Any], now: datetime) -> bool | None:
    """True if the plan wants the car to charge in the quarter hour containing `now`, False if it wants a pause,
    None if the plan does not decide (not needed, infeasible, no departure): charging then stays as it is."""
    if plan.get("status") != "planned":
        return None
    q = now.replace(minute=(now.minute // 15) * 15, second=0, microsecond=0)
    return q in plan.get("quarters", {})
