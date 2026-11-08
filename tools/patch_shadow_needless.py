"""One-off: learn mode also records the energy delivered although nothing was needed (kept for the record).

Finding 08.11.2026: while the plan says "not needed" every decision is "no decision" and was not compared at all, so the energy the wallbox
delivers anyway (for example charging with the sun) was invisible. The automatic mode needs exactly that number.
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


edit("custom_components/plugwhen/shadow.py", [
    ('SECONDS_KEYS = ("charge_charging", "charge_idle", "pause_charging", "pause_idle")\nENERGY_KEYS = ("kwh_charge", "kwh_pause")',
     'SECONDS_KEYS = ("charge_charging", "charge_idle", "pause_charging", "pause_idle", "needless_charging")\nENERGY_KEYS = ("kwh_charge", "kwh_pause", "kwh_needless")'),
    ("        self._last: tuple[datetime, str | None, bool | None, float | None] | None = None",
     "        self._last: tuple[datetime, str | None, bool | None, float | None, str | None] | None = None"),
    ("""        if self._last is not None:
            t0, a0, c0, e0 = self._last
            dt = now - t0
            if timedelta(0) < dt <= MAX_GAP and a0 in ("charge", "pause"):
                day = self.days.setdefault(t0.date().isoformat(), _empty_day())
                if c0 is not None:
                    day[f"{a0}_{'charging' if c0 else 'idle'}"] += dt.total_seconds()
                    changed = True
                if energy_kwh is not None and e0 is not None and energy_kwh >= e0:
                    day[f"kwh_{a0}"] += energy_kwh - e0
                    changed = True
        self._last = (now, decision.action if decision else None, charging, energy_kwh)""",
     """        if self._last is not None:
            t0, a0, c0, e0, r0 = self._last
            dt = now - t0
            if timedelta(0) < dt <= MAX_GAP and (a0 in ("charge", "pause") or (a0 == "none" and r0 == "not_needed")):
                day = self.days.setdefault(t0.date().isoformat(), _empty_day())
                if a0 == "none":                        # nothing was needed: what the wallbox delivered anyway (for example with the sun)
                    if c0:
                        day["needless_charging"] += dt.total_seconds()
                        changed = True
                    if energy_kwh is not None and e0 is not None and energy_kwh >= e0:
                        day["kwh_needless"] += energy_kwh - e0
                        changed = True
                else:
                    if c0 is not None:
                        day[f"{a0}_{'charging' if c0 else 'idle'}"] += dt.total_seconds()
                        changed = True
                    if energy_kwh is not None and e0 is not None and energy_kwh >= e0:
                        day[f"kwh_{a0}"] += energy_kwh - e0
                        changed = True
        self._last = (now, decision.action if decision else None, charging, energy_kwh, decision.reason if decision else None)"""),
    ("""        decided = sum(tot[k] for k in SECONDS_KEYS)""", """        decided = sum(tot[k] for k in ("charge_charging", "charge_idle", "pause_charging", "pause_idle"))"""),
    ("""            "kwh_in_charge": round(tot["kwh_charge"], 1),
        }""", """            "kwh_in_charge": round(tot["kwh_charge"], 1),
            "needless_h": round(tot["needless_charging"] / 3600, 1),
            "kwh_needless": round(tot["kwh_needless"], 1),
        }"""),
])

edit("custom_components/plugwhen/dashboard.py", [
    ('        lm_note="Im Lernmodus wird nichts geschaltet:',
     '        lm_needless="Ohne Bedarf geladen (zum Beispiel mit Sonne)", lm_needless_in="kWh in den letzten 7 Tagen",\n'
     '        lm_note="Im Lernmodus wird nichts geschaltet:'),
    ('        lm_note="Nothing is switched in learn mode:',
     '        lm_needless="Charged although nothing was needed (for example with the sun)", lm_needless_in="kWh in the last 7 days",\n'
     '        lm_note="Nothing is switched in learn mode:'),
    ('''        f"{{% if a.until %}} · {t['until_t']} {{{{ (a.until | as_datetime | as_local).strftime('%H:%M') }}}}{{% endif %}}{{% endif %}}"
    )''', '''        f"{{% if a.until %}} · {t['until_t']} {{{{ (a.until | as_datetime | as_local).strftime('%H:%M') }}}}{{% endif %}}{{% endif %}}"
        f"{{% if a.summary and a.summary.kwh_needless %}}\\n\\n{t['lm_needless']}: **{{{{ a.summary.kwh_needless }}}}** {t['lm_needless_in']}{{% endif %}}"
    )'''),
])
print("ok")
