"""What Plugwhen WOULD write into evcc (pure Python). Nothing is written yet: this is shown in learn mode so the plans can be compared
with evcc's own ones before Plugwhen is ever allowed to set them.

Two kinds, both as evcc knows them:

* **the plan for the next departure that needs charging** (evcc: one plan per vehicle, a target state of charge and a time). It comes from
  Plugwhen's look-ahead, so it is written early - "34 % by Friday 07:00" already on Monday - and follows what happens: more driving raises
  it, charging with the sun in between drops it, after Friday the next needed departure takes its place. evcc then charges in time as
  soon as the car is plugged in. (`POST /api/vehicles/<name>/plan/soc/<soc>/<time>`; shown in `GET /api/state` under `vehicles.<key>.plan`.)
* **repeating plans per weekday** from the learned week (evcc: `repeatingPlans`, weekdays + time + target). Equal times and targets are
  grouped ("Tue-Fri 07:00 33 %").

Rule for later, visible now: a plan already set in evcc that differs is the user's own plan and would never be overwritten.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

SAME_SOC_PCT = 1.0        # targets within this are the same
SAME_TIME_MIN = 15.0      # times within this are the same


def _parse(t: Any) -> datetime | None:
    if isinstance(t, datetime):
        return t if t.tzinfo is not None else None
    try:
        d = datetime.fromisoformat(str(t).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return d if d.tzinfo is not None else None


def _soc(v: Any) -> int | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return min(100, int(math.ceil(f - 1e-9))) if f > 0 else None


def current_plan(state: dict[str, Any] | None, key: str) -> dict[str, Any] | None:
    """evcc's one-time plan of vehicle `key`: {"soc", "time"} or None (no plan, or a plan without a time)."""
    v = ((state or {}).get("vehicles") or {}).get(key)
    p = v.get("plan") if isinstance(v, dict) else None
    if not isinstance(p, dict):
        return None
    t, soc = _parse(p.get("time")), _soc(p.get("soc"))
    if t is None or soc is None:
        return None
    return {"soc": round(float(p.get("soc"))), "time": t.isoformat()}


def current_weekly(state: dict[str, Any] | None, key: str) -> list[dict[str, Any]]:
    """evcc's repeating plans of vehicle `key`, weekdays converted to Plugwhen's (0 = Monday; evcc counts 0 = Sunday)."""
    v = ((state or {}).get("vehicles") or {}).get(key)
    raw = v.get("repeatingPlans") if isinstance(v, dict) else None
    out = []
    for p in raw if isinstance(raw, list) else []:
        if not isinstance(p, dict):
            continue
        days = sorted({(int(d) + 6) % 7 for d in p.get("weekdays") or [] if str(d).lstrip("-").isdigit()})
        soc = _soc(p.get("soc"))
        if days and soc is not None and isinstance(p.get("time"), str):
            out.append({"weekdays": days, "time": p["time"][:5], "soc": soc, "active": bool(p.get("active", True))})
    return out


def hhmm(hour: float) -> str:
    h = int(hour)
    m = int(round((hour - h) * 60))
    if m == 60:
        h, m = h + 1, 0
    return f"{h % 24:02d}:{m:02d}"


def weekly_plans(week: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Repeating plans from the learned week: `week` = [{"weekday", "hour", "target_soc"}] for the weekdays with a departure.
    Equal time and target are grouped, sorted by the first weekday."""
    groups: dict[tuple[str, int], list[int]] = {}
    for d in week:
        soc = _soc(d.get("target_soc"))
        if soc is None or d.get("hour") is None:
            continue
        groups.setdefault((hhmm(float(d["hour"])), soc), []).append(int(d["weekday"]))
    out = [{"weekdays": sorted(days), "time": t, "soc": s} for (t, s), days in groups.items()]
    return sorted(out, key=lambda p: (p["weekdays"][0], p["time"]))


def same(a: dict[str, Any] | None, b: dict[str, Any] | None) -> bool:
    if not a or not b:
        return False
    ta, tb = _parse(a.get("time")), _parse(b.get("time"))
    if ta is None or tb is None:
        return False
    return abs(float(a["soc"]) - float(b["soc"])) <= SAME_SOC_PCT and abs((ta - tb).total_seconds()) <= SAME_TIME_MIN * 60


def same_weekly(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> bool:
    """Both repeating plans cover the same weekdays with the same times and targets (inactive evcc plans do not count)."""
    def days(plans):
        return {d: (p["time"], p["soc"]) for p in plans if p.get("active", True) for d in p["weekdays"]}
    da, db = days(a), days(b)
    if not da or da.keys() != db.keys():
        return False
    return all(da[d][0] == db[d][0] and abs(da[d][1] - db[d][1]) <= SAME_SOC_PCT for d in da)


def decide_write(would: dict[str, Any] | None, current: dict[str, Any] | None, last_written: dict[str, Any] | None) -> tuple[str | None, str]:
    """("set" | "delete" | None, reason). Plugwhen only touches a plan it wrote itself: a plan in evcc that is not the last one Plugwhen
    wrote is the user's own and is left alone. Nothing is written when evcc already has the same plan."""
    if current and not same(current, last_written):
        return None, "own_plan"
    if would:
        return (None, "same") if same(would, current) else ("set", "update" if current else "new")
    if current and same(current, last_written):
        return "delete", "not_needed_anymore"
    return None, "nothing"


def evcc_plan(state: dict[str, Any] | None, key: str | None, ahead: dict[str, Any] | None, week: list[dict[str, Any]],
              now: datetime, reason: str = "planned", lasts_until: str | None = None, written: bool = False,
              last_written: dict[str, Any] | None = None, write_enabled: bool = False) -> dict[str, Any] | None:
    """The comparison for the dashboard, or None without an evcc car.

    `ahead` = {"departure": datetime, "target_soc": float} for the first departure of the look-ahead that needs charging, or None (then
    `reason` says why: "covered" = the charge lasts the whole look-ahead (until `lasts_until`), "unknown_soc", "no_departure").
    `week` = the learned departures per weekday (see `weekly_plans`). `own_plan`: evcc already has a different one-time plan (set by
    hand or by evcc itself); Plugwhen would leave it alone. `written` stays False until Plugwhen may write (not in learn mode)."""
    if not key:
        return None
    would = None
    if ahead is not None:
        dep, soc = _parse(ahead.get("departure")), _soc(ahead.get("target_soc"))
        if dep is not None and dep > now and soc is not None:
            would = {"soc": soc, "time": dep.isoformat()}
        else:
            reason = "no_departure" if dep is None or dep <= now else "no_target"
    elif reason == "planned":
        reason = "covered"
    cur = current_plan(state, key) if state is not None else None
    match = same(would, cur)
    mine = bool(cur) and same(cur, last_written)
    weekly = weekly_plans(week)
    weekly_cur = current_weekly(state, key) if state is not None else []
    return {
        "would_write": would,
        "reason": "planned" if would else reason,
        "lasts_until": lasts_until if not would else None,
        "current": cur,
        "evcc_known": state is not None,
        "same": match,
        "own_plan": bool(cur) and not match and not mine,
        "by_plugwhen": mine,
        "write_enabled": bool(write_enabled),
        "weekly": weekly,
        "weekly_current": weekly_cur,
        "weekly_same": same_weekly(weekly, weekly_cur),
        "written": bool(written) or (mine and match),
    }
