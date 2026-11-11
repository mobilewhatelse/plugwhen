"""Looking ahead: where does the energy for the next departures come from, and would charging with the sun in advance save grid energy?
(pure Python, no Home Assistant imports)

The plan of `plan.py` only reaches the next departure. A car that is charged on the sunny weekend can skip a night on the grid on
Wednesday. This module looks over the next few departures:

1. **Deficits in order.** The car must leave with at least the range the need asks for (reserve, lifted by what was learned). After
   each trip it has used the expected energy. Whatever is missing before a departure is its deficit.
2. **Home windows.** The car can charge between its return (departure plus the expected time away) and the next departure.
3. **Sun first, in the same window.** The available power (sun forecast minus the base load, or whatever else the availability input
   says) inside a window covers that window's deficit first.
4. **Pre-charging.** Sun that is left over in an earlier window is used for the grid energy of a later deficit, as far as the battery
   stays below a cap (default 80 %) and the sun lasts. That is the recommendation: "charge 14 kWh with the sun on Saturday, it replaces
   12 kWh from the grid before Wednesday".

It needs no solar plant: without a forecast nothing is pre-charged and the result simply says how much each departure needs from the
grid. It recommends only; nothing is switched. For every departure with a need it also says the **latest start**:
the time by which charging at full power must begin to be ready (`latest_start`) and at the preferred power (`latest_start_pref`). The assumptions are explicit: the time away follows from the length of the trip
(`away_hours`), the trips are the expected (typical) ones.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

QUARTER = timedelta(minutes=15)
QUARTER_H = 0.25
DEFAULT_EFFICIENCY = 0.9
PRECHARGE_CAP = 0.8                  # pre-charging fills the battery up to this share of its capacity
MIN_AWAY_H, MAX_AWAY_H = 3.0, 10.0
DAYLIGHT = (7, 19)                   # hours in which a window beyond the forecast could have sun, when the forecast does not tell
MIN_SUN_KW = 1.0                     # a quarter hour with less available power is not counted as sun slot for the span
TINY_KWH = 0.2


@dataclass(frozen=True)
class Trip:
    departure: datetime
    km_typical: float        # the energy the trip is expected to use
    km_target: float         # the range to have at departure (reserve floor, lifted by the learned high value)


SAME_TRIP_WINDOW = timedelta(hours=2)   # a calendar trip this close to a learned departure counts as the same trip


def without_same_trip(trips: list[Trip], departure: datetime, window: timedelta = SAME_TRIP_WINDOW) -> list[Trip]:
    """The trips without the one that is the same as a trip at `departure` (within the window). Trips at another time stay: they come on top."""
    return [t for t in trips if abs(t.departure - departure) > window]


def away_hours(km_typical: float) -> float:
    """How long the car is away: three hours plus an hour per 12 km, between 3 and 10 hours (a stand-in until it is learned from the plug-in times)."""
    return min(MAX_AWAY_H, max(MIN_AWAY_H, 3.0 + km_typical / 12.0))


def _quarter(t: datetime) -> datetime:
    return t.replace(minute=(t.minute // 15) * 15, second=0, microsecond=0)


def _sun_in(start: datetime, end: datetime, sun_kw: dict[datetime, float] | None, max_kw: float) -> tuple[float, datetime | None, datetime | None]:
    """Wallbox energy the sun could deliver between `start` and `end`, and the first and last quarter hour with real sun."""
    if not sun_kw or end <= start:
        return 0.0, None, None
    total, first, last = 0.0, None, None
    t = _quarter(start)
    while t < end:
        nxt = t + QUARTER
        frac = (min(nxt, end) - max(t, start)).total_seconds() / 900.0
        kw = min(max_kw, max(0.0, sun_kw.get(t, 0.0)))
        if frac > 0 and kw >= MIN_SUN_KW:  # weaker sun cannot be charged (a wallbox needs more than that), so it does not count
            total += kw * QUARTER_H * frac
            first = first or t
            last = nxt
        t = nxt
    return total, first, last


def _sun_segments(start: datetime, end: datetime, sun_kw: dict[datetime, float] | None, max_kw: float) -> list[dict[str, Any]]:
    """The stretches inside [start, end] in which the sun delivers real power (at least MIN_SUN_KW): from, to, energy, mean power.
    A gap of one quarter hour does not split a stretch (a cloud passing by)."""
    if not sun_kw or end <= start:
        return []
    segs: list[list[Any]] = []                        # [from, to, kwh, gap_kwh_pending]
    t = _quarter(start)
    while t < end:
        nxt = t + QUARTER
        lo, hi = max(t, start), min(nxt, end)
        frac = (hi - lo).total_seconds() / 900.0
        kw = min(max_kw, max(0.0, sun_kw.get(t, 0.0)))
        if frac > 0 and kw >= MIN_SUN_KW:
            kwh = kw * QUARTER_H * frac
            if segs and (lo - segs[-1][1]) <= QUARTER:
                segs[-1][1] = hi
                segs[-1][2] += kwh
            else:
                segs.append([lo, hi, kwh])
        t = nxt
    return [{"from": a, "to": b, "kwh": k, "avg_kw": k / max(1e-6, (b - a).total_seconds() / 3600.0)} for a, b, k in segs]


def sun_unknown_hours(home_from: datetime, departure: datetime, until: datetime | None,
                      daylight: tuple[int, int] = DAYLIGHT) -> float:
    """Daylight hours of the window [home_from, departure] that lie beyond the end of the forecast `until` (None = no forecast at all:
    nothing to mark). Night-only windows never count: the sun would not matter there anyway."""
    if until is None or departure <= until:
        return 0.0
    lo = max(home_from, until)
    hours = 0.0
    day = lo.replace(hour=0, minute=0, second=0, microsecond=0)
    while day < departure:
        a = max(lo, day + timedelta(hours=daylight[0]))
        b = min(departure, day + timedelta(hours=daylight[1]))
        if b > a:
            hours += (b - a).total_seconds() / 3600.0
        day += timedelta(days=1)
    return hours


def horizon_plan(
    now: datetime,
    soc_kwh: float | None,
    capacity_kwh: float,
    consumption: float,
    trips: list[Trip],
    sun_kw: dict[datetime, float] | None,
    max_kw: float,
    *,
    efficiency: float = DEFAULT_EFFICIENCY,
    cap_share: float = PRECHARGE_CAP,
    pref_kw: float | None = None,
) -> dict[str, Any]:
    """The look-ahead over `trips` (see the module text). `soc_kwh`: energy in the battery now (None = unknown)."""
    iso = lambda t: t.isoformat() if t else None  # noqa: E731
    result: dict[str, Any] = {"status": "ok", "days": [], "precharge": [], "grid_without_precharge_kwh": 0.0,
                              "grid_with_precharge_kwh": 0.0, "saved_grid_kwh": 0.0, "sun_used": bool(sun_kw)}
    # the forecast covers whole days: it ends at the midnight after its last quarter hour; the sun hours of the season come from it too
    sun_until = (max(sun_kw).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)) if sun_kw else None
    lit = sorted({t.hour for t, kw in (sun_kw or {}).items() if kw > 0})
    daylight = (lit[0], lit[-1] + 1) if lit else DAYLIGHT
    result["sun_until"] = sun_until.isoformat() if sun_until else None
    if soc_kwh is None:
        result["status"] = "unknown_soc"
        return result
    trips = sorted((t for t in trips if t.departure > now), key=lambda t: t.departure)
    if not trips or capacity_kwh <= 0 or consumption <= 0 or max_kw <= 0:
        result["status"] = "no_trips"
        return result
    eff = max(0.1, efficiency)

    soc = max(0.0, min(capacity_kwh, soc_kwh))
    rows: list[dict[str, Any]] = []
    prev: Trip | None = None
    for trip in trips:
        home_from = now if prev is None else max(now, prev.departure + timedelta(hours=away_hours(prev.km_typical)))
        home_from = min(home_from, trip.departure)
        target = min(capacity_kwh, max(0.0, trip.km_target * consumption))
        deficit = max(0.0, target - soc)
        soc_end = max(soc, target)                       # at the end of the window, before the trip
        need = deficit / eff                             # from the wallbox
        sun, first, last = _sun_in(home_from, trip.departure, sun_kw, max_kw)
        segments = _sun_segments(home_from, trip.departure, sun_kw, max_kw)
        direct = min(sun, need)
        rows.append({"trip": trip, "home_from": home_from, "need": need, "sun": sun, "direct": direct, "grid": need - direct,
                     "spare": sun - direct, "soc_end": soc_end, "extra": 0.0, "pre_in": 0.0, "first": first, "last": last, "items": {},
                     "segments": segments})
        soc = max(0.0, soc_end - trip.km_typical * consumption)
        prev = trip

    without = sum(r["grid"] for r in rows)
    cap = cap_share * capacity_kwh
    for i, ri in enumerate(rows):
        # what earlier pre-charging still holds in the battery at the end of this window (the part that has not covered a deficit yet)
        carried = sum(rows[k]["extra"] for k in range(i)) - sum(rows[j]["pre_in"] * eff for j in range(i + 1))
        carried = max(0.0, carried)
        for j in range(i + 1, len(rows)):
            if ri["spare"] < TINY_KWH:
                break
            rj = rows[j]
            if rj["grid"] < TINY_KWH:
                continue
            room_batt = cap - (ri["soc_end"] + carried + ri["extra"])
            m = min(ri["spare"], rj["grid"], max(0.0, room_batt) / eff)
            if m < TINY_KWH:
                continue
            ri["spare"] -= m
            ri["extra"] += m * eff
            rj["grid"] -= m
            rj["pre_in"] += m
            ri["items"][j] = ri["items"].get(j, 0.0) + m

    for r in rows:
        result["days"].append({
            "departure": iso(r["trip"].departure), "window_start": iso(r["home_from"]), "need_kwh": round(r["need"], 1),
            "latest_start": iso(r["trip"].departure - timedelta(hours=r["need"] / max_kw)) if r["need"] >= TINY_KWH else None,
            "latest_start_pref": (iso(r["trip"].departure - timedelta(hours=r["need"] / min(max_kw, pref_kw)))
                                  if r["need"] >= TINY_KWH and pref_kw else None),
            "sun_direct_kwh": round(r["direct"], 1), "precharge_kwh": round(r["pre_in"], 1), "grid_kwh": round(max(0.0, r["grid"]), 1),
            "sun_known": sun_unknown_hours(r["home_from"], r["trip"].departure, sun_until, daylight) < 1.0,
        })
        for j, m in sorted(r["items"].items()):
            result["precharge"].append({
                "window_start": iso(r["home_from"]), "window_end": iso(r["trip"].departure), "sun_from": iso(r["first"]), "sun_to": iso(r["last"]),
                "kwh": round(m, 1), "for_departure": iso(rows[j]["trip"].departure), "replaces_grid_kwh": round(m, 1),
            })
    # with normal behaviour: until when does the charge last, and what is the first charging that is needed (whatever the sun does)
    first = next((i for i, r in enumerate(rows) if r["need"] >= TINY_KWH), None)
    result["trips_looked_at"] = len(rows)
    result["last_departure"] = iso(rows[-1]["trip"].departure)
    if first is None:
        result["lasts_until"] = iso(rows[-1]["trip"].departure)         # no charging needed within the whole look-ahead
        result["first_need"] = None
    else:
        r0 = rows[first]
        result["lasts_until"] = iso(rows[first - 1]["trip"].departure) if first > 0 else None
        result["first_need"] = {
            "departure": iso(r0["trip"].departure), "window_start": iso(r0["home_from"]), "need_kwh": round(r0["need"], 1),
            "latest_start": iso(r0["trip"].departure - timedelta(hours=r0["need"] / max_kw)),
            "latest_start_pref": iso(r0["trip"].departure - timedelta(hours=r0["need"] / min(max_kw, pref_kw))) if pref_kw else None,
            "covered_by_sun": r0["grid"] < TINY_KWH,
        }
    # the sun windows in the times the car is at home: when would it make sense to plug in? (a recommendation, nothing is switched)
    windows = []
    for i, r in enumerate(rows):
        used = r["direct"] + sum(r["items"].values())
        purpose = "need" if r["direct"] >= TINY_KWH else ("precharge" if sum(r["items"].values()) >= TINY_KWH else "spare")
        for sg in r["segments"]:
            windows.append({"from": iso(sg["from"]), "to": iso(sg["to"]), "sun_kwh": round(sg["kwh"], 1), "avg_kw": round(sg["avg_kw"], 1),
                            "purpose": purpose, "used_kwh": round(used, 1), "home_from": iso(r["home_from"]), "departure": iso(r["trip"].departure)})
    result["sun_windows"] = windows
    best = next((w for w in windows if w["purpose"] in ("need", "precharge") and w["sun_kwh"] >= 1.0), None)
    result["best_sun_window"] = best
    with_pre = sum(max(0.0, r["grid"]) for r in rows)
    result.update({"grid_without_precharge_kwh": round(without, 1), "grid_with_precharge_kwh": round(with_pre, 1),
                   "saved_grid_kwh": round(without - with_pre, 1)})
    if sum(r["need"] for r in rows) < TINY_KWH:
        result["status"] = "no_need"
    return result
