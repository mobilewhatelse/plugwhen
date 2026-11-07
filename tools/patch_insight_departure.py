"""One-off: the check says what it knows about the departure: ready in time per weekday, and a verdict for it (kept for the record).

User feedback 07.11.2026: bars of "departure guessed right within one hour" (31 to 46 %) looked like a failure and are the wrong
question, because real departures vary; the plan aims at the early departure, so the useful number is "ready in time".
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def edit(rel, pairs):
    p = ROOT / rel
    s = p.read_text(encoding="utf-8")
    for a, b in pairs:
        assert s.count(a) == 1, f"{rel}: {a[:90]}"
        s = s.replace(a, b)
    p.write_text(s, encoding="utf-8")


edit("custom_components/plugwhen/insight.py", [
    ("""    dep = {wd: [0, 0] for wd in range(7)}          # weekday -> [right, checked]
    ready_median = ready_early = 0""",
     """    dep = {wd: [0, 0, 0, 0] for wd in range(7)}    # weekday -> [guessed right, checked, ready with the early plan, ready with the median plan]
    ready_median = ready_early = 0"""),
    ("""                ready_median += rec.first_move_hour >= p.departure_hour          # finished at the median: in time?
                early = p.departure_early if p.departure_early is not None else p.departure_hour
                ready_early += rec.first_move_hour >= early""",
     """                in_time_median = rec.first_move_hour >= p.departure_hour          # finished at the median: in time?
                early = p.departure_early if p.departure_early is not None else p.departure_hour
                in_time_early = rec.first_move_hour >= early
                ready_median += in_time_median
                ready_early += in_time_early
                dep[wd][2] += in_time_early
                dep[wd][3] += in_time_median"""),
    ("""        gain = learned - reserve
        verdict = "learning_helps" if gain >= HELPS_POINTS else "reserve_enough" if gain < SAME_POINTS else "little\"""",
     """        gain = learned - reserve
        dep_gain = (ready_early - ready_median) / dep_total if dep_total else 0.0
        if gain >= HELPS_POINTS:
            verdict = "learning_helps"                    # the kilometres help
        elif dep_gain >= DEPARTURE_HELPS_POINTS:
            verdict = "departure_helps"                   # the kilometres hardly do, the departure does
        else:
            verdict = "reserve_enough" if gain < SAME_POINTS else "little\""""),
    ("""HELPS_POINTS = 0.05
""", """HELPS_POINTS = 0.05
DEPARTURE_HELPS_POINTS = 0.10   # ready in time on at least 10 points more days with the early plan than with the median plan
"""),
    ("""        "ready_early_pct": round(100 * ready_early / dep_total) if dep_total else None,
        "departure_by_weekday": [
            {"weekday": wd, "days": n, "right_pct": round(100 * ok / n) if n else None} for wd, (ok, n) in sorted(dep.items())
        ],""",
     """        "ready_early_pct": round(100 * ready_early / dep_total) if dep_total else None,
        "departure_gain_points": round(100 * (ready_early - ready_median) / dep_total) if dep_total else None,
        "departure_by_weekday": [
            {"weekday": wd, "days": n, "right_pct": round(100 * ok / n) if n else None,
             "ready_early_pct": round(100 * early / n) if n else None, "ready_median_pct": round(100 * med / n) if n else None}
            for wd, (ok, n, early, med) in sorted(dep.items())
        ],"""),
    ("""alone), `reserve_enough` (less than 2 points: the reserve alone does it), `little` in between, `too_little_data` (fewer than
21 days could be checked).""", """alone), `departure_helps` (the kilometres hardly help, but a plan until the early departure is ready in time on at least 10 points
more days than one until the usual departure), `reserve_enough` (less than 2 points: the reserve alone does it), `little` in between,
`too_little_data` (fewer than 21 days could be checked)."""),
])

edit("custom_components/plugwhen/charts.py", [
    ('        departure="Abfahrtszeit richtig geraten (± 1 Stunde)",', '        departure="Rechtzeitig fertig je Wochentag (Plan bis zur frühen Abfahrt)",'),
    ('        departure="Departure hour guessed right (± 1 hour)",', '        departure="Ready in time per weekday (plan until the early departure)",'),
    ("        pct = day.get(\"right_pct\")\n", "        pct = day.get(\"ready_early_pct\")\n"),
])

edit("custom_components/plugwhen/const.py", [
    ('LEARNING_STATES = ["learning_helps", "reserve_enough", "little", "too_little_data"]',
     'LEARNING_STATES = ["learning_helps", "departure_helps", "reserve_enough", "little", "too_little_data"]'),
])

edit("custom_components/plugwhen/sensor.py", [
    ('''        keys = ("days", "reserve_km", "coverage_reserve_pct", "coverage_learned_pct", "gain_points", "departure_right_pct",
                "departure_days", "departure_by_weekday")''',
     '''        keys = ("days", "reserve_km", "coverage_reserve_pct", "coverage_learned_pct", "gain_points", "departure_right_pct",
                "departure_days", "departure_by_weekday", "ready_median_pct", "ready_early_pct", "departure_gain_points")'''),
])

edit("tools/gen_strings.py", [
    ('lc_helps="Learning helps",', 'lc_helps="Learning helps", lc_dep="Learning helps for the departure",'),
    ('lc_helps="Lernen hilft",', 'lc_helps="Lernen hilft", lc_dep="Lernen hilft bei der Abfahrt",'),
    ('"learning_check": {"name": L["s_lc"], "state": {"learning_helps": L["lc_helps"],',
     '"learning_check": {"name": L["s_lc"], "state": {"learning_helps": L["lc_helps"], "departure_helps": L["lc_dep"],'),
])

# dashboard: two plain lines, kilometres and departure
edit("custom_components/plugwhen/dashboard.py", [
    ('        lc_h="Bringt das Lernen etwas?", lc_tile="Lernen: lohnt es sich?", lc_yes="Ja.", lc_no="Kaum.", lc_some="Wenig.",',
     '        lc_km="Kilometer", lc_depl="Abfahrt", lc_km_helps="Mit dem Gelernten wären", lc_km_helps_b="Prozentpunkte mehr Tage gedeckt gewesen",\n'
     '        lc_km_same="Die feste Reserve allein deckt fast genauso viele Tage", lc_km_same_b="das Lernen der Kilometer bringt hier wenig",\n'
     '        lc_dep_good="Mit dem Plan bis zur frühen Abfahrt wäre das Auto an", lc_dep_good_b="Prozent der Tage rechtzeitig fertig gewesen, bis zur üblichen nur an",\n'
     '        lc_dep_none="Zur Abfahrt gibt es noch keine Aussage.",\n'
     '        lc_h="Bringt das Lernen etwas?", lc_tile="Lernen: lohnt es sich?", lc_yes="Ja.", lc_no="Kaum.", lc_some="Wenig.",'),
    ('        lc_h="Does learning help?", lc_tile="Does learning help?", lc_yes="Yes.", lc_no="Hardly.", lc_some="A little.",',
     '        lc_km="Kilometres", lc_depl="Departure", lc_km_helps="With what was learned", lc_km_helps_b="percentage points more days would have been covered",\n'
     '        lc_km_same="The fixed reserve alone covers almost as many days", lc_km_same_b="learning the kilometres brings little here",\n'
     '        lc_dep_good="With the plan until the early departure the car would have been ready in time on", lc_dep_good_b="percent of the days, with the one until the usual departure only on",\n'
     '        lc_dep_none="There is no statement about the departure yet.",\n'
     '        lc_h="Does learning help?", lc_tile="Does learning help?", lc_yes="Yes.", lc_no="Hardly.", lc_some="A little.",'),
    ('''    lc_line = (
        "{% set a = " + _s(lc_id) + ".attributes %}{% set st = states('" + lc_id + "') %}"
        f"{{% if st == 'too_little_data' %}}{t['lc_few_a']} {{{{ a.days }}}} {t['lc_few_b']}"
        f"{{% elif st == 'learning_helps' %}}**{t['lc_yes']}** {t['lc_helps_a']} {{{{ a.gain_points }}}} {t['lc_helps_b']}."
        f"{{% elif st == 'reserve_enough' %}}**{t['lc_no']}** {t['lc_enough']}."
        f"{{% else %}}**{t['lc_some']}** {t['lc_helps_a']} {{{{ a.gain_points }}}} {t['lc_helps_b']}.{{% endif %}}"
    )''',
     '''    lc_line = (
        "{% set a = " + _s(lc_id) + ".attributes %}{% set st = states('" + lc_id + "') %}"
        f"{{% if st == 'too_little_data' %}}{t['lc_few_a']} {{{{ a.days }}}} {t['lc_few_b']}{{% else %}}"
        f"**{t['lc_km']}:** {{% if st == 'learning_helps' %}}{t['lc_km_helps']} {{{{ a.gain_points }}}} {t['lc_km_helps_b']}."
        f"{{% else %}}{t['lc_km_same']} ({{{{ a.coverage_reserve_pct }}}} → {{{{ a.coverage_learned_pct }}}} %): {t['lc_km_same_b']}.{{% endif %}}\\n\\n"
        f"**{t['lc_depl']}:** {{% if a.ready_early_pct is not none %}}{t['lc_dep_good']} {{{{ a.ready_early_pct }}}} {t['lc_dep_good_b']} {{{{ a.ready_median_pct }}}} %."
        f"{{% else %}}{t['lc_dep_none']}{{% endif %}}{{% endif %}}"
    )'''),
])
print("ok")
