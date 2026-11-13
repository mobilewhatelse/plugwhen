"""Texts of the warning that the car will not be ready (pure Python)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

try:  # inside Home Assistant the module lives in a package, the tests import it flat
    from .notice import Ahead, Notice
except ImportError:  # pragma: no cover
    from notice import Ahead, Notice

TEXTS = {
    "de": {
        "title": "{name}: morgen nicht bereit",
        "plug_in": "Bitte anstecken: {name} liegt bei {soc} %, bis {dep} fehlen {kwh} kWh (Ziel {target} %, {km} km Reichweite).",
        "low": "{name} liegt bei {soc} %, bis {dep} fehlen {kwh} kWh (Ziel {target} %, {km} km Reichweite). Ob angesteckt ist, ist unbekannt.",
        "too_late": "{name} wird bis {dep} nicht mehr voll: es fehlen {kwh} kWh, möglich sind noch höchstens {possible} kWh (Ziel {target} %).",
        "not_reachable": "{name}: das Ziel von {target} % ({km} km Reichweite) ist mit dem Akku nicht erreichbar.",
        "unknown_dep": "der nächsten Abfahrt",
        "unknown_soc": "?",
        "ahead_title": "{name}: morgen laden",
        "ahead_charge": "Morgen ({day}) wird Laden nötig: für die Abfahrt {dep_day} {dep} fehlen {kwh} kWh. Spätestens ab {start_pref} mit {pref} kW, mit voller Leistung ab {start}.",
        "ahead_charge_nostart": "Morgen ({day}) wird Laden nötig: für die Abfahrt {dep_day} {dep} fehlen {kwh} kWh.",
        "ahead_sun": "Morgen ({day}) lohnt Vorladen mit Sonne: von {from} bis {to} Uhr etwa {kwh} kWh. Das ersetzt Netzstrom vor der Abfahrt {dep_day} {dep}.",
        "ahead_sun_today": "Heute lohnt Vorladen mit Sonne: von {from} bis {to} Uhr etwa {kwh} kWh. Das ersetzt Netzstrom vor der Abfahrt {dep_day} {dep}.",
        "weekdays": ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"],
    },
    "en": {
        "title": "{name}: not ready for tomorrow",
        "plug_in": "Please plug in: {name} is at {soc} %, {kwh} kWh are missing by {dep} (target {target} %, {km} km range).",
        "low": "{name} is at {soc} %, {kwh} kWh are missing by {dep} (target {target} %, {km} km range). It is not known whether it is plugged in.",
        "too_late": "{name} will not be full by {dep}: {kwh} kWh are missing, at most {possible} kWh can still be charged (target {target} %).",
        "not_reachable": "{name}: the target of {target} % ({km} km range) cannot be reached with this battery.",
        "unknown_dep": "the next departure",
        "unknown_soc": "?",
        "ahead_title": "{name}: charge tomorrow",
        "ahead_charge": "Tomorrow ({day}) charging will be needed: {kwh} kWh are missing for the departure {dep_day} {dep}. Latest start {start_pref} at {pref} kW, at full power {start}.",
        "ahead_charge_nostart": "Tomorrow ({day}) charging will be needed: {kwh} kWh are missing for the departure {dep_day} {dep}.",
        "ahead_sun": "Tomorrow ({day}) it pays to charge ahead with the sun: from {from} to {to} about {kwh} kWh. That replaces grid energy before the departure {dep_day} {dep}.",
        "ahead_sun_today": "Today it pays to charge ahead with the sun: from {from} to {to} about {kwh} kWh. That replaces grid energy before the departure {dep_day} {dep}.",
        "weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    },
}


def notice_text(language: str, n: Notice, name: str, departure: datetime | None) -> tuple[str, str]:
    """(title, message) of a warning in German or English (anything else falls back to English)."""
    t = TEXTS["de" if (language or "").lower().startswith("de") else "en"]
    dep = departure.strftime("%H:%M") if departure is not None else t["unknown_dep"]
    soc = f"{n.soc:.0f}" if n.soc is not None else t["unknown_soc"]
    values = dict(name=name, soc=soc, dep=dep, kwh=f"{n.shortfall_kwh:.1f}", target=f"{n.target_soc:.0f}", km=f"{n.km:.0f}",
                  possible=f"{n.max_possible_kwh:.1f}" if n.max_possible_kwh is not None else "?")
    return t["title"].format(**values), t[n.kind].format(**values)


def ahead_text(language: str, a: Ahead, name: str, pref_kw: float | None = None, today: Any = None) -> tuple[str, str]:
    """(title, message) of the heads-up for tomorrow in German or English."""
    t = TEXTS["de" if (language or "").lower().startswith("de") else "en"]
    wd = t["weekdays"]
    hm = lambda x: x.strftime("%H:%M")  # noqa: E731
    values = dict(name=name, day=wd[a.day.weekday()], dep_day=wd[a.departure.weekday()], dep=hm(a.departure), kwh=f"{a.kwh:.0f}",
                  pref=f"{pref_kw:g}" if pref_kw else "?")
    if a.kind == "sun":
        values.update({"from": hm(a.sun_from) if a.sun_from else "?", "to": hm(a.sun_to) if a.sun_to else "?"})
        key = "ahead_sun_today" if today is not None and a.day == today else "ahead_sun"
        return t["ahead_title"].format(**values), t[key].format(**values)
    def when(x):
        return f"{wd[x.weekday()]} {hm(x)}" if x is not None else "?"
    values.update(start=when(a.latest_start), start_pref=when(a.latest_start_pref))
    key = "ahead_charge" if a.latest_start is not None and a.latest_start_pref is not None else "ahead_charge_nostart"
    return t["ahead_title"].format(**values), t[key].format(**values)
