"""Fleet values: anonymous trip days to our service, consumption of many cars of the same model back (pure Python, no Home
Assistant imports; the coordinator does the sending).

Only with *Share anonymous data* switched on. Sent per day with a trip (at least `MIN_KM`, consumption and outdoor
temperature known): the car model, the battery size, km, kWh per km, the mean outdoor temperature of the day and the odometer
as a step of 10 000 km. Per day charged only at home (enough to say something): the wallbox energy per 100 % state of
charge; against the battery size it gives the charging loss, over the odometer steps the ageing of the battery. Per whole
day parked and not charged: the fall of the state of charge (loss while parked).
**No date, no time, no place, no id.** The service mixes the days and keeps no link to who sent them, so they cannot be
deleted later.

The service files the free car name under a model of its list (open data) and says which; the list can grow without an
update of Plugwhen, and names it does not know stay as they are.

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
KM_STEP = 10000             # the odometer is sent only as a step of this size
MIN_HOME_KWH = 3.0          # a charging day needs this much at home ...
MIN_RISE_SHARE = 0.20       # ... and a rise of the state of charge of at least 20 %


def model_name(manufacturer: str | None, model: str | None) -> str | None:
    """The car model as the service keeps it: maker and model of the device the state of charge belongs to, small letters,
    only letters, digits, space, dot, plus, hyphen. None if nothing usable is known (then nothing is sent)."""
    raw = " ".join(str(x) for x in (manufacturer, model) if x)
    s = re.sub(r"[^a-z0-9 .+\-äöü]", "", raw.strip().lower())
    s = re.sub(r"\s+", " ", s).strip()[:60]
    return s if len(s) >= 2 and any(c.isalpha() for c in s) else None


def km_step(odometer: float | None) -> int | None:
    if odometer is None or odometer < 0 or odometer > 1_000_000:
        return None
    return int(odometer // KM_STEP * KM_STEP)


def charge_days(records: list, model: str, battery_kwh: float, after: date | None, today: date) -> list[dict[str, Any]]:
    """Days charged only at home: wallbox energy per 100 % state of charge (same days as `trip_days` would cover)."""
    out: list[dict[str, Any]] = []
    if battery_kwh <= 0:
        return out
    for r in sorted(records, key=lambda r: r.day):
        if r.day >= today or (after is not None and r.day <= after):
            continue
        home, charged = r.home_kwh, r.charged_kwh
        if home is None or charged is None or home < MIN_HOME_KWH or charged < MIN_RISE_SHARE * battery_kwh:
            continue
        if not 0.6 <= charged / home <= 1.02:      # above: charged elsewhere too; below: nonsense
            continue
        per100 = home / (charged / battery_kwh)
        row: dict[str, Any] = {"modell": model, "akku_kwh": round(float(battery_kwh)), "wb_kwh_je_100": round(per100, 1)}
        if r.temp_c is not None:
            row["temp_c"] = round(r.temp_c)
        step = km_step(getattr(r, "odometer_km", None))
        if step is not None:
            row["km_stand"] = step
        out.append(row)
    return out[-MAX_DAYS_PER_SEND:]


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
        row = {"modell": model, "akku_kwh": round(float(battery_kwh)), "km": round(km), "kwh_km": round(r.consumption, 3),
               "temp_c": round(r.temp_c)}
        step = km_step(getattr(r, "odometer_km", None))
        if step is not None:
            row["km_stand"] = step
        out.append(row)
    return out[-MAX_DAYS_PER_SEND:], last


def parked_days(records: list, model: str, battery_kwh: float, after: date | None, today: date) -> list[dict[str, Any]]:
    """Days parked a whole day and not charged: the fall of the state of charge in % (rounded to 0.5), only with the current
    consent. Gives the loss while parked per car model (sleep, app, alarm system); no date, like the trip days."""
    out: list[dict[str, Any]] = []
    for r in sorted(records, key=lambda r: r.day):
        if r.day >= today or (after is not None and r.day <= after):
            continue
        drop = getattr(r, "parked_drop_pct", None)
        if drop is None:
            continue
        row: dict[str, Any] = {"modell": model, "akku_kwh": round(float(battery_kwh)), "verlust_pct": float(drop)}
        if r.temp_c is not None:
            row["temp_c"] = round(r.temp_c)
        out.append(row)
    return out[-MAX_DAYS_PER_SEND:]


def payload(days: list[dict[str, Any]], first: bool, charges: list[dict[str, Any]] | None = None,
            parked: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    p: dict[str, Any] = {"schema": 1, "integration": "plugwhen", "tage": days, "erstes_mal": bool(first)}
    if charges:
        p["ladungen"] = charges
    if parked:
        p["standtage"] = parked
    return p


_ALIAS = {"mercedes": "mercedes-benz", "vw": "volkswagen", "mb": "mercedes-benz"}


def _words(name: str) -> list[str]:
    return [_ALIAS.get(w, w) for w in name.split() if w]


def group_of(models: dict[str, Any] | None, model: str | None, known: dict[str, str] | None = None) -> str | None:
    """The name the service files the car under: what it said when the days were sent (`known`), else the longest model
    of its answer whose words are all in the car name (same maker), else the car name itself."""
    if not model:
        return None
    if known and known.get(model):
        return known[model]
    words = _words(model)
    best, n = None, 0
    for key in ((models or {}).get("modelle") or {}):
        kw = _words(str(key))
        if len(kw) >= 2 and words and kw[0] == words[0] and set(kw) <= set(words) and len(kw) > n:
            best, n = str(key), len(kw)
    return best or model


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
