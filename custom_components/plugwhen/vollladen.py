"""Once a week full (pure Python, no Home Assistant imports).

A switch per car; the allowed days (e.g. Saturday and Sunday) and the target (e.g. 100 %) are settings. Rules (wish of a user, 15.11.2026):

* Once per week (Monday to Sunday), even if several days are allowed. Done as soon as the car reached the target that week.
* With a solar forecast the day with the most expected sun among the allowed days still ahead this week is chosen; without
  one (no PV) the first of them. Days the forecast does not reach count as no sun, so a later day can still win once the
  forecast reaches it (the choice is made again every run).
* The grid is allowed: what the sun does not deliver comes from the grid, so the target is reached (not everybody has PV).
  The planner already takes the sunny quarter hours first and the rest in the quietest ones before the departure, so the
  battery is full shortly before the car leaves and does not sit at 100 % for long.
* It counts for a plan whose time until the departure includes the chosen day. Without a departure: full by the evening of
  the chosen day (EVENING_H).
* Once it counts for a departure, it is kept until that departure (a few hours later if the departure moves), also past
  midnight and into the next week (bug 16.11.2026: chosen Sunday, departure Monday morning, the planner charges in the
  night, at midnight the full target was gone and the car got only the normal target). Done is booked for the week of the
  chosen day.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

DAY_SETS: dict[str, tuple[int, ...]] = {
    "weekend": (5, 6),
    "saturday": (5,),
    "sunday": (6,),
    "friday_sunday": (4, 5, 6),
    "any_day": (0, 1, 2, 3, 4, 5, 6),
}
DEFAULT_DAYS = "weekend"
DEFAULT_DAY_SET: frozenset[int] = frozenset(DAY_SETS[DEFAULT_DAYS])
DAY_SHORT = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")


def days_of(old_option: str | None) -> frozenset[int] | None:
    """The weekdays of a former selection ("weekend", "friday_sunday" …), None if unknown. Since 0.9.2 the days are one switch
    per weekday; this carries an existing choice over."""
    return frozenset(DAY_SETS[old_option]) if old_option in DAY_SETS else None


def days_text(days) -> str:
    """'Sa,So' for the bug report."""
    return ",".join(DAY_SHORT[d] for d in sorted(days or ())) or "keiner"
DEFAULT_TARGET = 100.0
EVENING_H = 20           # without a departure: full by this hour of the chosen day
DONE_MARGIN = 1.0        # the target counts as reached this many percent below it (cars often stop at 99 %)
HOLD_SLACK_H = 3         # a kept full charge also covers a departure that moved this many hours later


def week_key(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def sun_kwh_per_day(available_kw: dict[datetime, float] | None) -> dict[date, float]:
    """Expected available energy per day from the quarter-hour curve (kW per quarter hour)."""
    out: dict[date, float] = {}
    for t, kw in (available_kw or {}).items():
        out[t.date()] = out.get(t.date(), 0.0) + max(0.0, float(kw)) * 0.25
    return out


def choose_day(today: date, days, available_kw: dict[datetime, float] | None, done_week: str | None) -> date | None:
    """The day of this week for the full charge, or None (done this week, or no allowed day left this week, or no day ticked).
    `days` = the ticked weekdays (0=Monday), or a former selection name."""
    if done_week == week_key(today):
        return None
    allowed = DAY_SETS.get(days or DEFAULT_DAYS, DAY_SETS[DEFAULT_DAYS]) if isinstance(days, str) or days is None else tuple(days)
    ahead = [today + timedelta(days=k) for k in range(7 - today.weekday()) if (today + timedelta(days=k)).weekday() in allowed]
    if not ahead:
        return None
    sun = sun_kwh_per_day(available_kw)
    if not any(sun.get(d, 0.0) > 0.05 for d in ahead):
        return ahead[0]
    return max(ahead, key=lambda d: (round(sun.get(d, 0.0), 1), -d.toordinal()))   # most sun; among equals the earlier day


def applies(now: datetime, departure: datetime | None, day: date | None) -> bool:
    """Does the full charge count for the plan from now to this departure?"""
    if day is None or now.date() > day:
        return False
    if departure is None:
        return now.date() == day and now.hour < EVENING_H
    return departure.date() >= day


def held(now: datetime, hold_until: datetime | None) -> bool:
    """Is a full charge that once counted for a departure still kept?"""
    return hold_until is not None and now < hold_until + timedelta(hours=HOLD_SLACK_H)


def applies_held(now: datetime, departure: datetime | None, hold_until: datetime | None) -> bool:
    """Does the kept full charge count for the plan to this departure (the kept one, or one that moved a little later)?"""
    return (departure is not None and held(now, hold_until)
            and departure <= hold_until + timedelta(hours=HOLD_SLACK_H))


def evening(day: date, tzinfo) -> datetime:
    return datetime(day.year, day.month, day.day, EVENING_H, 0, tzinfo=tzinfo)


def reached(soc: float | None, target: float) -> bool:
    return soc is not None and soc >= target - DONE_MARGIN
