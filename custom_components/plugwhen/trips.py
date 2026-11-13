"""Trips from a calendar (pure Python): an event in a calendar of Home Assistant is a departure Plugwhen plans for.

* start of the event = the departure,
* kilometres: written in the title or the description ("Linz 200 km", "120km", "85 Kilometer") win; otherwise the distance to the event's
  location from a route service (Waze travel time, optional), there and back unless the event says one way ("einfach", "one way"),
* the event replaces the learned departure of its day; the range to have is the trip plus a margin, at least the reserve.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

TRIP_MARGIN = 1.15          # 15 % on top of the kilometres of a trip (detours, cold, motorway)
HORIZON_DAYS = 14
_KM = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:km|kilometer|kilometres|kilometers)\b", re.IGNORECASE)
_ONE_WAY = re.compile(r"\b(einfach|one[ -]?way|nur hin)\b", re.IGNORECASE)


def parse_km(*texts: str | None) -> float | None:
    """Kilometres written in a text ("200 km", "120km", "85,5 Kilometer"), the first one found, or None."""
    for text in texts:
        m = _KM.search(text or "")
        if m:
            km = float(m.group(1).replace(",", "."))
            if 0 < km < 5000:
                return km
    return None


def one_way(*texts: str | None) -> bool:
    return any(_ONE_WAY.search(t or "") for t in texts)


def _parse(t: Any, tz) -> datetime | None:
    if isinstance(t, datetime):
        d = t
    else:
        s = str(t or "")
        if len(s) == 10:   # an all-day event has no time: not a departure we can plan for
            return None
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None
    return d if d.tzinfo is not None else d.replace(tzinfo=tz)


def trips_from_events(events: list[dict[str, Any]] | None, now: datetime, days: int = HORIZON_DAYS) -> list[dict[str, Any]]:
    """Calendar events ({start, summary, description, location}) as trips ahead, sorted by departure. All-day events and events in
    the past are left out. `km_given` = kilometres written in the event, `one_way` = only one direction."""
    out = []
    for e in events or []:
        if not isinstance(e, dict):
            continue
        dep = _parse(e.get("start"), now.tzinfo)
        if dep is None or dep <= now or dep > now + timedelta(days=days):
            continue
        title, desc, loc = str(e.get("summary") or ""), str(e.get("description") or ""), str(e.get("location") or "").strip()
        out.append({"departure": dep, "title": title, "location": loc or None,
                    "km_given": parse_km(title, desc), "one_way": one_way(title, desc)})
    return sorted(out, key=lambda x: x["departure"])


def trip_km(trip: dict[str, Any], route_km: float | None) -> tuple[float | None, str | None]:
    """(kilometres of the trip, source): written in the event ("event"), else the route there and back ("route"), else (None, None)."""
    if trip.get("km_given"):
        return float(trip["km_given"]), "event"
    if route_km:
        return round(float(route_km) * (1 if trip.get("one_way") else 2), 1), "route"
    return None, None


def range_for_trip(km: float, reserve_km: float) -> float:
    """The range to have at the departure of a trip: its kilometres plus a margin, at least the reserve."""
    return round(max(reserve_km, km * TRIP_MARGIN), 1)


_COORDS = re.compile(r"^\s*(-?\d{1,2}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)\s*$")


def coordinates(text: str | None) -> str | None:
    """'48.2082, 16.3738' -> '48.2082,16.3738' (the location is already coordinates), else None."""
    m = _COORDS.match(text or "")
    if not m:
        return None
    lat, lon = float(m.group(1)), float(m.group(2))
    return f"{lat},{lon}" if -90 <= lat <= 90 and -180 <= lon <= 180 else None


_SUFFIX = re.compile(   # door, staircase, floor: "Stiege 2", "Top 14", "Tür 3a", "3. Stock", "2. OG", "Apt 4"
    r"\s*(?:\b(?:stiege|stg\.?|tür|tuer|top|haus|block|wohnung|whg\.?|apt\.?|apartment|flat|unit|suite)\s*\d+[a-zA-Z]?\b"
    r"|\b\d+\.?\s*(?:stock|stockwerk|og|obergeschoss|floor)\b|\b(?:eg|dg|erdgeschoss|dachgeschoss)\b)", re.IGNORECASE)
_DOOR = re.compile(r"(\b\d+[a-zA-Z]?)(?:\s*/\s*[\w]+)+")      # "Hauptstraße 5/2/7" -> "Hauptstraße 5"
_POSTCODE = re.compile(r"\b\d{4,5}\b")


GEO_MISS = "miss:"   # remembered location that OpenStreetMap did not find, followed by the time


def address_variants(text: str | None) -> list[str]:
    """What to ask OpenStreetMap for, in this order: the text as written, without door, staircase or floor
    ("Hauptstraße 5/2/7, Stiege 2" -> "Hauptstraße 5"), and only the part with the postcode and town (good enough for the
    kilometres). Each one only once."""
    t = " ".join(str(text or "").split())
    if not t:
        return []
    out = [t]
    parts = [p.strip() for p in t.split(",")]
    clean = [_DOOR.sub(r"\1", _SUFFIX.sub("", p)).strip(" ,") for p in parts]
    out.append(", ".join(p for p in clean if p))
    town = [p for p in clean if _POSTCODE.search(p)]
    if town and len(clean) > 1:
        out.append(", ".join(town))
    seen: list[str] = []
    for v in out:
        if v and v not in seen:
            seen.append(v)
    return seen


def parse_geocode(data) -> str | None:
    """The first hit of an OpenStreetMap (Nominatim) search as 'lat,lon', or None."""
    if isinstance(data, list) and data and isinstance(data[0], dict):
        try:
            return f"{float(data[0]['lat'])},{float(data[0]['lon'])}"
        except (KeyError, TypeError, ValueError):
            return None
    return None


def waze_region(country: str | None) -> str:
    """The region the route service wants for this country."""
    c = (country or "").upper()
    if c in ("US", "CA"):
        return "us"
    if c == "IL":
        return "il"
    if c in ("AU", "NZ"):
        return "au"
    return "eu"


def event_days(events: list[dict[str, Any]] | None, tz, max_days: int = 14) -> set:
    """The dates an event of the trip calendar touches: a special trip is an exception, so the learning leaves these days out.
    Timed events: from the start date to the end date; all-day events: the end date is exclusive. At most `max_days` per event."""
    from datetime import date

    out: set[date] = set()
    for e in events or []:
        if not isinstance(e, dict):
            continue
        s, en = str(e.get("start") or ""), str(e.get("end") or e.get("start") or "")
        try:
            if len(s) == 10:
                first, last = date.fromisoformat(s), date.fromisoformat(en[:10]) - timedelta(days=1) if len(en) == 10 else date.fromisoformat(s)
            else:
                a = _parse(s, tz)
                b = _parse(en, tz) or a
                if a is None:
                    continue
                first, last = a.astimezone(tz).date(), b.astimezone(tz).date()
        except ValueError:
            continue
        last = max(first, last)
        d, n = first, 0
        while d <= last and n < max_days:
            out.add(d)
            d += timedelta(days=1)
            n += 1
    return out
