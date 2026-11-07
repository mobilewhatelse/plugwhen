"""One-off: the two charts and the verdict "does learning help" in the dashboard (kept for the record)."""
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen" / "dashboard.py"
s = p.read_text(encoding="utf-8")


def rep(a, b):
    global s
    assert s.count(a) == 1, a[:80]
    s = s.replace(a, b)


rep('    "mode": "select", "would_switch": "sensor",', '    "mode": "select", "would_switch": "sensor", "learning_check": "sensor",')

rep('        learn_h="Lernmodus", mode_name="Betriebsart", would="Würde schalten",',
    '        lc_h="Bringt das Lernen etwas?", lc_tile="Lernen: lohnt es sich?", lc_yes="Ja.", lc_no="Kaum.", lc_some="Wenig.",\n'
    '        lc_helps_a="Mit dem Gelernten wären", lc_helps_b="Prozentpunkte mehr Tage gedeckt gewesen",\n'
    '        lc_enough="Die feste Reserve allein hätte fast genauso viele Tage gedeckt", lc_enough_b="Das Lernen schadet nicht, bringt bei der Reichweite hier aber wenig.",\n'
    '        lc_dep_a="Abfahrtszeit: an", lc_dep_b="Prozent der", lc_dep_c="Fahrtage auf ± 1 Stunde richtig geraten.",\n'
    '        lc_few_a="Noch zu wenig Daten: geprüft wurden", lc_few_b="Tage, nötig sind 21.",\n'
    '        lc_note="Geprüft wird Tag für Tag an Ihrem eigenen Verlauf, wobei an jedem Tag nur die Tage davor bekannt sind.",\n'
    '        shadow_chart_h="Plan gegen Wirklichkeit",\n'
    '        learn_h="Lernmodus", mode_name="Betriebsart", would="Würde schalten",')
rep('        learn_h="Learn mode", mode_name="Mode", would="Would switch",',
    '        lc_h="Does learning help?", lc_tile="Does learning help?", lc_yes="Yes.", lc_no="Hardly.", lc_some="A little.",\n'
    '        lc_helps_a="With what was learned", lc_helps_b="percentage points more days would have been covered",\n'
    '        lc_enough="The fixed reserve alone would have covered almost as many days", lc_enough_b="Learning does no harm, but brings little for the range here.",\n'
    '        lc_dep_a="Departure hour: on", lc_dep_b="percent of the", lc_dep_c="days with a trip it was guessed right within 1 hour.",\n'
    '        lc_few_a="Too little data yet: checked", lc_few_b="days, 21 are needed.",\n'
    '        lc_note="It is checked day by day against your own history, and on each day only the days before it are known.",\n'
    '        shadow_chart_h="Plan against reality",\n'
    '        learn_h="Learn mode", mode_name="Mode", would="Would switch",')

rep('    plugs = (\n',
    '''    lc_id = ids["learning_check"]
    lc = (
        "{% set a = " + _s(lc_id) + ".attributes %}{% set st = states('" + lc_id + "') %}"
        f"{{% if st == 'too_little_data' %}}{t['lc_few_a']} {{{{ a.days }}}} {t['lc_few_b']}"
        f"{{% elif st == 'learning_helps' %}}**{t['lc_yes']}** {t['lc_helps_a']} {{{{ a.gain_points }}}} {t['lc_helps_b']} "
        "({{ a.coverage_reserve_pct }} % → {{ a.coverage_learned_pct }} %)."
        f"{{% elif st == 'reserve_enough' %}}**{t['lc_no']}** {t['lc_enough']} ({{{{ a.coverage_reserve_pct }}}} %). {t['lc_enough_b']}"
        f"{{% else %}}**{t['lc_some']}** {t['lc_helps_a']} {{{{ a.gain_points }}}} {t['lc_helps_b']} "
        "({{ a.coverage_reserve_pct }} % → {{ a.coverage_learned_pct }} %).{% endif %}"
        f"{{% if a.departure_days %}}\\n\\n{t['lc_dep_a']} {{{{ a.departure_right_pct }}}} {t['lc_dep_b']} {{{{ a.departure_days }}}} {t['lc_dep_c']}{{% endif %}}"
        f"\\n\\n*{t['lc_note']}*"
    )
    lc_chart = "{% set c = state_attr('" + lc_id + "', 'chart') %}{% if c %}![](data:image/svg+xml;utf8,{{ c | urlencode }}){% endif %}"
    shadow_chart = ("{% set c = state_attr('" + ids["would_switch"] + "', 'chart') %}"
                    "{% if c %}![](data:image/svg+xml;utf8,{{ c | urlencode }}){% endif %}")
    plugs = (
''')

rep('''            {"type": "markdown", "content": learn},
        ]},''',
    '''            {"type": "markdown", "content": shadow_chart},
            {"type": "markdown", "content": learn},
        ]},''')

rep('''            {"type": "heading", "heading": head(t["week_h"]), "icon": "mdi:calendar-week"},
            {"type": "markdown", "content": week},''',
    '''            {"type": "heading", "heading": head(t["lc_h"]), "icon": "mdi:school-outline"},
            {"type": "tile", "entity": ids["learning_check"], "name": t["lc_tile"]},
            {"type": "markdown", "content": lc},
            {"type": "markdown", "content": lc_chart},
            {"type": "heading", "heading": head(t["week_h"]), "icon": "mdi:calendar-week"},
            {"type": "markdown", "content": week},''')
p.write_text(s, encoding="utf-8")
print("ok")
