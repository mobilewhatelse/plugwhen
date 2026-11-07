"""One-off: step A, the rest: constants, texts, sensor attributes, dashboard line, docs, version (kept for the record)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "custom_components" / "plugwhen"


def edit(path, pairs):
    p = path if isinstance(path, Path) else ROOT / path
    s = p.read_text(encoding="utf-8")
    for a, b in pairs:
        assert s.count(a) == 1, f"{p.name}: {a[:80]}"
        s = s.replace(a, b)
    p.write_text(s, encoding="utf-8")


edit(PKG / "const.py", [
    ('V_CHARGE_MIN = "charge_kw_min"            # lowest charging power (1 phase, 6 A = 1.4 kW)\n',
     'V_CHARGE_MIN = "charge_kw_min"            # lowest charging power (1 phase, 6 A = 1.4 kW)\n'
     'V_CHARGE_PREF = "charge_kw_pref"          # preferred lowest power: spread no flatter than this (the car\'s charger wastes more below)\n'
     'DEFAULT_CHARGE_PREF = 4.0\n'
     'CALIBRATE_INTERVAL = timedelta(hours=24)  # learn the house-specific numbers again (quarter add, base load, solar accuracy)\n'),
])

edit(ROOT / "tools" / "gen_strings.py", [
    ('f_min="Wallbox power (minimum)",', 'f_min="Wallbox power (minimum)", f_pref="Preferred lowest charging power",'),
    ('    d_min="Lowest charging power of the wallbox (1 phase, 6 A is about 1.4 kW).",',
     '    d_min="Lowest charging power of the wallbox (1 phase, 6 A is about 1.4 kW).",\n'
     '    d_pref="The plan spreads the charging no flatter than this (the car\'s charger wastes more energy at very low power); only if the energy does not fit that way it goes down to the minimum. Default 4 kW.",'),
    ('f_min="Wallbox-Leistung (mindestens)",', 'f_min="Wallbox-Leistung (mindestens)", f_pref="Bevorzugte kleinste Ladeleistung",'),
    ('    d_min="Kleinste Ladeleistung der Wallbox (1 Phase, 6 A sind etwa 1,4 kW).",',
     '    d_min="Kleinste Ladeleistung der Wallbox (1 Phase, 6 A sind etwa 1,4 kW).",\n'
     '    d_pref="Der Plan verteilt das Laden nicht flacher als diesen Wert (der Lader im Auto hat bei sehr kleiner Leistung höhere Verluste); nur wenn die Energie so nicht hineinpasst, geht er bis zum Minimum hinunter. Standard 4 kW.",'),
    ('od_sdeduct="kW taken off the solar forecast first, for what the house and a home battery use. The rest counts as available for the car.",',
     'od_sdeduct="kW taken off the solar forecast first, for what the house and a home battery use. Empty: learned from the night-time base load of the grid import counter (default 0.5 kW until then).",'),
    ('od_sdeduct="kW, die zuerst von der Solarprognose abgehen, für Haus und Hausakku. Der Rest gilt als verfügbar fürs Auto.",',
     'od_sdeduct="kW, die zuerst von der Solarprognose abgehen, für Haus und Hausakku. Leer: aus der nächtlichen Grundlast des Bezugszählers gelernt (bis dahin 0,5 kW).",'),
    ('"charge_kw_max": L["f_max"], "charge_kw_min": L["f_min"],', '"charge_kw_max": L["f_max"], "charge_kw_min": L["f_min"], "charge_kw_pref": L["f_pref"],'),
    ('"charge_kw_max": L["d_max"], "charge_kw_min": L["d_min"],', '"charge_kw_max": L["d_max"], "charge_kw_min": L["d_min"], "charge_kw_pref": L["d_pref"],'),
])

edit(PKG / "sensor.py", [
    ('            "learn_km": v.learn_km,\n',
     '            "learn_km": v.learn_km,\n'
     '            "efficiency": v.efficiency or 0.9, "efficiency_learned": v.efficiency is not None,\n'),
    ('            "availability_source": v.availability_source,\n',
     '            "availability_source": v.availability_source,\n'
     '            "solar_factor": self.plug.solar_factor(), "solar_deduct_kw": self.plug.solar_deduct_kw(),\n'
     '            "solar_deduct_source": self.plug.solar_deduct_source(), "spread_floor_kw": p.get("spread_floor_kw"),\n'
     '            "pref_kw": float(v.cfg.get("charge_kw_pref") or 4.0),\n'),
])

edit(PKG / "dashboard.py", [
    ('        learn_h="Lernmodus", mode_name="Betriebsart", would="Würde schalten",',
     '        cal_sun="Sonne", cal_factor="Prognose ×", cal_learned="bei Ihnen gelernt", cal_unchecked="Prognose noch ungeprüft",\n'
     '        cal_deduct="Abzug fürs Haus", cal_src_learned="gelernt", cal_src_setting="eingestellt", cal_src_default="Vorgabe",\n'
     '        cal_loss="Ladeverluste", cal_floor="verteilt ab",\n'
     '        learn_h="Lernmodus", mode_name="Betriebsart", would="Würde schalten",'),
    ('        learn_h="Learn mode", mode_name="Mode", would="Would switch",',
     '        cal_sun="Sun", cal_factor="forecast ×", cal_learned="learned here", cal_unchecked="forecast not checked yet",\n'
     '        cal_deduct="deduction for the house", cal_src_learned="learned", cal_src_setting="setting", cal_src_default="default",\n'
     '        cal_loss="charging losses", cal_floor="spread from",\n'
     '        learn_h="Learn mode", mode_name="Mode", would="Would switch",'),
    ('    head = (lambda h: f"{name} · {h}") if multi else (lambda h: h)\n',
     '    calib_line = (\n'
     '        "{% set a = " + _s(ids["charge_plan"]) + ".attributes %}{% set n = " + need + " %}"\n'
     '        "{% if a.solar_deduct_kw is not none %}"\n'
     '        f"{t[\'cal_sun\']}: {{% if a.solar_factor %}}{t[\'cal_factor\']} {{{{ a.solar_factor }}}} ({t[\'cal_learned\']}){{% else %}}{t[\'cal_unchecked\']}{{% endif %}} · "\n'
     '        f"{t[\'cal_deduct\']} {{{{ a.solar_deduct_kw }}}} kW ({{{{ {{\'learned\': \'{t[\'cal_src_learned\']}\', \'setting\': \'{t[\'cal_src_setting\']}\', \'default\': \'{t[\'cal_src_default\']}\'}}.get(a.solar_deduct_source, \'\') }}}}) · "\n'
     '        f"{t[\'cal_loss\']} {{{{ ((1 - (n.efficiency or 0.9)) * 100) | round(0) | int }}}} % ({{{{ \'{t[\'cal_src_learned\']}\' if n.efficiency_learned else \'{t[\'cal_src_default\']}\' }}}})"\n'
     '        f"{{% if a.spread_floor_kw %}} · {t[\'cal_floor\']} {{{{ a.spread_floor_kw }}}} kW{{% endif %}}{{% endif %}}"\n'
     '    )\n'
     '    head = (lambda h: f"{name} · {h}") if multi else (lambda h: h)\n'),
    ('            {"type": "markdown", "content": _chart(ids["charge_plan"])},\n',
     '            {"type": "markdown", "content": _chart(ids["charge_plan"])},\n'
     '            {"type": "markdown", "content": calib_line},\n'),
])

# installation test: the new attributes are there
edit(ROOT / "tests" / "install" / "itest.py", [
    ('    log(state(lid)["state"] == "on", "kilometre learning is on by default")\n',
     '    log(state(lid)["state"] == "on", "kilometre learning is on by default")\n'
     '    ca, pa0 = state(cid)["attributes"], state(pid)["attributes"]\n'
     '    log("efficiency" in ca and ca.get("efficiency_learned") is False and pa0.get("solar_deduct_source") == "default" and pa0.get("pref_kw") == 4.0,\n'
     '        "house numbers start as defaults (efficiency, solar deduction, preferred power) and say so",\n'
     '        f"eff {ca.get(\'efficiency\')} learned {ca.get(\'efficiency_learned\')} deduct {pa0.get(\'solar_deduct_source\')} pref {pa0.get(\'pref_kw\')}")\n'),
])

# docs, changelog, version
EN = """## Honest numbers: what is learned instead of set

Every number that depends on the house or the car has a default that works everywhere, and Plugwhen replaces it with a learned
value as soon as there is enough data (daily, in the background; the dashboard says which one is in use):

| Number | Default | Learned from |
|---|---|---|
| departure the plan aims at | learned median hour | the **early** departure (20th percentile of the weekday's first trips): a car ready at the median is late on about half of the early days |
| preferred lowest charging power | 4 kW (setting per car) | the plan spreads no flatter than this; the car's charger wastes more below a few kW; down to the minimum only if the energy does not fit |
| charging losses | 10 % | days with home charging only: rise of the state of charge x capacity against the wallbox energy (clamped 2 to 25 %) |
| deduction from the solar forecast | 0.5 kW | the night-time base load (median of the hours 1 to 5 of the grid import counter); a setting overrides it |
| quarter-hour add of the potential calculator | 0.7 kW | the 5-minute statistics of the grid import of the chosen peak guard: highest quarter hour above its hour's mean, 80th percentile |
| accuracy of the solar forecast | 1.0 | predicted against measured solar energy per day (the Energy dashboard's production statistic), median ratio of the last 30 days, 0.5 to 1.5; the plan uses the scaled forecast |

"""
DE = """## Ehrliche Zahlen: was gelernt statt gesetzt wird

Jede Zahl, die vom Haus oder vom Auto abhängt, hat eine Vorgabe, die überall funktioniert, und Plugwhen ersetzt sie durch einen gelernten Wert,
sobald genug Daten da sind (täglich im Hintergrund; das Dashboard sagt, welcher gerade gilt):

| Zahl | Vorgabe | Gelernt aus |
|---|---|---|
| Abfahrt, auf die der Plan zielt | gelernte mittlere Stunde | die **frühe** Abfahrt (20. Perzentil der ersten Fahrten des Wochentags): ein Auto, das zur mittleren Abfahrt fertig ist, ist an etwa der Hälfte der frühen Tage zu spät |
| bevorzugte kleinste Ladeleistung | 4 kW (Einstellung je Auto) | der Plan verteilt nicht flacher; der Lader im Auto hat unter wenigen kW höhere Verluste; bis zum Minimum nur, wenn die Energie sonst nicht passt |
| Ladeverluste | 10 % | Tage mit Laden nur zu Hause: Anstieg des Ladestands × Akkugröße gegen die Wallbox-Energie (begrenzt auf 2 bis 25 %) |
| Abzug von der Solarprognose | 0,5 kW | die nächtliche Grundlast (Median der Stunden 1 bis 5 des Bezugszählers); eine Einstellung geht vor |
| Viertelstunden-Zuschlag des Potenzialrechners | 0,7 kW | die 5-Minuten-Statistik des Netzbezugs des gewählten Wächters: höchste Viertelstunde über dem Stundenmittel, 80. Perzentil |
| Treffsicherheit der Solarprognose | 1,0 | erwartete gegen gemessene Solarenergie je Tag (Erzeugungsstatistik des Energie-Dashboards), Median der letzten 30 Tage, 0,5 bis 1,5; der Plan rechnet mit der skalierten Prognose |

"""
edit("README.md", [
    ("## Does the learning help? (a check on your own history)\n", EN + "## Does the learning help? (a check on your own history)\n"),
    ("**Status: version 0.5.1 in development**", "**Status: version 0.6.0 in development**"),
    ("- **Was the departure guessed right?** The learned usual hour of the first trip against the real one, within one hour (the history knows\n  the hour, not the minute), as one bar per weekday.\n",
     "- **Was the departure guessed right?** The learned usual hour of the first trip against the real one, within one hour (the history knows\n  the hour, not the minute), as one bar per weekday.\n- **Would the car have been ready in time?** A plan that finishes at the usual (median) departure against one that finishes at the early\n  departure, as two bars.\n"),
])
edit("docs/ANLEITUNG.md", [
    ("## Bringt das Lernen etwas? (eine Prüfung am eigenen Verlauf)\n", DE + "## Bringt das Lernen etwas? (eine Prüfung am eigenen Verlauf)\n"),
    ("Stand: Version 0.5.1 (in Entwicklung).", "Stand: Version 0.6.0 (in Entwicklung)."),
    ("- **Wurde die Abfahrt richtig geraten?** Die gelernte übliche Stunde der ersten Fahrt gegen die echte, auf eine Stunde genau (der Verlauf kennt\n  die Stunde, nicht die Minute), als ein Balken je Wochentag.\n",
     "- **Wurde die Abfahrt richtig geraten?** Die gelernte übliche Stunde der ersten Fahrt gegen die echte, auf eine Stunde genau (der Verlauf kennt\n  die Stunde, nicht die Minute), als ein Balken je Wochentag.\n- **Wäre das Auto rechtzeitig fertig gewesen?** Ein Plan bis zur üblichen (mittleren) Abfahrt gegen einen bis zur frühen Abfahrt, als zwei Balken.\n"),
])
edit("CHANGELOG.md", [
    ("# Changelog\n", """# Changelog

## 0.6.0 (unreleased) - honest numbers

- **The plan aims at the early departure** (20th percentile of the weekday's first trips) instead of the median: a car that is ready at
  the median departure is late on about half of the early days. The check *Does learning help?* shows both as bars (ready in time:
  plan until the usual departure against plan until the early departure).
- **Preferred lowest charging power** (setting per car, default 4 kW): the rest is spread no flatter than this, because the car's charger
  wastes more energy at very low power; down to the wallbox minimum only if the energy does not fit. Attribute `spread_floor_kw`.
- **House-specific numbers learned instead of set** (daily, defaults until enough data, overridable): charging losses from days with
  home charging only; the deduction from the solar forecast from the night-time base load (the setting is optional now); the
  quarter-hour add of the potential calculator from the 5-minute statistics of the peak guard's grid import (was a fixed 0.7 kW measured
  in one house). Attributes `efficiency`, `efficiency_learned`, `solar_deduct_kw`, `solar_deduct_source`, `quarter_add_kw`.
- **Accuracy of the solar forecast**: predicted against measured solar energy per day (production statistic of the Energy dashboard);
  the median ratio of the last 30 days scales the forecast before the plan uses it (0.5 to 1.5). Attribute `solar_factor`.
- Dashboard: one line under the plan chart says which numbers are learned, set or default.
"""),
])
m = PKG / "manifest.json"
d = json.loads(m.read_text(encoding="utf-8"))
d["version"] = "0.6.0"
m.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("ok")
