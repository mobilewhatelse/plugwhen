"""Does the learning bring anything for THIS car? (pure Python, no Home Assistant imports)

The history of the car is walked through day by day; before each day the model only knows the days before it. For every day
two questions are answered:

* **Would the range have been enough?** With the fixed reserve alone (what a car without learning would keep) and with the
  reserve lifted by what was learned for that weekday (the larger of the reserve and the weekday's 80th percentile).
* **Was the departure guessed right?** The learned usual hour of the first trip against the real one, within one hour
  (the history knows the hour, not the minute).
* **Would the car have been ready in time?** A plan that finishes at the learned departure is late whenever the car left
  earlier. Counted for the median hour and for the early hour (20th percentile) the plan now aims at.

From that comes one plain verdict: `learning_helps` (the learned value covers at least 5 points more days than the reserve
alone), `reserve_enough` (less than 2 points: the reserve alone does it), `little` in between, `too_little_data` (fewer than
21 days could be checked). Nothing is invented: a day without kilometres is not counted.
"""

from __future__ import annotations

from typing import Any

try:  # inside Home Assistant the module lives in a package, the tests import it flat
    from .learning import MIN_DRIVE_KM, DayRecord, MobilityModel
except ImportError:  # pragma: no cover
    from learning import MIN_DRIVE_KM, DayRecord, MobilityModel

WARMUP_DAYS = 28          # days the model sees before the first day is checked
MIN_CHECKED_DAYS = 21
HELPS_POINTS = 0.05
SAME_POINTS = 0.02
DEPARTURE_TOLERANCE_H = 1.0


def learning_check(records: list[DayRecord], reserve_km: float, warmup_days: int = WARMUP_DAYS) -> dict[str, Any]:
    model = MobilityModel()
    checked = covered_reserve = covered_learned = 0
    dep = {wd: [0, 0] for wd in range(7)}          # weekday -> [right, checked]
    ready_median = ready_early = 0
    for i, rec in enumerate(sorted(records, key=lambda r: r.day)):
        km = rec.clean_km()
        if i >= warmup_days:
            p = model.plan(rec.day.weekday())
            if km is not None and p.km_high is not None:
                checked += 1
                covered_reserve += km <= reserve_km
                covered_learned += km <= max(reserve_km, p.km_high)
            if km is not None and km >= MIN_DRIVE_KM and rec.first_move_hour is not None and p.departure_hour is not None:
                wd = rec.day.weekday()
                dep[wd][1] += 1
                dep[wd][0] += abs(p.departure_hour - rec.first_move_hour) <= DEPARTURE_TOLERANCE_H
                ready_median += rec.first_move_hour >= p.departure_hour          # finished at the median: in time?
                early = p.departure_early if p.departure_early is not None else p.departure_hour
                ready_early += rec.first_move_hour >= early
        model.add_day(rec)

    reserve = covered_reserve / checked if checked else None
    learned = covered_learned / checked if checked else None
    dep_total = sum(v[1] for v in dep.values())
    dep_right = sum(v[0] for v in dep.values())
    if checked < MIN_CHECKED_DAYS:
        verdict = "too_little_data"
    else:
        gain = learned - reserve
        verdict = "learning_helps" if gain >= HELPS_POINTS else "reserve_enough" if gain < SAME_POINTS else "little"
    return {
        "verdict": verdict,
        "days": checked,
        "reserve_km": reserve_km,
        "coverage_reserve_pct": round(100 * reserve) if reserve is not None else None,
        "coverage_learned_pct": round(100 * learned) if learned is not None else None,
        "gain_points": round(100 * (learned - reserve)) if checked else None,
        "departure_right_pct": round(100 * dep_right / dep_total) if dep_total else None,
        "departure_days": dep_total,
        "ready_median_pct": round(100 * ready_median / dep_total) if dep_total else None,
        "ready_early_pct": round(100 * ready_early / dep_total) if dep_total else None,
        "departure_by_weekday": [
            {"weekday": wd, "days": n, "right_pct": round(100 * ok / n) if n else None} for wd, (ok, n) in sorted(dep.items())
        ],
    }
