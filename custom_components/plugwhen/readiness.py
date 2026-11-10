"""Ready to switch? (pure Python) A checklist that says when Plugwhen may switch the wallbox itself (mode "direct", later):
only after the learn mode has shown that its decisions match what really happened. Until then it only plans, warns and - in mode
"evcc" - hands the plan to evcc.

Checks: the trips are learned (every weekday the car is used has enough examples), enough days with a comparison (days on which
Plugwhen would have charged or paused), the decisions agreed often enough, and - only with a solar plant - the solar forecast was
checked against what the plant really produced.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

MIN_SAMPLES = 3          # examples per weekday the car is used
MIN_COMPARE_DAYS = 7     # days with a comparison of decision and reality
MIN_AGREE_PCT = 80       # share of the decided time in which reality did the same
MIN_SOLAR_DAYS = 5       # days the solar forecast was checked (only with a solar plant)
DAYS_PER_COMPARE_DAY = 2.0   # rough: a car is charged on about every second day


def switch_readiness(weekdays: list[dict[str, Any]], compare_days: int, agree_pct: float | None, solar_days: int | None,
                     now: datetime) -> dict[str, Any]:
    """`weekdays` = [{"weekday", "samples", "used"}] (used = the car is driven on that weekday), `solar_days` None = no solar plant.
    Returns {"ready", "checks": [{"key", "ok", "value", "need"}], "estimate": ISO date or None}."""
    used = [d for d in weekdays if d.get("used")]
    learned = sum(1 for d in used if (d.get("samples") or 0) >= MIN_SAMPLES)
    checks = [
        {"key": "trips", "ok": bool(used) and learned == len(used), "value": learned, "need": len(used) or None},
        {"key": "compare_days", "ok": compare_days >= MIN_COMPARE_DAYS, "value": compare_days, "need": MIN_COMPARE_DAYS},
        {"key": "agree", "ok": agree_pct is not None and agree_pct >= MIN_AGREE_PCT and compare_days >= MIN_COMPARE_DAYS,
         "value": agree_pct, "need": MIN_AGREE_PCT},
    ]
    if solar_days is not None:
        checks.append({"key": "solar", "ok": solar_days >= MIN_SOLAR_DAYS, "value": solar_days, "need": MIN_SOLAR_DAYS})
    ready = all(c["ok"] for c in checks)
    estimate = None
    if not ready:
        waits = [max(0, MIN_COMPARE_DAYS - compare_days) * DAYS_PER_COMPARE_DAY]
        if solar_days is not None:
            waits.append(max(0, MIN_SOLAR_DAYS - solar_days))
        days = max(waits)
        if days > 0:
            estimate = (now + timedelta(days=days)).date().isoformat()
    return {"ready": ready, "checks": checks, "estimate": estimate}
