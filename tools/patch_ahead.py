"""One-off: the look-ahead notice 'tomorrow charging is needed' with the latest start (kept for the record).

User 07/08.11.2026: "so that I know tomorrow I must charge, looking ahead: on the same day it is often too late".
The notice comes on the evening BEFORE the day on which charging has to happen (the date the car's home window before a departure with
a need begins), or before the day on which charging with the sun in advance is recommended. It says the latest start at the preferred
power and at full power.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "custom_components" / "plugwhen"


def edit(path, pairs):
    p = path if isinstance(path, Path) else ROOT / path
    s = p.read_text(encoding="utf-8")
    for a, b in pairs:
        assert s.count(a) == 1, f"{p.name}: {a[:90]}"
        s = s.replace(a, b)
    p.write_text(s, encoding="utf-8")


edit(PKG / "horizon.py", [
    ("    efficiency: float = DEFAULT_EFFICIENCY,\n    cap_share: float = PRECHARGE_CAP,\n) -> dict[str, Any]:",
     "    efficiency: float = DEFAULT_EFFICIENCY,\n    cap_share: float = PRECHARGE_CAP,\n    pref_kw: float | None = None,\n) -> dict[str, Any]:"),
    ("""            "latest_start": iso(r["trip"].departure - timedelta(hours=r["need"] / max_kw)) if r["need"] >= TINY_KWH else None,""",
     """            "latest_start": iso(r["trip"].departure - timedelta(hours=r["need"] / max_kw)) if r["need"] >= TINY_KWH else None,
            "latest_start_pref": (iso(r["trip"].departure - timedelta(hours=r["need"] / min(max_kw, pref_kw)))
                                  if r["need"] >= TINY_KWH and pref_kw else None),"""),
    ("the time by which charging at full power must begin to be ready (`latest_start`).",
     "the time by which charging at full power must begin to be ready (`latest_start`) and at the preferred power (`latest_start_pref`)."),
])

edit(PKG / "notice.py", [
    ("def dedupe_key(n: Notice, departure_day: date) -> str:",
     '''@dataclass(frozen=True)
class Ahead:
    """The heads-up for the day after today: charging will be needed (`charge`) or charging with the sun in advance is recommended (`sun`)."""

    kind: str                      # "charge" or "sun"
    day: date                      # the day on which to charge (tomorrow)
    departure: datetime            # the departure the energy is for
    kwh: float                     # wallbox energy (charge: still from the grid, sun: to charge with the sun)
    latest_start: datetime | None  # at full power
    latest_start_pref: datetime | None  # at the preferred power
    sun_from: datetime | None = None
    sun_to: datetime | None = None


def _dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value)) if value else None
    except ValueError:
        return None


def check_ahead(horizon: dict[str, Any] | None, now: datetime, from_hour: float, min_kwh: float = 1.0) -> Ahead | None:
    """The heads-up of this evening for tomorrow, from the look-ahead (`horizon.horizon_plan`). Only from `from_hour` on, like the other
    warning. A recommended pre-charge with the sun tomorrow comes first, otherwise a departure that needs grid energy and whose home window
    begins tomorrow. Charging that has to happen today is the job of the plug-in warning, not of this one."""
    if not horizon or horizon.get("status") != "ok":
        return None
    if now.hour + now.minute / 60.0 < from_hour:
        return None
    tomorrow = (now + timedelta(days=1)).date()
    for p in horizon.get("precharge") or []:
        start, dep = _dt(p.get("sun_from")), _dt(p.get("for_departure"))
        if start is not None and dep is not None and start.date() == tomorrow and float(p.get("kwh") or 0) >= max(2.0, min_kwh):
            return Ahead("sun", tomorrow, dep, float(p["kwh"]), None, None, start, _dt(p.get("sun_to")))
    for d in horizon.get("days") or []:
        start, dep = _dt(d.get("window_start")), _dt(d.get("departure"))
        if start is not None and dep is not None and start.date() == tomorrow and float(d.get("grid_kwh") or 0) >= min_kwh:
            return Ahead("charge", tomorrow, dep, float(d["grid_kwh"]), _dt(d.get("latest_start")), _dt(d.get("latest_start_pref")))
    return None


def ahead_key(a: Ahead) -> str:
    """Once per day of charging and kind."""
    return f"ahead:{a.day.isoformat()}:{a.kind}"


def dedupe_key(n: Notice, departure_day: date) -> str:'''),
    ("from dataclasses import dataclass\nfrom datetime import date\n", "from dataclasses import dataclass\nfrom datetime import date, datetime, timedelta\nfrom typing import Any\n"),
])

edit(PKG / "messages.py", [
    ('''        "unknown_dep": "der nächsten Abfahrt",
        "unknown_soc": "?",
    },''', '''        "unknown_dep": "der nächsten Abfahrt",
        "unknown_soc": "?",
        "ahead_title": "{name}: morgen laden",
        "ahead_charge": "Morgen ({day}) wird Laden nötig: für die Abfahrt {dep_day} {dep} fehlen {kwh} kWh. Spätestens ab {start_pref} mit {pref} kW, mit voller Leistung ab {start}.",
        "ahead_charge_nostart": "Morgen ({day}) wird Laden nötig: für die Abfahrt {dep_day} {dep} fehlen {kwh} kWh.",
        "ahead_sun": "Morgen ({day}) lohnt Vorladen mit Sonne: von {from} bis {to} Uhr etwa {kwh} kWh. Das ersetzt Netzstrom vor der Abfahrt {dep_day} {dep}.",
        "weekdays": ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"],
    },'''),
    ('''        "unknown_dep": "the next departure",
        "unknown_soc": "?",
    },''', '''        "unknown_dep": "the next departure",
        "unknown_soc": "?",
        "ahead_title": "{name}: charge tomorrow",
        "ahead_charge": "Tomorrow ({day}) charging will be needed: {kwh} kWh are missing for the departure {dep_day} {dep}. Latest start {start_pref} at {pref} kW, at full power {start}.",
        "ahead_charge_nostart": "Tomorrow ({day}) charging will be needed: {kwh} kWh are missing for the departure {dep_day} {dep}.",
        "ahead_sun": "Tomorrow ({day}) it pays to charge ahead with the sun: from {from} to {to} about {kwh} kWh. That replaces grid energy before the departure {dep_day} {dep}.",
        "weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    },'''),
    ("from .notice import Notice\n", "from .notice import Ahead, Notice\n"),
    ("    from notice import Notice\n", "    from notice import Ahead, Notice\n"),
])
ms = (PKG / "messages.py").read_text(encoding="utf-8")
ms += '''

def ahead_text(language: str, a: Ahead, name: str, pref_kw: float | None = None) -> tuple[str, str]:
    """(title, message) of the heads-up for tomorrow in German or English."""
    t = TEXTS["de" if (language or "").lower().startswith("de") else "en"]
    wd = t["weekdays"]
    hm = lambda x: x.strftime("%H:%M")  # noqa: E731
    values = dict(name=name, day=wd[a.day.weekday()], dep_day=wd[a.departure.weekday()], dep=hm(a.departure), kwh=f"{a.kwh:.0f}",
                  pref=f"{pref_kw:g}" if pref_kw else "?")
    if a.kind == "sun":
        values.update({"from": hm(a.sun_from) if a.sun_from else "?", "to": hm(a.sun_to) if a.sun_to else "?"})
        return t["ahead_title"].format(**values), t["ahead_sun"].format(**values)
    def when(x):
        return f"{wd[x.weekday()]} {hm(x)}" if x is not None else "?"
    values.update(start=when(a.latest_start), start_pref=when(a.latest_start_pref))
    key = "ahead_charge" if a.latest_start is not None and a.latest_start_pref is not None else "ahead_charge_nostart"
    return t["ahead_title"].format(**values), t[key].format(**values)
'''
(PKG / "messages.py").write_text(ms, encoding="utf-8")
print("ok")
