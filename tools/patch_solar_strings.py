"""One-off: texts of the solar options (kept for the record)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
g = ROOT / "tools" / "gen_strings.py"
s = g.read_text(encoding="utf-8")


def rep(a, b):
    global s
    assert s.count(a) == 1, a[:60]
    s = s.replace(a, b)


rep('o_wachter="Quarter-hour peak guard", o_load="Other load forecast", o_avail="Availability of power",',
    'o_wachter="Quarter-hour peak guard", o_load="Other load forecast", o_avail="Availability of power",\n'
    '    o_solar="Use the solar forecast of the Energy dashboard", o_sdeduct="Deduction from the solar forecast",\n'
    '    od_solar="Charge from the expected solar surplus first while the car is at home, then spread the rest over the parking time. '
    'Works with any solar forecast set up in the Energy dashboard; without one the rest is simply spread.",\n'
    '    od_sdeduct="kW taken off the solar forecast first, for what the house and a home battery use. The rest counts as available for the car.",')
rep('o_wachter="Viertelstunden-Wächter", o_load="Andere Last-Prognose", o_avail="Verfügbarkeit von Strom",',
    'o_wachter="Viertelstunden-Wächter", o_load="Andere Last-Prognose", o_avail="Verfügbarkeit von Strom",\n'
    '    o_solar="Solarprognose des Energie-Dashboards nutzen", o_sdeduct="Abzug von der Solarprognose",\n'
    '    od_solar="Zuerst mit dem erwarteten Sonnenüberschuss laden, solange das Auto zu Hause steht, den Rest über die Standzeit verteilen. '
    'Funktioniert mit jeder Solarprognose, die im Energie-Dashboard eingerichtet ist; ohne wird der Rest einfach verteilt.",\n'
    '    od_sdeduct="kW, die zuerst von der Solarprognose abgehen, für Haus und Hausakku. Der Rest gilt als verfügbar fürs Auto.",')
rep('"availability_entity": L["o_avail"],', '"availability_entity": L["o_avail"], "use_solar_forecast": L["o_solar"], "solar_deduct_kw": L["o_sdeduct"],')
rep('"availability_entity": L["od_avail"],', '"availability_entity": L["od_avail"], "use_solar_forecast": L["od_solar"], "solar_deduct_kw": L["od_sdeduct"],')
g.write_text(s, encoding="utf-8")
print("ok")
