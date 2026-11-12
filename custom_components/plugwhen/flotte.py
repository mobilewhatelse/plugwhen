"""Fleet values: anonymous trip days to our service, consumption of many cars of the same model back (pure Python, no Home
Assistant imports; the coordinator does the sending).

Only with *Share anonymous data* switched on. Sent per day with a trip (at least `MIN_KM`, consumption and outdoor
temperature known): the car model, the battery size, km, kWh per km and the mean outdoor temperature of the day. **No date,
no time, no place, no id.** The service mixes the days and keeps no link to who sent them, so they cannot be deleted later.

Back comes a key (valid 180 days) to fetch the models: per car model (from 5 cars) and all cars together. Plugwhen uses them
only as long as the car has no values of its own: own curve, then the own model, then all cars, then the start values.
A failure never disturbs Plugwhen: nothing sent, nothing fetched, everything as before.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

try:  # inside Home Assistant the module lives in a package, the tests import it flat
    from .startwerte import temperature_factor
except ImportError:  # pragma: no cover
    from startwerte import temperature_factor

ZIEL_SENDEN = "https://www.aiwhatelse.eu/autodaten/v1/senden.php"
ZIEL_MODELLE = "https://www.aiwhatelse.eu/autodaten/v1/modelle.php"

MIN_KM = 30.0               # shorter days say little about the consumption (the service ignores them too)
MAX_KM = 1500.0
MIN_CONSUMPTION, MAX_CONSUMPTION = 0.08, 0.60
MAX_DAYS_PER_SEND = 400     # first send: everything the history has; the service takes at most 400
EXTRAPOLATE_K = 5.0         # a fleet curve is used at most this far outside its temperatures


def model_name(manufacturer: str | None, model: str | None) -> str | None:
    """The car model as the service keeps it: maker and model of the device the state of charge belongs to, small letters,
    only letters, digits, space, dot, plus, hyphen. None if nothing usable is known (then nothing is sent)."""
    raw = " ".join(str(x) for x in (manufacturer, model) if x)
    s = re.sub(r"[^a-z0-9 .+\-äöü]", "", raw.strip().lower())
    s = re.sub(r"\s+", " ", s).strip()[:60]
    return s if len(s) >= 2 and any(c.isalpha() for c in s) else None


def trip_days(records: list, model: str, battery_kwh: float, after: date | None, today: date) -> tuple[list[dict[str, Any]], date | None]:
    """The days to send: complete days (before `today`) after `after` with a trip, consumption and temperature.
    Returns the days (without their date) and the last date covered, or (`[]`, `after`) when there is nothing new."""
    out: list[dict[str, Any]] = []
    last = after
    for r in sorted(records, key=lambda r: r.day):
        if r.day >= today or (after is not None and r.day <= after):
            continue
        last = r.day if last is None or r.day > last else last
        km = r.clean_km()
        if km is None or not (MIN_KM <= km <= MAX_KM) or r.consumption is None or r.temp_c is None:
            continue
        if not (MIN_CONSUMPTION <= r.consumption <= MAX_CONSUMPTION):
            continue
        out.append({"modell": model, "akku_kwh": round(float(battery_kwh)), "km": round(km), "kwh_km": round(r.consumption, 3),
                    "temp_c": round(r.temp_c)})
    return out[-MAX_DAYS_PER_SEND:], last


def payload(days: list[dict[str, Any]], first: bool) -> dict[str, Any]:
    return {"schema": 1, "integration": "plugwhen", "tage": days, "erstes_mal": bool(first)}


def entry_for(models: dict[str, Any] | None, model: str | None) -> tuple[dict[str, Any] | None, str | None]:
    """The fleet values for a car: (values, "fleet_model") for its own model, else (values, "fleet_all"), else (None, None)."""
    if not isinstance(models, dict) or models.get("schema") != 1:
        return None, None
    own = (models.get("modelle") or {}).get(model) if model else None
    if isinstance(own, dict) and own.get("mittel_kwh_km"):
        return own, "fleet_model"
    every = models.get("alle")
    if isinstance(every, dict) and every.get("mittel_kwh_km"):
        return every, "fleet_all"
    return None, None


def consumption(entry: dict[str, Any], temp_c: float | None) -> float | None:
    """kWh per km of the fleet at `temp_c`: its line by temperature if it has one, else its mean moved with the start curve."""
    try:
        mean = float(entry["mittel_kwh_km"])
        t_mean = float(entry.get("mittel_temp_c") if entry.get("mittel_temp_c") is not None else 15.0)
    except (KeyError, TypeError, ValueError):
        return None
    if temp_c is None:
        value = float(entry.get("median_kwh_km") or mean)
    elif entry.get("steigung_kwh_km_je_k") is not None:
        lo = float(entry.get("temp_min_c", t_mean)) - EXTRAPOLATE_K
        hi = float(entry.get("temp_max_c", t_mean)) + EXTRAPOLATE_K
        at = max(lo, min(hi, temp_c))
        value = mean + min(0.0, float(entry["steigung_kwh_km_je_k"])) * (at - t_mean)
    else:
        value = mean * temperature_factor(temp_c) / temperature_factor(t_mean)
    return round(max(MIN_CONSUMPTION, min(MAX_CONSUMPTION, value)), 3)


def due(last: str | None, now: datetime, hours: float = 20.0) -> bool:
    """Once a day (a little less than 24 h, so it does not drift later every day)."""
    if not last:
        return True
    try:
        t = datetime.fromisoformat(last)
    except ValueError:
        return True
    if t.tzinfo is None and now.tzinfo is not None:
        t = t.replace(tzinfo=now.tzinfo)
    return (now - t).total_seconds() >= hours * 3600
