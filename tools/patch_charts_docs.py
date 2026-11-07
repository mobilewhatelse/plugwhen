"""One-off: documentation of the two charts (kept for the record)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def edit(rel, pairs):
    p = ROOT / rel
    s = p.read_text(encoding="utf-8")
    for a, b in pairs:
        assert s.count(a) == 1, f"{rel}: {a[:70]}"
        s = s.replace(a, b)
    p.write_text(s, encoding="utf-8")


EN = """## Does the learning help? (a check on your own history)

Sensor **Does learning help?** (and a card with two charts in the dashboard). It walks through the history of *your* car day by day,
and on each day the model only knows the days before it. Two questions:

- **Would the range have been enough?** With the fixed reserve alone (what a car without learning would keep) and with the reserve lifted
  by what was learned for that weekday (the larger of the reserve and the weekday's 80th percentile). Two bars show the share of days.
- **Was the departure guessed right?** The learned usual hour of the first trip against the real one, within one hour (the history knows
  the hour, not the minute), as one bar per weekday.

Verdict: **learning helps** (at least 5 percentage points more days covered), **reserve is enough** (less than 2 points: the reserve alone
does it, the learned value costs nothing but brings little), **little difference**, or **too little data** (fewer than 21 days could be
checked). Days without kilometres are not counted. On the author's car the reserve alone covers about 88 % of the days and with the
learned value about 90 %; the departure hour is what the history helps most with.

The learn mode card has a second chart: per day, the hours in which the plan and the wallbox agreed (green) and the hours in which they
differed (red).

"""
DE = """## Bringt das Lernen etwas? (eine Prüfung am eigenen Verlauf)

Sensor **Bringt das Lernen etwas?** (und eine Karte mit zwei Grafiken im Dashboard). Er geht den Verlauf *Ihres* Autos Tag für Tag durch, und an
jedem Tag kennt das Modell nur die Tage davor. Zwei Fragen:

- **Hätte die Reichweite gereicht?** Mit der festen Reserve allein (was ein Auto ohne Lernen vorhielte) und mit der Reserve, angehoben um das
  für den Wochentag Gelernte (der größere Wert aus Reserve und 80. Perzentil des Wochentags). Zwei Balken zeigen den Anteil der Tage.
- **Wurde die Abfahrt richtig geraten?** Die gelernte übliche Stunde der ersten Fahrt gegen die echte, auf eine Stunde genau (der Verlauf kennt
  die Stunde, nicht die Minute), als ein Balken je Wochentag.

Urteil: **Lernen hilft** (mindestens 5 Prozentpunkte mehr Tage gedeckt), **Reserve reicht** (weniger als 2 Punkte: die Reserve allein genügt, der
gelernte Wert kostet nichts, bringt aber wenig), **kaum Unterschied** oder **zu wenig Daten** (weniger als 21 Tage prüfbar). Tage ohne Kilometer
zählen nicht. Beim Auto des Autors deckt die Reserve allein etwa 88 % der Tage, mit dem Gelernten etwa 90 %; am meisten hilft der Verlauf bei der
Abfahrtszeit.

Die Karte des Lernmodus hat eine zweite Grafik: je Tag die Stunden, in denen Plan und Wallbox übereinstimmten (grün), und die Stunden, in denen
sie abwichen (rot).

"""

edit("README.md", [
    ("## Learn mode\n", EN + "## Learn mode\n"),
    ("| `select` Mode | `off` or `learn` |", "| `select` Mode | `off` or `learn` |\n| `sensor` Does learning help? | `learning_helps`, `reserve_enough`, `little`, `too_little_data`; attributes `coverage_reserve_pct`, `coverage_learned_pct`, `departure_right_pct`, `chart` |"),
    ("**Status: version 0.5.0 in development**", "**Status: version 0.5.1 in development**"),
])
edit("docs/ANLEITUNG.md", [
    ("## Lernmodus\n", DE + "## Lernmodus\n"),
    ("Stand: Version 0.5.0 (in Entwicklung).", "Stand: Version 0.5.1 (in Entwicklung)."),
])
edit("CHANGELOG.md", [
    ("# Changelog\n", """# Changelog

## 0.5.1 (unreleased) - does the learning help, two charts

- **Sensor "Does learning help?"**: walks through the history of the car day by day (the model only knows the days before each day):
  how many days the range would have been enough with the fixed reserve alone and with the learned value, and how often the departure
  hour was guessed right (within one hour) per weekday. Verdict: *learning helps*, *reserve is enough*, *little difference*, *too little
  data* (fewer than 21 days).
- **Two charts as SVG** (attribute `chart`, shown by a normal markdown card, no custom card): the check above (two bars and one bar per
  weekday) and, in learn mode, plan against reality per day (green = agreed, red = differed). German and English labels.
- Dashboard: card *Does learning help?* with the verdict in plain words and the chart; the learn mode card has its chart.
"""),
])
m = ROOT / "custom_components" / "plugwhen" / "manifest.json"
d = json.loads(m.read_text(encoding="utf-8"))
d["version"] = "0.5.1"
m.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("ok")
