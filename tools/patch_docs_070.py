"""One-off: documentation of 0.7.0: charging habit, look-ahead, house-only add (kept for the record)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def edit(rel, pairs):
    p = ROOT / rel
    s = p.read_text(encoding="utf-8")
    for a, b in pairs:
        assert s.count(a) == 1, f"{rel}: {a[:80]}"
        s = s.replace(a, b)
    p.write_text(s, encoding="utf-8")


EN = """## Looking ahead: when must I charge at the latest?

The plan reaches the next departure; on the same day it is often too late. The **look-ahead** goes up to **fourteen days and ten
departures** ahead and answers, **for normal behaviour** (the learned trips): *until when does the charge last, and by when must
charging start at the latest?* For every departure it works out the energy that is missing (the car must leave with at least the range
the need asks for, after each trip it has used the expected energy) and the **latest start**: the departure minus the time needed
at the preferred power and at full power.

- **Charge ahead with the sun** (with a solar forecast, e.g. of the Energy dashboard): sun that is left over in an earlier window (for
  example the weekend) is used for the grid energy of a later departure (for example Wednesday), as far as the battery stays below
  80 % and the sun lasts. Example: *Saturday 10 to 13 h, 14 kWh, replaces grid energy before Wednesday 07:00.* The chart *The next
  departures* shows where the energy of each departure comes from: sun in the same window (yellow), sun charged ahead (orange), grid (blue).
- **A heads-up on the evening before:** from the evening hour of the warning on, Plugwhen tells you that **tomorrow** charging will be
  needed (with the latest start) or that charging ahead with the sun pays tomorrow. Once per day and kind. Charging that has to happen
  today is the job of the plug-in warning.
- **Without a solar plant** nothing is pre-charged; the look-ahead then only says what each departure needs from the grid and by when.
- It **recommends only; nothing is switched.** Assumptions are open: the time the car is away follows from the length of the trip (3 h
  plus 1 h per 12 km, 3 to 10 h) until it is learned from the plug-in times; the trips are the typical ones. The solar forecast reaches as
  far as the forecast provider delivers it, beyond that the look-ahead counts on the grid.
- The plan chart shows the latest start at full power as a dashed line.

## When do you charge? (the charging habit)

Sensor **Charging habit** (the share of the energy charged at night, 20 to 7 h, over the last 90 days) and a chart per weekday: the
energy on an average Monday, Tuesday and so on, **during the day (9 to 17 h)**, **at night** and in between. It needs only the
energy counter of the wallbox, no solar plant, and it does not judge (with a night tariff, night charging is what you want). It shows where charging could
move: a weekday with much night charging is where grid energy and peaks come from. Fewer than 28 days of data give *too little data*.

"""
DE = """## Vorausschau: wann muss ich spätestens laden?

Der Plan reicht bis zur nächsten Abfahrt; am selben Tag ist es oft schon zu spät. Die **Vorausschau** geht bis zu **vierzehn Tage und zehn
Abfahrten** weit und beantwortet **bei normalem Verhalten** (den gelernten Fahrten): *Bis wann reicht der Ladestand, und wann muss das Laden
spätestens beginnen?* Für jede Abfahrt wird die fehlende Energie gerechnet (das Auto muss mit mindestens der Reichweite losfahren, die der Bedarf
verlangt; nach jeder Fahrt hat es die erwartete Energie verbraucht) und der **späteste Start**: die Abfahrt minus die Zeit, die bei bevorzugter
Leistung und bei voller Leistung nötig ist.

- **Mit Sonne vorladen** (mit Solarprognose, z. B. aus dem Energie-Dashboard): Sonne, die in einem früheren Fenster übrig ist (zum Beispiel am
  Wochenende), wird für den Netzstrom einer späteren Abfahrt genutzt (zum Beispiel Mittwoch), solange der Akku unter 80 % bleibt und die Sonne reicht.
  Beispiel: *Samstag 10 bis 13 Uhr, 14 kWh, ersetzt Netzstrom vor Mittwoch 07:00.* Die Grafik *Die nächsten Abfahrten* zeigt, woher der Strom jeder
  Abfahrt kommt: Sonne im selben Fenster (gelb), mit Sonne vorgeladen (orange), Netz (blau).
- **Eine Vorwarnung am Vorabend:** Ab der Abendstunde der Warnung sagt Plugwhen, dass **morgen** geladen werden muss (mit dem spätesten Start) oder
  dass sich morgen das Vorladen mit Sonne lohnt. Einmal je Tag und Art. Laden, das heute geschehen muss, ist Sache der Anstecken-Warnung.
- **Ohne Solaranlage** wird nichts vorgeladen; die Vorausschau sagt dann nur, was jede Abfahrt aus dem Netz braucht und bis wann.
- Sie **empfiehlt nur, es wird nichts geschaltet.** Die Annahmen sind offen: Wie lange das Auto weg ist, folgt aus der Länge der Fahrt (3 Stunden plus
  1 Stunde je 12 km, 3 bis 10 Stunden), bis es aus den Steckzeiten gelernt wird; die Fahrten sind die typischen. Die Solarprognose reicht so weit, wie
  der Anbieter sie liefert, danach rechnet die Vorausschau mit dem Netz.
- Das Plan-Bild zeigt den spätesten Start bei voller Leistung als gestrichelte Linie.

## Wann laden Sie? (die Ladegewohnheit)

Sensor **Ladegewohnheit** (Anteil der Energie, die nachts, 20 bis 7 Uhr, in den letzten 90 Tagen geladen wurde) und eine Grafik je Wochentag: die Energie an
einem durchschnittlichen Montag, Dienstag und so weiter, **tagsüber (9 bis 17 Uhr)**, **nachts** und dazwischen. Sie braucht nur den Energiezähler der
Wallbox, keine Solaranlage, und sie bewertet nicht (mit Nachtstrom ist nachts laden genau richtig). Sie zeigt, wohin sich das Laden verschieben ließe: Ein Wochentag mit viel
Laden in der Nacht ist, wo Netzstrom und Spitzen herkommen. Unter 28 Tagen Daten steht *zu wenig Daten*.

"""

edit("README.md", [
    ("## Does the learning help? (a check on your own history)\n", EN + "## Does the learning help? (a check on your own history)\n"),
    ("| quarter-hour add of the potential calculator | 0.7 kW | the 5-minute statistics of the grid import of the chosen peak guard: highest quarter hour above its hour's mean, 80th percentile |",
     "| quarter-hour add of the potential calculator | 0.7 kW | the 5-minute statistics of the grid import of the chosen peak guard, **for the house alone** (hours in which the wallbox delivered nothing) and **by load level** (quiet, medium, high hours): highest quarter hour above its hour's mean, 80th percentile; a level needs 12 hours, until then 0.7 kW applies there; the hours are collected for good |"),
    ("**Status: version 0.6.1 in development**", "**Status: version 0.7.0 in development**"),
    ("- `sensor` Would switch | learn mode:", "- `sensor` Would switch | learn mode:") if False else ("| `select` Mode | `off` or `learn` |", "| `select` Mode | `off` or `learn` |\n| `sensor` Charging habit | share of the energy charged at night; attributes `by_weekday`, `day_share_pct`, `weekend_share_pct`, `chart` |"),
])
edit("docs/ANLEITUNG.md", [
    ("## Bringt das Lernen etwas? (eine Prüfung am eigenen Verlauf)\n", DE + "## Bringt das Lernen etwas? (eine Prüfung am eigenen Verlauf)\n"),
    ("| Viertelstunden-Zuschlag des Potenzialrechners | 0,7 kW | die 5-Minuten-Statistik des Netzbezugs des gewählten Wächters: höchste Viertelstunde über dem Stundenmittel, 80. Perzentil |",
     "| Viertelstunden-Zuschlag des Potenzialrechners | 0,7 kW | die 5-Minuten-Statistik des Netzbezugs des gewählten Wächters, **nur für das Haus** (Stunden ohne Wallbox-Energie) und **nach Lastzustand** (ruhige, mittlere, hohe Stunden): höchste Viertelstunde über dem Stundenmittel, 80. Perzentil; ein Zustand braucht 12 Stunden, bis dahin gilt dort 0,7 kW; die Stunden werden dauerhaft gesammelt |"),
    ("Stand: Version 0.6.1 (in Entwicklung).", "Stand: Version 0.7.0 (in Entwicklung)."),
])
edit("CHANGELOG.md", [
    ("# Changelog\n", """# Changelog

## 0.7.0 (unreleased) - look ahead, charging habit, house-only add

- **Look-ahead: when must I charge at the latest?** Up to fourteen days and ten departures ahead, for normal behaviour (the learned trips):
  until when the charge lasts (`lasts_until`), the first charging that is needed (`first_need`: day, latest start at the preferred power and at
  full power) and per departure the energy that is missing. Chart *The next departures* (sun in the same window, sun charged ahead, grid).
- **Charge ahead with the sun** (needs a solar forecast, works without a plant: then nothing is pre-charged): sun left over in an earlier window
  (the weekend) covers the grid energy of a later departure (Wednesday), as far as the battery stays below 80 %. A recommendation, nothing is switched.
- **Heads-up on the evening before:** tomorrow charging is needed (with the latest start), or charging ahead with the sun pays tomorrow. Once per
  day and kind, German and English texts. The plan chart shows the latest start at full power as a dashed line.
- **Charging habit:** sensor and chart, the energy per weekday during the day (9 to 17 h), at night (20 to 7 h) and in between, from the energy
  counter of the wallbox only (no solar plant needed, no judgement).
- **The quarter-hour add is measured for the house alone and by load level.** One learned value (0.26 kW in one house) was wrong: quiet hours
  need about 0.1 kW, loaded hours several, and in loaded hours the car's own current steps and the throttling are in the grid import and are modelled
  separately. Hours without wallbox energy are collected for good (the recorder keeps 5-minute values for ten days); a load level with fewer than
  12 hours uses the default 0.7 kW.
- **Learn mode also records the energy delivered although nothing was needed** (for example charging with the sun): `kwh_needless` and
  `needless_h` in the summary, a line on the card. The automatic mode needs that number.
"""),
])
m = ROOT / "custom_components" / "plugwhen" / "manifest.json"
d = json.loads(m.read_text(encoding="utf-8"))
d["version"] = "0.7.0"
m.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("ok")
