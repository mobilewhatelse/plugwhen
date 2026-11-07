"""One-off: documentation of the departure statement and version 0.6.1 (kept for the record)."""
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


edit("README.md", [
    ("- **Was the departure guessed right?** The learned usual hour of the first trip against the real one, within one hour (the history knows\n  the hour, not the minute), as one bar per weekday.\n- **Would the car have been ready in time?** A plan that finishes at the usual (median) departure against one that finishes at the early\n  departure, as two bars.\n",
     "- **Would the car have been ready in time?** A plan that finishes at the usual (median) departure against one that finishes at the early\n  departure (20th percentile), as two bars and then per weekday for the early plan. Real departures vary, so the useful number is not\n  \"guessed to the hour\" but \"ready in time\"; that is why the plan aims at the early departure.\n"),
    ("Verdict: **learning helps** (at least 5 percentage points more days covered), **reserve is enough**",
     "Verdict: **learning helps** (at least 5 percentage points more days covered), **learning helps for the departure** (the kilometres hardly help,\nbut the early plan is ready in time on at least 10 points more days than the median plan), **reserve is enough**"),
    ("**Status: version 0.6.0 in development**", "**Status: version 0.6.1 in development**"),
])
edit("docs/ANLEITUNG.md", [
    ("- **Wurde die Abfahrt richtig geraten?** Die gelernte übliche Stunde der ersten Fahrt gegen die echte, auf eine Stunde genau (der Verlauf kennt\n  die Stunde, nicht die Minute), als ein Balken je Wochentag.\n- **Wäre das Auto rechtzeitig fertig gewesen?** Ein Plan bis zur üblichen (mittleren) Abfahrt gegen einen bis zur frühen Abfahrt, als zwei Balken.\n",
     "- **Wäre das Auto rechtzeitig fertig gewesen?** Ein Plan bis zur üblichen (mittleren) Abfahrt gegen einen bis zur frühen Abfahrt (20. Perzentil), als\n  zwei Balken und dann je Wochentag für den frühen Plan. Echte Abfahrten schwanken, deshalb ist nicht „auf die Stunde erraten“ die nützliche Zahl,\n  sondern „rechtzeitig fertig“; darum zielt der Plan auf die frühe Abfahrt.\n"),
    ("Urteil: **Lernen hilft** (mindestens 5 Prozentpunkte mehr Tage gedeckt), **Reserve reicht**",
     "Urteil: **Lernen hilft** (mindestens 5 Prozentpunkte mehr Tage gedeckt), **Lernen hilft bei der Abfahrt** (die Kilometer helfen kaum, aber der frühe\nPlan ist an mindestens 10 Punkten mehr Tagen rechtzeitig fertig als der mittlere), **Reserve reicht**"),
    ("Stand: Version 0.6.0 (in Entwicklung).", "Stand: Version 0.6.1 (in Entwicklung)."),
])
edit("CHANGELOG.md", [
    ("# Changelog\n", """# Changelog

## 0.6.1 (unreleased) - the check says what it knows about the departure

- **The check *Does learning help?* no longer shows \"departure guessed right within one hour\"** (31 to 46 % in one house, which looked
  like a failure and is the wrong question, because real departures vary). It shows what the plan aims at: ready in time with the plan
  until the usual departure against the early one (52 against 85 % in that house), and per weekday for the early plan.
- **New verdict `departure_helps`** (*Learning helps for the departure*): the kilometres hardly help, but the early plan is ready in
  time on at least 10 points more days than the median plan. The card says it in two plain lines, kilometres and departure.
  Attributes `ready_median_pct`, `ready_early_pct`, `departure_gain_points`, per weekday `ready_early_pct` and `ready_median_pct`.
"""),
])
m = ROOT / "custom_components" / "plugwhen" / "manifest.json"
d = json.loads(m.read_text(encoding="utf-8"))
d["version"] = "0.6.1"
m.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("ok")
