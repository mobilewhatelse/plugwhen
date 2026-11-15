"""Bug report on request (button 'Send bug report'): what helps to find an error, never who.

Only on a press, independent of 'Share anonymous data'; the notification afterwards shows exactly what was sent. Never names, entity ids, addresses, IPs or values that
identify a home. Entity ids in texts become their kind ("select.wallbox_mode" -> "select"), names of cars become "Auto 1".
Pure functions here (tested without Home Assistant); the coordinator collects the raw values.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections import deque
from datetime import datetime
from typing import Any

MAX_LINES = 20         # warnings kept (only in memory, gone after a restart)
SLOW_S = 15            # a command taking longer counts as slow (wallbox over the cloud)
MAX_BYTES = 8000       # the server takes 16 KB with the text; the oldest log lines go first

_URL = re.compile(r"\b[a-z][a-z0-9+.-]*://\S+", re.I)
_MAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_IP = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b")
_ENTITY = re.compile(r"\b([a-z][a-z0-9_]*)\.[a-z0-9_]+\b")
# entry ids (ULID, hex), serials, vehicle identification numbers: long runs of letters and digits with at least one digit
_LONG_ID = re.compile(r"\b(?=[A-Za-z0-9]*\d)(?=[A-Za-z0-9]*[A-Za-z])[A-Za-z0-9]{12,}\b")

_TS = re.compile(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:[+-]\d{2}:?\d{2}|Z)?")
_CLOCK = re.compile(r"(?<![\d.:])\d{1,2}:\d{2}(?::\d{2})?(?![\d:])")


def anonym(text: Any, names: list[str] | None = None, limit: int = 300) -> str | None:
    """A text without what identifies anybody: names (longest first), URLs, e-mail, IPs, long ids, entity ids (kind kept)."""
    if text is None:
        return None
    t = str(text)
    for i, n in enumerate(sorted({x for x in (names or []) if x and len(x.strip()) >= 2}, key=len, reverse=True)):
        t = re.sub(re.escape(n.strip()), "<name>", t, flags=re.I)
    t = _URL.sub("<url>", t)
    t = _MAIL.sub("<mail>", t)
    t = _IP.sub("<ip>", t)
    t = _TS.sub("<zeitpunkt>", t)
    t = _CLOCK.sub("<uhrzeit>", t)
    t = _LONG_ID.sub("<id>", t)
    t = _ENTITY.sub(lambda m: m.group(1), t)
    return t.strip()[:limit]


class Calls:
    """How a wallbox setting answers: per entity number of commands, time of the service call, failures, value taken or not."""

    def __init__(self) -> None:
        self.items: dict[str, dict[str, Any]] = {}

    def call(self, entity_id: str, seconds: float, error: BaseException | None = None) -> None:
        r = self.items.setdefault(entity_id, {"n": 0, "sum": 0.0, "max": 0.0, "slow": 0, "failed": 0, "errors": {}})
        r["n"] += 1
        r["sum"] += seconds
        r["max"] = max(r["max"], seconds)
        if seconds > SLOW_S:
            r["slow"] += 1
        if error is not None:
            r["failed"] += 1
            kind = type(error).__name__
            r["errors"][kind] = r["errors"].get(kind, 0) + 1

    def reply(self, entity_id: str, taken: bool, seconds: float | None) -> None:
        r = self.items.setdefault(entity_id, {"n": 0, "sum": 0.0, "max": 0.0, "slow": 0, "failed": 0, "errors": {}})
        key = "taken" if taken else "not_taken"
        r[key] = r.get(key, 0) + 1
        if taken and seconds is not None:
            r["reply_max"] = round(max(r.get("reply_max", 0.0), seconds), 1)

    def summary(self, entity_id: str) -> dict[str, Any] | None:
        r = self.items.get(entity_id)
        if not r:
            return None
        out = {"befehle": r["n"], "mittel_s": round(r["sum"] / r["n"], 1) if r["n"] else None, "laengste_s": round(r["max"], 1),
               "langsam": r["slow"], "fehlgeschlagen": r["failed"], "fehlerarten": dict(r["errors"])}
        for k, name in (("taken", "uebernommen"), ("not_taken", "nicht_uebernommen"), ("reply_max", "uebernahme_laengste_s")):
            if k in r:
                out[name] = r[k]
        return out

    def text(self, entity_id: str) -> str | None:
        """One line (the server keeps only three levels): '3 Befehle, Mittel 21.3 s, längste 25.0 s, 1 langsam, ...'."""
        s = self.summary(entity_id)
        if not s:
            return None
        parts = [f"{s['befehle']} Befehle", f"Mittel {s['mittel_s']} s", f"längste {s['laengste_s']} s", f"{s['langsam']} langsam",
                 f"{s['fehlgeschlagen']} fehlgeschlagen"]
        if s["fehlerarten"]:
            parts.append("Fehler " + ", ".join(f"{k} {v}x" for k, v in s["fehlerarten"].items()))
        if "uebernommen" in s or "nicht_uebernommen" in s:
            parts.append(f"Wert übernommen {s.get('uebernommen', 0)}, nicht übernommen {s.get('nicht_uebernommen', 0)}")
        if "uebernahme_laengste_s" in s:
            parts.append(f"Übernahme längste {s['uebernahme_laengste_s']} s")
        return ", ".join(parts)


class Lines(logging.Handler):
    """The last warnings and errors of Plugwhen, only in memory; anonymised when the report is built, not before."""

    def __init__(self) -> None:
        super().__init__(logging.WARNING)
        self.lines: deque = deque(maxlen=MAX_LINES)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.lines.append((record.created, record.levelname, record.getMessage()))   # shown as "vor 2.0 h", never the clock
        except Exception:  # noqa: BLE001 - logging must never fail
            pass


def sensor_state(state: Any, now: datetime | None = None) -> str:
    """'ok', 'unbekannt', 'nicht_verfuegbar' or 'fehlt' (entity not there); with the age class of the last value."""
    if state is None:
        return "fehlt"
    s = str(getattr(state, "state", ""))
    if s == "unavailable":
        return "nicht_verfuegbar"
    if s in ("unknown", ""):
        return "unbekannt"
    changed = getattr(state, "last_reported", None) or getattr(state, "last_updated", None)
    if now is not None and isinstance(changed, datetime):
        h = (now - changed).total_seconds() / 3600
        return "ok" if h < 1 else "ok, älter als 1 h" if h < 24 else "ok, älter als 1 Tag"
    return "ok"


def rel_h(when: Any, now: datetime) -> str | None:
    """'in 2.5 h' or 'vor 1.0 h': no clock time (when someone leaves home is nobody's business), only the distance."""
    if isinstance(when, str):
        try:
            when = datetime.fromisoformat(when)
        except ValueError:
            return None
    if not isinstance(when, datetime):
        return None
    h = (when - now).total_seconds() / 3600
    return f"in {h:.1f} h" if h >= 0 else f"vor {-h:.1f} h"


def windows_text(plan: dict[str, Any] | None, now: datetime, limit: int = 4) -> str | None:
    """The next windows of a charge plan, relative: 'in 2.0 h für 1.5 h 6.7 kWh (max 7.4 kW)'."""
    if not isinstance(plan, dict):
        return None
    out = []
    for w in (plan.get("windows") or [])[:limit]:
        s, e = w.get("start"), w.get("end")
        s = datetime.fromisoformat(s) if isinstance(s, str) else s
        e = datetime.fromisoformat(e) if isinstance(e, str) else e
        if not isinstance(s, datetime) or not isinstance(e, datetime):
            continue
        out.append(f"{rel_h(s, now)} für {(e - s).total_seconds() / 3600:.2f} h {w.get('energy_kwh')} kWh (max {w.get('peak_kw')} kW)")
    head = f"Status {plan.get('status')}, benötigt {plan.get('needed_kwh')} kWh, geplant {plan.get('planned_kwh')} kWh"
    return head + ("; " + "; ".join(out) if out else "; keine Fenster")


def ago(t: Any) -> str:
    """A log line's time (seconds since the epoch) as 'vor 2.0 h'; anything else is masked."""
    if isinstance(t, (int, float)):
        return f"vor {max(0.0, time.time() - t) / 3600:.1f} h"
    return "vor ? h"


def state_text(entity_id: str, state: Any, now: datetime) -> str:
    """What a setting says now, without a clock time: a button's last press as 'gedrückt vor 3.2 h', a time setting only as
    'gesetzt' (it would tell when somebody leaves), any other time stamp relative."""
    dom = entity_id.split(".")[0]
    s = str(getattr(state, "state", state))
    if s in ("unknown", "unavailable", ""):
        return s or "unbekannt"
    if dom in ("button", "input_button"):
        return f"gedrückt {rel_h(s, now) or '?'}"
    if dom in ("time", "input_datetime") or _CLOCK.fullmatch(s.strip()):
        return "gesetzt"
    if _TS.fullmatch(s.strip()):
        return rel_h(s, now) or "<zeitpunkt>"
    return s


def bericht(version: str, ha_version: str, einrichtung: dict[str, Any], autos: list[dict[str, Any]], zeilen: list[tuple],
            fehler: dict[str, Any], names: list[str]) -> dict[str, Any]:
    """The report: everything given here is anonymised once more (a name in a log line, an id in an error text)."""
    def clean(x: Any) -> Any:
        if isinstance(x, dict):
            return {str(k): clean(v) for k, v in x.items()}
        if isinstance(x, (list, tuple)):
            return [clean(v) for v in x]
        if isinstance(x, str):
            return anonym(x, names)
        return x

    def flat(a: dict[str, Any]) -> dict[str, Any]:   # per car only single values: the server keeps three levels
        return {str(k): (v if isinstance(v, (bool, int, float)) or v is None else anonym(json.dumps(v, ensure_ascii=False)
                         if isinstance(v, (dict, list)) else v, names)) for k, v in a.items()}

    b = {"schema": 1, "version": version, "ha_version": ha_version, "einrichtung": clean(einrichtung),
         "autos": [flat(a) for a in autos][:10], "fehler": {k: anonym(v, names) for k, v in fehler.items() if v},
         "protokoll": [f"{ago(t)} {lvl} {anonym(msg, names, 240)}" for t, lvl, msg in zeilen][-MAX_LINES:]}
    while b["protokoll"] and len(json.dumps(b, ensure_ascii=False).encode()) > MAX_BYTES:
        b["protokoll"].pop(0)
    return b


def anzeige(b: dict[str, Any], de: bool, gesendet: bool) -> str:
    """The notification after the press: exactly what was sent (or, if sending failed, what would have been sent)."""
    if gesendet:
        head = ("**Danke, der Fehlerbericht ist angekommen.** Gesendet wurde genau das:" if de else
                "**Thank you, the bug report was received.** Exactly this was sent:")
    else:
        head = ("**Senden hat nicht geklappt**, bitte später noch einmal. Gesendet worden wäre genau das:" if de else
                "**Sending failed**, please try again later. Exactly this would have been sent:")
    lines = [head, ""]
    lines.append(f"- Version {b['version']}, Home Assistant {b['ha_version']}")
    for i, a in enumerate(b.get("autos") or [], 1):
        lines.append(f"- Auto {i}: " + ", ".join(f"{k}: {v}" for k, v in a.items() if v not in (None, {}, [], "")))
    for k, v in (b.get("fehler") or {}).items():
        lines.append(f"- {k}: {v}")
    if b.get("protokoll"):
        lines += ["", "Protokoll:" if de else "Log:"] + [f"    {x}" for x in b["protokoll"]]
    lines += ["", ("Keine Namen, Entitäts-IDs, Adressen oder Uhrzeiten. Einrichtung: " if de else
                   "No names, entity ids, addresses or clock times. Setup: ")
              + ", ".join(f"{k} {v}" for k, v in (b.get("einrichtung") or {}).items())]
    return "\n".join(lines)
