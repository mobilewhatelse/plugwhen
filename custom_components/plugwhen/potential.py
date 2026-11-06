"""Potential calculator: what would spreading the charging bring in this household? (pure Python, no Home Assistant imports)

It replays the household's own history with different ways of charging the car and compares the monthly peak quarter hour,
the demand charge and how often the car would not have been ready at departure. Same car energy and same house load in every
strategy; only *when* and *how fast* the car takes its grid energy changes.

Inputs (all hourly, keys = start of the local hour):
* `grid`  - energy imported from the grid in that hour (kWh; = mean kW of the hour)
* `car`   - energy the wallbox delivered in that hour (kWh)
* `trips` - start hours of trips (the odometer rose in that hour)

Strategies:
* `as_is`  - what really happened (in hours with charging at least one quarter hour at full power)
* `guard`  - a real-time guard holds the import below `guard_kw` (down to the minimum power), what is missing is charged later
* `spread` - the grid energy of a charging session is spread evenly from parking to departure (no real-time data needed)
* `fixed`  - the wallbox's own "ready by" with a fixed low power, ending at departure (a setting, no software)

The quarter-hour peak is estimated from hourly values: house hourly mean + `quarter_add_kw` (how far the house goes above its
hourly mean within an hour) + the car. Everything is an estimate: the result says so and reports the data it is based on.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

HOUR = timedelta(hours=1)
SESSION_GAP_H = 2          # charging hours closer than this belong to one session
MAX_BACK_H = 14            # the parking window starts at most this long before the first charging hour
MAX_SESSION_H = 24
MIN_SESSION_KWH = 0.5
MIN_DAYS = 14              # less history than this: no statement
MIN_SESSIONS = 5


@dataclass(frozen=True)
class Prices:
    """Demand charge in money per kW and year: `low` up to `threshold` kW, `high` above (one price: high = low)."""

    low: float
    high: float
    threshold: float = 0.0
    minimum_kw: float = 0.0

    def monthly(self, peak_kw: float) -> float:
        p = max(peak_kw, self.minimum_kw)
        if self.threshold > 0:
            return (min(p, self.threshold) * self.low + max(0.0, p - self.threshold) * self.high) / 12.0
        return p * self.low / 12.0


@dataclass
class Session:
    start: datetime           # first hour with charging
    end: datetime             # last hour with charging
    leave: datetime           # the car left (next trip) or the window ends
    window_start: datetime    # parking started (car stood still since then)
    grid_kwh: float = 0.0
    hours: list[datetime] = field(default_factory=list)


def _house(grid: dict[datetime, float], car: dict[datetime, float], t: datetime) -> float | None:
    g = grid.get(t)
    if g is None:
        return None
    return max(0.0, g - min(car.get(t, 0.0), g))


def _grid_part(grid: dict[datetime, float], car: dict[datetime, float], t: datetime) -> float:
    g = grid.get(t)
    return 0.0 if g is None else min(car.get(t, 0.0), g)


def clean_grid(grid: dict[datetime, float], max_kw: float = 30.0) -> dict[datetime, float]:
    """Drop counter jumps: an hour after a gap collects the missing hours, and nothing above `max_kw` is a real hourly mean."""
    return {t: v for t, v in grid.items() if 0.0 <= v <= max_kw and (t - HOUR) in grid}


def car_quarter_kw(car: dict[datetime, float], full_kw: float) -> dict[datetime, float]:
    """Estimated highest quarter-hour power of the car in each hour from hourly energy.

    Inside a block of charging hours the car charged at about its hourly mean (a steady 1.6 kWh per hour is 1.6 kW, not
    6.4 kW). At the edges of a block (and in blocks of one or two hours) the hour was only partly used: the car charged at
    the block's level, at most at full power. Assuming full power everywhere would overstate the peak of a car that
    already charges slowly, and with it the saving."""
    out: dict[datetime, float] = {}
    hours = sorted(t for t, v in car.items() if v > 0.05)
    blocks: list[list[datetime]] = []
    for t in hours:
        if blocks and t - blocks[-1][-1] == HOUR:
            blocks[-1].append(t)
        else:
            blocks.append([t])
    for b in blocks:
        inner = [car[t] for t in b[1:-1]]
        level = sorted(inner)[len(inner) // 2] if inner else None
        for i, t in enumerate(b):
            c = car[t]
            edge = i == 0 or i == len(b) - 1
            if not edge:
                out[t] = min(full_kw, c)
            elif level is not None:
                out[t] = min(full_kw, max(level, c))
            else:  # one or two hours: the energy came in a short burst
                out[t] = full_kw if c > 0.25 * full_kw else min(full_kw, c / 0.25)
    return out


def find_sessions(grid: dict[datetime, float], car: dict[datetime, float], trips: list[datetime]) -> list[Session]:
    trips = sorted(trips)
    out: list[Session] = []
    for t in sorted(car):
        if car[t] <= 0.2:
            continue
        if out and t - out[-1].end <= timedelta(hours=SESSION_GAP_H):
            out[-1].end = t
        else:
            out.append(Session(start=t, end=t, leave=t, window_start=t))
    for i, s in enumerate(out):
        nxt = next((d for d in trips if d > s.end), None)
        leave = min(nxt, s.start + timedelta(hours=MAX_SESSION_H)) if nxt else s.start + timedelta(hours=MAX_SESSION_H)
        if i + 1 < len(out):
            leave = min(leave, out[i + 1].start)
        s.leave = max(leave, s.end + HOUR)
        last_trip = max((d for d in trips if d <= s.start), default=None)
        earliest = s.start - timedelta(hours=MAX_BACK_H)
        if last_trip is not None:
            earliest = max(earliest, last_trip + HOUR)
        if i > 0:
            earliest = max(earliest, out[i - 1].leave)
        s.window_start = min(s.start, earliest)
        n = int((s.leave - s.window_start) / HOUR)
        s.hours = [s.window_start + k * HOUR for k in range(n)]
        s.grid_kwh = sum(_grid_part(grid, car, h) for h in s.hours)
    return [s for s in out if s.grid_kwh >= MIN_SESSION_KWH]


def _plan(strategy: str, s: Session, grid, car, full_kw: float, min_kw: float, guard_kw: float | None,
          fixed_kw: float, quarter_add_kw: float) -> tuple[dict[datetime, float], float]:
    """Car grid energy per hour for one session and the energy still missing at departure."""
    if strategy in ("as_is", "guard"):
        want = {h: _grid_part(grid, car, h) for h in s.hours}
    elif strategy == "spread":
        p = min(full_kw, max(min_kw, s.grid_kwh / max(1, len(s.hours))))
        want, rest = {}, s.grid_kwh
        for h in s.hours:
            take = min(p, rest)
            want[h] = take
            rest -= take
    elif strategy == "fixed":
        need = int(s.grid_kwh / fixed_kw + 0.999)
        want, rest = {}, s.grid_kwh
        for h in s.hours[max(0, len(s.hours) - need):]:
            take = min(fixed_kw, rest)
            want[h] = take
            rest -= take
        return want, max(0.0, rest)
    else:
        raise ValueError(strategy)
    if strategy == "guard" and guard_kw:
        held, backlog = {}, 0.0
        for h in s.hours:
            hq = (_house(grid, car, h) or 0.0) + quarter_add_kw
            give = min(want.get(h, 0.0) + backlog, max(min_kw, guard_kw - hq), full_kw)
            backlog = want.get(h, 0.0) + backlog - give
            held[h] = give
        return held, max(0.0, backlog)
    return want, 0.0


def calculate(
    grid: dict[datetime, float],
    car: dict[datetime, float],
    trips: list[datetime],
    *,
    full_kw: float = 11.0,
    min_kw: float = 1.4,
    fixed_kw: float = 4.1,
    guard_kw: float | None = None,
    quarter_add_kw: float = 0.7,
    prices: Prices | None = None,
    measured_peaks: dict[str, float] | None = None,
) -> dict[str, Any]:
    """The comparison for the given history. `measured_peaks` (month -> kW, measured without a guard) checks the model."""
    hours = sorted(t for t in grid if t in car)
    days = len({t.date() for t in hours})
    sessions = find_sessions(grid, car, trips)
    result: dict[str, Any] = {"days": days, "sessions": len(sessions), "status": "ok", "strategies": {}, "months": []}
    if days < MIN_DAYS or len(sessions) < MIN_SESSIONS:
        result["status"] = "too_little_data"
        return result
    strategies = ["as_is", "spread", "fixed"] + (["guard"] if guard_kw else [])
    months = sorted({t.strftime("%Y-%m") for t in hours})
    real_q = car_quarter_kw(car, full_kw)
    for st in strategies:
        load: dict[datetime, float] = defaultdict(float)
        missing = []
        for s in sessions:
            plan, miss = _plan(st, s, grid, car, full_kw, min_kw, guard_kw, fixed_kw, quarter_add_kw)
            for h, v in plan.items():
                load[h] += v
            if miss > 0.5:
                missing.append({"start": s.start.isoformat(), "missing_kwh": round(miss, 1)})
        peaks: dict[str, float] = defaultdict(float)
        for t in hours:
            house = _house(grid, car, t)
            if house is None:
                continue
            c = load.get(t, 0.0)
            if st == "as_is" and c > 0:
                gp = _grid_part(grid, car, t)
                share = gp / car[t] if car.get(t) else 0.0         # the part of the car's power that came from the grid
                c = real_q.get(t, c) * share
            peaks[t.strftime("%Y-%m")] = max(peaks[t.strftime("%Y-%m")], house + quarter_add_kw + c)
        entry: dict[str, Any] = {
            "peaks": {m: round(peaks[m], 2) for m in months if m in peaks},
            "not_ready": len(missing),
            "not_ready_sessions": missing[:10],
        }
        if prices:
            monthly = [prices.monthly(peaks[m]) for m in months if m in peaks]
            entry["cost_per_year"] = round(sum(monthly) / len(monthly) * 12, 0) if monthly else None
        result["strategies"][st] = entry
    base = result["strategies"]["as_is"]["peaks"]
    if measured_peaks:
        errs = [abs(base[m] - measured_peaks[m]) for m in base if m in measured_peaks]
        result["model_error_kw"] = round(max(errs), 2) if errs else None
    s_peaks = result["strategies"]["spread"]["peaks"]
    result["peak_as_is_kw"] = round(max(base.values()), 1) if base else None
    result["peak_spread_kw"] = round(max(s_peaks.values()), 1) if s_peaks else None
    if prices:
        a, b = result["strategies"]["as_is"].get("cost_per_year"), result["strategies"]["spread"].get("cost_per_year")
        result["saving_spread_per_year"] = round(a - b, 0) if a is not None and b is not None else None
        if guard_kw and result["strategies"]["guard"].get("cost_per_year") is not None:
            result["saving_spread_vs_guard_per_year"] = round(result["strategies"]["guard"]["cost_per_year"] - b, 0)
    gk = [s.grid_kwh for s in sessions]
    wh = [len(s.hours) for s in sessions]
    result["session_kwh_median"] = round(sorted(gk)[len(gk) // 2], 1)
    result["window_h_median"] = sorted(wh)[len(wh) // 2]
    result["verdict"] = verdict(result)
    return result


def verdict(r: dict[str, Any]) -> str:
    """One plain key for the outcome (the text is built in the Home Assistant layer)."""
    a, s = r.get("peak_as_is_kw"), r.get("peak_spread_kw")
    if a is None or s is None:
        return "unknown"
    if a - s < 1.0:
        return "little"            # spreading changes the peak by less than 1 kW: hardly worth it
    fixed = max(r["strategies"]["fixed"]["peaks"].values(), default=a)
    if r["strategies"]["fixed"]["not_ready"] == 0 and fixed - s < 1.0:
        return "setting_enough"    # the wallbox's own "ready by" with a low current gets almost the same
    return "worth_it"
