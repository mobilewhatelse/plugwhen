"""Texts of the warning that the car will not be ready (pure Python)."""

from __future__ import annotations

from datetime import datetime

try:  # inside Home Assistant the module lives in a package, the tests import it flat
    from .notice import Notice
except ImportError:  # pragma: no cover
    from notice import Notice

TEXTS = {
    "de": {
        "title": "{name}: morgen nicht bereit",
        "plug_in": "Bitte anstecken: {name} liegt bei {soc} %, bis {dep} fehlen {kwh} kWh (Ziel {target} %, {km} km Reichweite).",
        "low": "{name} liegt bei {soc} %, bis {dep} fehlen {kwh} kWh (Ziel {target} %, {km} km Reichweite). Ob angesteckt ist, ist unbekannt.",
        "too_late": "{name} wird bis {dep} nicht mehr voll: es fehlen {kwh} kWh, möglich sind noch höchstens {possible} kWh (Ziel {target} %).",
        "not_reachable": "{name}: das Ziel von {target} % ({km} km Reichweite) ist mit dem Akku nicht erreichbar.",
        "unknown_dep": "der nächsten Abfahrt",
        "unknown_soc": "?",
    },
    "en": {
        "title": "{name}: not ready for tomorrow",
        "plug_in": "Please plug in: {name} is at {soc} %, {kwh} kWh are missing by {dep} (target {target} %, {km} km range).",
        "low": "{name} is at {soc} %, {kwh} kWh are missing by {dep} (target {target} %, {km} km range). It is not known whether it is plugged in.",
        "too_late": "{name} will not be full by {dep}: {kwh} kWh are missing, at most {possible} kWh can still be charged (target {target} %).",
        "not_reachable": "{name}: the target of {target} % ({km} km range) cannot be reached with this battery.",
        "unknown_dep": "the next departure",
        "unknown_soc": "?",
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
