"""Charging plan: in which quarter hours to charge (pure Python, no Home Assistant imports).

Input is the energy still to take from the wallbox (`need_kwh`, from `need.compute_need`), the departure, what the
wallbox can deliver and two optional curves per quarter hour:

* `available_kw`: power that is cheap or free for this household in that quarter hour, already net of the house load.
  It can come from anywhere (own solar forecast, an energy community, a tariff signal) through the availability
  interface; the planner does not care where.
* `load`: the expected grid import of the house (`typical`, `high`) together with the peak target `target_kw`; the
  planner then keeps the car's grid draw below the target.

Order of choice:

1. Quarter hours with available power come first (the one with most available power first): the sun, when there is any.
2. The rest is spread over the parking time with the lowest even grid import (behind the last planned sun quarter hour,
   if it fits there without a higher power and the whole need would fit there at the preferred power even if the sun
   failed: the battery
   keeps room for a sun stronger than forecast, and a sun that does not come costs nothing): house and car are topped up to one common
   level (quiet quarter hours get more, busy ones less or nothing), never above the peak target. Quarter hours where the
   car would get less than the wallbox minimum are dropped and the rest filled again (among equals the later ones stay:
   the battery waits less at a high state of charge). Households without solar get only this step.
3. Tiny remainders below the wallbox minimum go to the quietest quarter hours, the later one first.
4. If the energy cannot be delivered by departure the plan says so and how much is missing; it never pretends.

The plan is advice. Carrying it out is a separate, optional step.
"""

from __future__ import annotations

import math
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
    pref_kw: float | None = None,
    others_kw: dict[datetime, float] | None = None,
    blocked: set[datetime] | None = None,
    pref_kw2: float | None = None,
    early: bool = False,
) -> dict[str, Any]:
    """Return the plan. `load` is a list of quarter hours {t, typical, high, n}; quarter hours not listed there count as
    unknown (`DEFAULT_HIGH_KW`). `available_kw` maps a quarter-hour start to the usable available power in kW.
    `pref_kw`: the preferred lowest charging power (the car's charger wastes more below a few kW); the rest is spread no
    flatter than this, and only if the energy does not fit that way the wallbox minimum `min_kw` is used.
    `others_kw`: what other cars already planned per quarter hour; it takes the available power first, the rest counts as
    load of the house. `blocked`: quarter hours in which another car charges at a wallbox this car shares (left out).
    `pref_kw2`: a lower preferred power to try when the energy does not fit at `pref_kw` (compact charging: three quarters of
    the wallbox power, then the car's own preferred power, and only then the wallbox minimum).
    `early`: among equal quarter hours the earlier ones are used (where the height of the grid import costs nothing: the
    car is charged as soon as it is plugged in, so a car that charges slower than set still has the whole parking time)."""
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
        if frac > 0.05 and not (blocked and t in blocked):
            q = known.get(t)
            high = q["high"] if q is not None and q.get("high") is not None else DEFAULT_HIGH_KW
            avail = max(0.0, available_kw.get(t, 0.0)) if available_kw is not None else 0.0
            other = max(0.0, (others_kw or {}).get(t, 0.0))
            if other:   # another car charges then: it uses the available power first, the rest is load like the house
                high += max(0.0, other - avail)
                avail = max(0.0, avail - other)
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

    # 2. the rest spread over the parking time with the lowest even grid import (quiet quarter hours get more); no flatter
    #    than the preferred power, and only when that does not fit down to the wallbox minimum
    rest = [q for q in quarters if q["t"] not in plan]
    floor = max(min_kw, min(max_kw, pref_kw)) if pref_kw else min_kw
    floors = [floor]   # the lowest powers to try, one after the other: preferred, the lower preferred one, the minimum
    for lower in (max(min_kw, min(max_kw, pref_kw2)) if pref_kw2 else None, min_kw):
        if lower is not None and lower < floors[-1] - 1e-9:
            floors.append(lower)

    def spread_over(cands: list[dict[str, Any]]) -> tuple[dict[datetime, float], float, float]:
        """(power per quarter hour, energy delivered, the lowest power used): at the preferred power, else step by step down
        to the wallbox minimum (never straight to the minimum: a small need would be charged at the worst efficiency)."""
        s, d, low = {}, 0.0, floors[-1]
        for low in floors:
            s = _spread(cands, remaining, max_kw, low, target_kw, early)
            d = sum(pw * QUARTER_H * next(q for q in cands if q["t"] == ts)["frac"] for ts, pw in s.items())
            if remaining - d <= 0.1:
                break
        return s, d, low

    spread, _delivered, used_floor = spread_over(rest)
    # the sun first also in time: if sun is planned, the grid part goes behind the last sun quarter hour - when all of it fits
    # there and needs no higher power than it would otherwise (or than the preferred one). A battery filled from the grid in the
    # morning has no room left for a sun that turns out stronger than forecast.
    after_sun = [q for q in rest if q["t"] > max(plan)] if plan else []
    # ... and only if the WHOLE need would still fit behind the sun: a forecast is no promise, and if the sun fails the car
    # must be charged all the same. Counted at the preferred power, not at the wallbox's: the car may charge slower than the
    # wallbox is set (3.7 instead of 11 kW), and then the time behind the sun must still be enough.
    safe_kw = floors[-2] if len(floors) > 1 else floors[0]
    room_after = sum(min(safe_kw, _room(q, max_kw, min_kw, target_kw)) * QUARTER_H * q["frac"] for q in after_sun)
    if after_sun and len(after_sun) < len(rest) and remaining >= 0.05 and room_after >= need_kwh:
        s, d, f = spread_over(after_sun)
        if remaining - d <= 0.1 and max(s.values(), default=0.0) <= max(max(spread.values(), default=0.0), floor) + 0.05:
            spread, used_floor = s, f
    result["spread_floor_kw"] = used_floor
    for t, p in spread.items():
        put(next(q for q in rest if q["t"] == t), p)

    # 3. what is still missing (tiny amounts below the wallbox minimum): the quietest quarter hours, the later one first
    for q in sorted(quarters, key=lambda x: (x["high"], x["t"].timestamp() if early else -x["t"].timestamp())):
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


def _room(q: dict[str, Any], max_kw: float, min_kw: float, target_kw: float | None) -> float:
    """The most the car can charge in this quarter hour (below the peak target, if there is one); 0 if less than the wallbox minimum."""
    room = min(max_kw, max_kw if target_kw is None else target_kw - q["high"] + q["avail"])
    return room if room >= min_kw else 0.0


def _spread(quarters: list[dict[str, Any]], energy: float, max_kw: float, min_kw: float,
            target_kw: float | None, early: bool = False) -> dict[datetime, float]:
    """Fill the quarter hours like water: the car tops up the expected import of the house to one common level, so the
    highest import (and with it the peak) stays as low as possible. Quarter hours where the car would get less than
    the wallbox minimum are dropped (the busiest and earliest first) and the rest is filled again."""
    if energy < 0.05:
        return {}

    def cap(q: dict[str, Any]) -> float:
        room = max_kw if target_kw is None else target_kw - q["high"] + q["avail"]
        return min(max_kw, room)

    cand = [q for q in quarters if cap(q) >= min_kw]
    while cand:
        base = {q["t"]: q["high"] - q["avail"] for q in cand}
        caps = {q["t"]: cap(q) for q in cand}

        def power(q: dict[str, Any], level: float) -> float:
            return min(caps[q["t"]], max(0.0, level - base[q["t"]]))

        def energy_at(level: float) -> float:
            return sum(power(q, level) * QUARTER_H * q["frac"] for q in cand)

        lo, hi = min(base.values()), max(base[t] + caps[t] for t in base)
        if energy_at(hi) <= energy:     # everything at its maximum and still not enough
            return {q["t"]: caps[q["t"]] for q in cand}
        for _ in range(40):
            mid = (lo + hi) / 2
            if energy_at(mid) < energy:
                lo = mid
            else:
                hi = mid
        result = {q["t"]: power(q, hi) for q in cand}
        low = [q for q in cand if result[q["t"]] < min_kw - 1e-6]
        if not low:
            return result
        # busiest go first, then the earliest (the later ones stay) - or, with `early`, the latest (the earlier ones stay)
        low.sort(key=lambda q: (-base[q["t"]], -q["t"].timestamp() if early else q["t"].timestamp()))
        short = sum(min_kw - result[q["t"]] for q in low) / (min_kw * len(low))    # how far below the minimum, 0..1
        drop = {q["t"] for q in low[: max(1, math.ceil(len(low) * short))]}
        cand = [q for q in cand if q["t"] not in drop]
    return {}


def charging_allowed(plan: dict[str, Any], now: datetime) -> bool | None:
    """True if the plan wants the car to charge in the quarter hour containing `now`, False if it wants a pause,
    None if the plan does not decide (not needed, infeasible, no departure): charging then stays as it is."""
    if plan.get("status") != "planned":
        return None
    q = now.replace(minute=(now.minute // 15) * 15, second=0, microsecond=0)
    return q in plan.get("quarters", {})
