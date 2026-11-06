"""One-off: documentation of learn mode (kept for the record)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def edit(rel, pairs):
    p = ROOT / rel
    s = p.read_text(encoding="utf-8")
    for a, b in pairs:
        assert s.count(a) == 1, f"{rel}: {a[:70]}"
        s = s.replace(a, b)
    p.write_text(s, encoding="utf-8")


EN = """## Learn mode

Per car the select *Mode* has two settings today: **Off** and **Learn** (default; the last choice is kept over a restart). In **Learn**
mode Plugwhen **switches nothing**. It only works out, for every moment, what it *would* do and writes it down:

- the sensor **Would switch** says `charge`, `pause` or `none` (no decision), with the reason (in a planned window, waiting for the next
  window, the plan is done, the target is tight so as much as possible at once, state of charge unknown, car not plugged in, nothing
  needed), when it expects the decision to change, and the planned power;
- a **journal** of the last decisions (only changes are written down);
- a **comparison with reality** per day (kept for 60 days), if you set the *charging* entity and/or the *wallbox energy counter*: how long
  the decision and the wallbox agreed, how many hours the wallbox charged although Plugwhen would have paused, and how much energy came in
  those hours, and the other way round. Example: *would have paused 3 h, but 9 kWh came in*.

Unknown things are never decisions: unknown state of charge, car not plugged in, nothing to charge, no departure give *no decision* and
the wallbox keeps doing what it does. A target that cannot be reached by departure gives `charge` at once (never wait when time is short).

This is the evidence on which switching can be offered later: only when the log shows that Plugwhen's decisions would have been right
for several days. **Switching itself is not built yet.** The dashboard has a *Learn mode* card with the decision, the comparison of the
last 7 days and the journal.

"""
DE = """## Lernmodus

Je Auto hat die Auswahl *Betriebsart* heute zwei Stellungen: **Aus** und **Lernen** (Standard; die letzte Wahl bleibt über einen Neustart
erhalten). Im Lernmodus **schaltet Plugwhen nichts**. Es berechnet nur für jeden Moment, was es tun *würde*, und schreibt es auf:

- der Sensor **Würde schalten** sagt `laden`, `pausieren` oder `keine Entscheidung`, mit Grund (im geplanten Fenster, wartet auf das nächste
  Fenster, der Plan ist abgearbeitet, das Ziel ist knapp also so viel wie möglich sofort, Ladestand unbekannt, Auto nicht angesteckt, nichts
  nötig), wann sich die Entscheidung voraussichtlich ändert und mit welcher Leistung;
- ein **Protokoll** der letzten Entscheidungen (nur Änderungen werden notiert);
- ein **Vergleich mit der Wirklichkeit** je Tag (60 Tage aufgehoben), wenn Sie die Entität *lädt gerade* und/oder den *Energiezähler der
  Wallbox* eingetragen haben: wie lange Entscheidung und Wallbox übereinstimmten, wie viele Stunden die Wallbox lud, obwohl Plugwhen
  pausiert hätte, und wie viel Energie in diesen Stunden kam, und umgekehrt. Beispiel: *hätte 3 h pausiert, aber 9 kWh kamen an*.

Unbekanntes ist nie eine Entscheidung: unbekannter Ladestand, Auto nicht angesteckt, nichts zu laden, keine Abfahrt ergeben *keine Entscheidung*,
die Wallbox macht weiter, was sie macht. Ein Ziel, das bis zur Abfahrt nicht erreichbar ist, ergibt `laden` sofort (nie warten, wenn die Zeit knapp ist).

Das ist der Beleg, auf dem das Schalten später angeboten werden kann: erst wenn das Protokoll zeigt, dass die Entscheidungen von Plugwhen
mehrere Tage lang richtig gewesen wären. **Das Schalten selbst ist noch nicht gebaut.** Das Dashboard hat eine Karte *Lernmodus* mit der
Entscheidung, dem Vergleich der letzten 7 Tage und dem Protokoll.

"""

edit("README.md", [
    ("## Entities per vehicle\n", EN + "## Entities per vehicle\n"),
    ("| `number` Reserve, `switch` Learn kilometres per weekday, `switch` Warn when the car will not be ready | settings |",
     "| `sensor` Would switch | learn mode: `charge`, `pause`, `none`, `off`; attributes `reason`, `planned_kw`, `until`, `summary`, `journal` |\n"
     "| `select` Mode | `off` or `learn` |\n"
     "| `number` Reserve, `switch` Learn kilometres per weekday, `switch` Warn when the car will not be ready | settings |"),
    ("**Status: version 0.4.0 in development** (learned week, need, charge plan with sun first and the rest spread, warning,\n> recorded plug-in times, potential calculator, ready-made dashboard).",
     "**Status: version 0.5.0 in development** (learned week, need, charge plan with sun first and the rest spread, warning,\n> recorded plug-in times, potential calculator, ready-made dashboard, learn mode)."),
])
edit("docs/ANLEITUNG.md", [
    ("## Grenzen\n", DE + "## Grenzen\n"),
    ("Stand: Version 0.4.0 (in Entwicklung).", "Stand: Version 0.5.0 (in Entwicklung)."),
])
edit("CHANGELOG.md", [
    ("# Changelog\n", """# Changelog

## 0.5.0 (unreleased) - learn mode

- **Mode per car** (select, *Off* or *Learn*, default Learn, the last choice survives a restart) and the sensor **Would switch**:
  in learn mode Plugwhen switches nothing, it works out what it *would* do (charge, pause, no decision, with the reason, until when,
  planned power) and writes it down. Unknown state of charge, a car that is not plugged in, nothing to charge or no departure are never
  decisions; a target that cannot be reached gives *charge* at once.
- **Comparison with reality** (needs the charging entity and/or the wallbox energy counter): per day how long decision and wallbox
  agreed, hours the wallbox charged although Plugwhen would have paused and the energy that came in, and the other way round; journal of
  the last decisions; both kept in a small store (60 days). Gaps longer than 20 minutes (restart, outage) are not attributed.
- Dashboard: card *Learn mode* (decision with reason, comparison of the last 7 days, journal, mode). Documentation: section *Learn mode*.
- Preparation for switching (planned): the log is the evidence on which it can be offered; switching itself is not built yet.
"""),
])
print("ok")
