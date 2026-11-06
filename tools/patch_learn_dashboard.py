"""One-off: learn mode card in the dashboard (kept for the record)."""
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen" / "dashboard.py"
s = p.read_text(encoding="utf-8")


def rep(a, b):
    global s
    assert s.count(a) == 1, a[:70]
    s = s.replace(a, b)


rep('"readiness": "sensor", "potential": "sensor", "week_plan": "sensor", "reserve_km": "number", "learn_km": "switch",',
    '"readiness": "sensor", "potential": "sensor", "week_plan": "sensor", "reserve_km": "number", "learn_km": "switch",\n    "mode": "select", "would_switch": "sensor",')

# texts
rep('        soc="Ladestand jetzt",',
    '        learn_h="Lernmodus", mode_name="Betriebsart", would="Würde schalten",\n'
    '        w_charge="Laden", w_pause="Pausieren", w_none="Keine Entscheidung", w_off="Aus",\n'
    '        r_in_window="im geplanten Fenster", r_waiting_for_window="wartet auf das nächste Fenster", r_plan_done="der Plan ist abgearbeitet",\n'
    '        r_cannot_reach_target="das Ziel ist knapp: so viel wie möglich sofort", r_unknown_soc="Ladestand unbekannt",\n'
    '        r_not_plugged="nicht angesteckt", r_not_needed="es muss nichts geladen werden", r_no_plan="kein Plan (keine Abfahrt)",\n'
    '        until_t="bis", lm_week="Vergleich mit der Wirklichkeit, letzte 7 Tage", lm_agree="Übereinstimmung", lm_days="Tage mit Daten",\n'
    '        lm_pause_ch="Stunden, in denen die Wallbox lud, obwohl Plugwhen pausiert hätte", lm_kwh_pause="kWh in diesen Zeiten",\n'
    '        lm_charge_idle="Stunden ohne Laden im geplanten Fenster", lm_kwh_charge="kWh in den geplanten Fenstern",\n'
    '        lm_journal="Letzte Entscheidungen", lm_none="Noch keine Entscheidungen.", lm_off="Der Lernmodus ist aus.",\n'
    '        lm_note="Im Lernmodus wird nichts geschaltet: Plugwhen schreibt nur auf, was es tun würde, und vergleicht das mit dem, was die Wallbox wirklich getan hat. Die Wallbox läuft weiter wie bisher.",\n'
    '        soc="Ladestand jetzt",')
rep('        soc="State of charge now",',
    '        learn_h="Learn mode", mode_name="Mode", would="Would switch",\n'
    '        w_charge="Charge", w_pause="Pause", w_none="No decision", w_off="Off",\n'
    '        r_in_window="in a planned window", r_waiting_for_window="waiting for the next window", r_plan_done="the plan is done",\n'
    '        r_cannot_reach_target="the target is tight: as much as possible at once", r_unknown_soc="state of charge unknown",\n'
    '        r_not_plugged="not plugged in", r_not_needed="nothing needs to be charged", r_no_plan="no plan (no departure)",\n'
    '        until_t="until", lm_week="Comparison with reality, last 7 days", lm_agree="Agreement", lm_days="days with data",\n'
    '        lm_pause_ch="hours the wallbox charged although Plugwhen would have paused", lm_kwh_pause="kWh in those times",\n'
    '        lm_charge_idle="hours without charging in a planned window", lm_kwh_charge="kWh in the planned windows",\n'
    '        lm_journal="Latest decisions", lm_none="No decisions yet.", lm_off="Learn mode is off.",\n'
    '        lm_note="Nothing is switched in learn mode: Plugwhen only writes down what it would do and compares it with what the wallbox really did. The wallbox keeps working as before.",\n'
    '        soc="State of charge now",')

# the card
rep('    plugs = (\n',
    '''    reasons = "{" + ", ".join(f"'{k}': '{t['r_' + k]}'" for k in (
        "in_window", "waiting_for_window", "plan_done", "cannot_reach_target", "unknown_soc", "not_plugged", "not_needed", "no_plan")) + "}"
    would_names = "{" + ", ".join(f"'{k}': '{t['w_' + k]}'" for k in ("charge", "pause", "none", "off")) + "}"
    learn = (
        "{% set a = " + _s(ids["would_switch"]) + ".attributes %}{% set st = states('" + ids["would_switch"] + "') %}"
        "{% set rs = " + reasons + " %}{% set wn = " + would_names + " %}"
        f"{{% if st == 'off' or not a.summary %}}{t['lm_off']}{{% else %}}"
        f"**{t['would']}:** {{{{ wn.get(st, st) }}}} · {{{{ rs.get(a.reason, a.reason) }}}}"
        f"{{% if a.until %}} · {t['until_t']} {{{{ (a.until | as_datetime | as_local).strftime('%H:%M') }}}}{{% endif %}}\\n\\n"
        "{% set s = a.summary %}"
        f"**{t['lm_week']}** ({{{{ s.days }}}} {t['lm_days']})\\n\\n"
        f"- {t['lm_agree']}: {{{{ (s.agree_pct ~ ' %') if s.agree_pct is not none else '–' }}}}\\n"
        f"- {t['lm_pause_ch']}: {{{{ s.pause_but_charging_h }}}} h · {t['lm_kwh_pause']}: {{{{ s.kwh_in_pause }}}}\\n"
        f"- {t['lm_charge_idle']}: {{{{ s.charge_but_idle_h }}}} h · {t['lm_kwh_charge']}: {{{{ s.kwh_in_charge }}}}\\n\\n"
        f"**{t['lm_journal']}**\\n"
        "{% for j in a.journal[:8] %}"
        "- {{ (j.t | as_datetime | as_local).strftime('%d.%m. %H:%M') }} · {{ wn.get(j.action, j.action) }} · {{ rs.get(j.reason, j.reason) }}\\n"
        f"{{% else %}}{t['lm_none']}{{% endfor %}}{{% endif %}}\\n\\n*{t['lm_note']}*"
    )
    plugs = (
''')
rep('''            {"type": "heading", "heading": head(t["plugs_h"]), "icon": "mdi:ev-plug-type2"},
            {"type": "markdown", "content": plugs},
        ]},''',
    '''            {"type": "heading", "heading": head(t["plugs_h"]), "icon": "mdi:ev-plug-type2"},
            {"type": "markdown", "content": plugs},
        ]},
        {"type": "grid", "cards": [
            {"type": "heading", "heading": head(t["learn_h"]), "icon": "mdi:school-outline"},
            {"type": "tile", "entity": ids["would_switch"], "name": t["would"]},
            {"type": "entities", "show_header_toggle": False, "entities": [{"entity": ids["mode"], "name": t["mode_name"]}]},
            {"type": "markdown", "content": learn},
        ]},''')
p.write_text(s, encoding="utf-8")
print("ok")
