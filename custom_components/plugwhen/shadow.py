"""Learn mode: what Plugwhen WOULD switch, written down and compared with what really happened (pure Python).

In learn mode nothing is switched. For every moment Plugwhen works out the decision it would take (`decide`): charge, pause, or
no decision, with the reason. `ShadowLog` writes the changes down (a short journal) and, for every day, adds up how the
decision compares with reality: how long the wallbox was charging while Plugwhen would have paused, how much energy came in
those minutes, and the other way round. That is the evidence on which switching can be suggested later, and the owner can read
it at any time: "would have paused 3 h, but 9 kWh came in".

Unknown things never become decisions: unknown state of charge, a car that is not plugged in, a plan that is not needed or has
no departure give "no decision" (`none`) and the wallbox keeps doing what it does.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

QUARTER = timedelta(minutes=15)
MAX_GAP = timedelta(minutes=20)    # a longer gap (restart, outage) is not attributed to the last state
JOURNAL_KEEP = 60
DAYS_KEEP = 60
SECONDS_KEYS = ("charge_charging", "charge_idle", "pause_charging", "pause_idle")
ENERGY_KEYS = ("kwh_charge", "kwh_pause")


def _quarter(t: datetime) -> datetime:
    return t.replace(minute=(t.minute // 15) * 15, second=0, microsecond=0)


@dataclass(frozen=True)
class Decision:
    action: str                        # "charge", "pause" or "none" (no decision)
    reason: str                        # key, translated by the dashboard
    kw: float | None = None            # planned power of the running quarter hour (charge)
    until: datetime | None = None      # when the decision is expected to change


def decide(plan: dict[str, Any] | None, now: datetime, plugged: bool | None, soc_known: bool) -> Decision:
    """The decision Plugwhen would take for `now` from the charge plan (see plan.make_plan)."""
    if not soc_known:
        return Decision("none", "unknown_soc")
    if plugged is False:
        return Decision("none", "not_plugged")
    status = (plan or {}).get("status")
    if status == "infeasible":
        return Decision("charge", "cannot_reach_target")       # as much as possible, at once: never wait when time is short
    if status != "planned":
        return Decision("none", "not_needed" if status == "not_needed" else "no_plan")
    quarters: dict[datetime, float] = plan.get("quarters") or {}
    q = _quarter(now)
    if q in quarters:
        end = q + QUARTER
        while end in quarters:
            end += QUARTER
        return Decision("charge", "in_window", quarters[q], end)
    later = sorted(t for t in quarters if t > q)
    if later:
        return Decision("pause", "waiting_for_window", None, later[0])
    return Decision("pause", "plan_done")


def _empty_day() -> dict[str, float]:
    return {k: 0.0 for k in SECONDS_KEYS + ENERGY_KEYS}


class ShadowLog:
    """Journal of decisions and the daily comparison with reality. Small, kept in a Store."""

    def __init__(self, data: dict[str, Any] | None = None) -> None:
        d = data if isinstance(data, dict) else {}
        self.journal: list[dict[str, Any]] = [x for x in d.get("journal", []) if isinstance(x, dict)]
        self.days: dict[str, dict[str, float]] = {
            k: {**_empty_day(), **{a: float(b) for a, b in v.items() if a in SECONDS_KEYS + ENERGY_KEYS}}
            for k, v in (d.get("days") or {}).items() if isinstance(v, dict)
        }
        self._last: tuple[datetime, str | None, bool | None, float | None] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"journal": self.journal, "days": self.days}

    def update(self, now: datetime, decision: Decision | None, charging: bool | None, energy_kwh: float | None) -> bool:
        """Note the decision of this moment and attribute the time since the last call to the previous state. `charging` is
        the real state of the wallbox (None if unknown), `energy_kwh` the wallbox energy counter. Returns True if anything
        changed (then the log should be saved)."""
        changed = False
        if decision is not None:
            last = self.journal[-1] if self.journal else None
            if last is None or last.get("action") != decision.action or last.get("reason") != decision.reason:
                self.journal.append({"t": now.isoformat(), "action": decision.action, "reason": decision.reason, "kw": decision.kw})
                del self.journal[:-JOURNAL_KEEP]
                changed = True
        if self._last is not None:
            t0, a0, c0, e0 = self._last
            dt = now - t0
            if timedelta(0) < dt <= MAX_GAP and a0 in ("charge", "pause"):
                day = self.days.setdefault(t0.date().isoformat(), _empty_day())
                if c0 is not None:
                    day[f"{a0}_{'charging' if c0 else 'idle'}"] += dt.total_seconds()
                    changed = True
                if energy_kwh is not None and e0 is not None and energy_kwh >= e0:
                    day[f"kwh_{a0}"] += energy_kwh - e0
                    changed = True
        self._last = (now, decision.action if decision else None, charging, energy_kwh)
        for old in sorted(self.days)[:-DAYS_KEEP]:
            del self.days[old]
        return changed

    def summary(self, now: datetime, days: int = 7) -> dict[str, Any]:
        """How decision and reality compare over the last `days`: share of the time they agreed, hours the wallbox charged
        although Plugwhen would have paused (and the energy that came in), hours it was idle in a planned window."""
        since = (now - timedelta(days=days)).date().isoformat()
        tot: dict[str, float] = defaultdict(float)
        seen = 0
        for d, v in self.days.items():
            if d >= since:
                seen += 1 if any(v[k] for k in SECONDS_KEYS + ENERGY_KEYS) else 0
                for k, x in v.items():
                    tot[k] += x
        decided = sum(tot[k] for k in SECONDS_KEYS)
        agree = tot["charge_charging"] + tot["pause_idle"]
        return {
            "days": seen,
            "agree_pct": round(100 * agree / decided) if decided > 0 else None,
            "pause_but_charging_h": round(tot["pause_charging"] / 3600, 1),
            "charge_but_idle_h": round(tot["charge_idle"] / 3600, 1),
            "kwh_in_pause": round(tot["kwh_pause"], 1),
            "kwh_in_charge": round(tot["kwh_charge"], 1),
        }
