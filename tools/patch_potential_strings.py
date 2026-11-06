"""One-off: texts and service definition of the potential calculator (kept for the record)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
g = ROOT / "tools" / "gen_strings.py"
s = g.read_text(encoding="utf-8")


def rep(a, b):
    global s
    assert s.count(a) == 1, a[:60]
    s = s.replace(a, b)


rep('''    r_ready="Ready", r_plug="Plug in", r_low="Too low", r_late="Too late", r_unreach="Not reachable", r_unknown="Unknown",''',
    '''    r_ready="Ready", r_plug="Plug in", r_low="Too low", r_late="Too late", r_unreach="Not reachable", r_unknown="Unknown",
    s_pot="Potential of spreading the charging", p_worth="Worth it", p_setting="Wallbox setting is enough", p_little="Little",
    p_few="Too little data", p_nodata="Data missing",
    o_grid="Grid import energy counter", o_plow="Demand charge per kW and year", o_phigh="Demand charge above the threshold", o_pthr="Threshold",
    od_grid="For the potential calculator: the meter's import counter (Wh or kWh, with long-term statistics). Taken from the quarter-hour peak guard if it is chosen.",
    od_plow="For the potential calculator, in your currency per kW and year (up to the threshold). Empty: taken from the peak guard, otherwise only kW are shown.",
    od_phigh="Price per kW and year above the threshold. Empty: the same price.",
    od_pthr="kW from which the higher price applies. 0 = one price.",
    sv_name="Calculate the potential", sv_desc="Replays the history of each vehicle with other ways of charging (as it was, spread over the parking time, the wallbox's own ready-by with a low current, the peak guard) and compares the monthly peak, the demand charge and how often the car would not have been ready. Read only, an estimate. Administrators only.",
    sv_days="Days", sv_days_d="How far back (14 to 365 days, default 90).",''')
rep('''    r_ready="Bereit", r_plug="Bitte anstecken", r_low="Zu niedrig", r_late="Zu spät", r_unreach="Nicht erreichbar", r_unknown="Unbekannt",''',
    '''    r_ready="Bereit", r_plug="Bitte anstecken", r_low="Zu niedrig", r_late="Zu spät", r_unreach="Nicht erreichbar", r_unknown="Unbekannt",
    s_pot="Potenzial durch verteiltes Laden", p_worth="Lohnt sich", p_setting="Wallbox-Einstellung reicht", p_little="Gering",
    p_few="Zu wenig Daten", p_nodata="Daten fehlen",
    o_grid="Energiezähler Netzbezug", o_plow="Leistungspreis je kW und Jahr", o_phigh="Leistungspreis über der Schwelle", o_pthr="Schwelle",
    od_grid="Für den Potenzialrechner: der Bezugszähler (Wh oder kWh, mit Langzeitstatistik). Wird vom Viertelstunden-Wächter übernommen, wenn er gewählt ist.",
    od_plow="Für den Potenzialrechner, in Ihrer Währung je kW und Jahr (bis zur Schwelle). Leer: vom Wächter übernommen, sonst werden nur kW gezeigt.",
    od_phigh="Preis je kW und Jahr über der Schwelle. Leer: derselbe Preis.",
    od_pthr="kW, ab denen der höhere Preis gilt. 0 = ein Preis.",
    sv_name="Potenzial berechnen", sv_desc="Spielt den Verlauf jedes Fahrzeugs mit anderen Ladeweisen nach (wie es war, über die Standzeit verteilt, die eigene Fertig-bis-Funktion der Wallbox mit kleinem Strom, der Spitzenwächter) und vergleicht Monatsspitze, Leistungspreis und wie oft das Auto nicht fertig gewesen wäre. Nur lesen, eine Schätzung. Nur für Administratoren.",
    sv_days="Tage", sv_days_d="Wie weit zurück (14 bis 365 Tage, Standard 90).",''')
rep('''            "data": {"waechter_entry": L["o_wachter"], "load_entity": L["o_load"], "availability_entity": L["o_avail"]},
            "data_description": {"waechter_entry": L["od_wachter"], "load_entity": L["od_load"], "availability_entity": L["od_avail"]},''',
    '''            "data": {"waechter_entry": L["o_wachter"], "load_entity": L["o_load"], "availability_entity": L["o_avail"],
                     "grid_energy_entity": L["o_grid"], "price_low": L["o_plow"], "price_high": L["o_phigh"], "price_threshold": L["o_pthr"]},
            "data_description": {"waechter_entry": L["od_wachter"], "load_entity": L["od_load"], "availability_entity": L["od_avail"],
                                 "grid_energy_entity": L["od_grid"], "price_low": L["od_plow"], "price_high": L["od_phigh"], "price_threshold": L["od_pthr"]},''')
rep('''                "readiness": {"name": L["s_ready"],''', '''                "potential": {"name": L["s_pot"], "state": {"worth_it": L["p_worth"], "setting_enough": L["p_setting"], "little": L["p_little"],
                                                           "too_little_data": L["p_few"], "no_data": L["p_nodata"]}},
                "readiness": {"name": L["s_ready"],''')
rep('''    return {
''', '''    services = {"calculate_potential": {"name": L["sv_name"], "description": L["sv_desc"],
                                         "fields": {"days": {"name": L["sv_days"], "description": L["sv_days_d"]}}}}
    return {
        "services": services,
''')
g.write_text(s, encoding="utf-8")

(ROOT / "custom_components" / "plugwhen" / "services.yaml").write_text('''calculate_potential:
  fields:
    days:
      required: false
      default: 90
      selector:
        number:
          min: 14
          max: 365
          mode: box
''', encoding="utf-8")
print("ok")
