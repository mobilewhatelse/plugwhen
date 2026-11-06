"""The Plugwhen dashboard (pure Python, no Home Assistant imports).

`build_views(vehicles, language)` returns the Lovelace views for a list of vehicles, each `{"name", "ids"}` with the entity
ids of that vehicle under the keys of `ENTITY_KEYS`. Only standard cards (tile, markdown, entities, heading) in a sections
view, so nothing has to be installed. German for `de`, English otherwise.
"""

from __future__ import annotations

from typing import Any

# key of the entity (the end of its unique id) -> domain
ENTITY_KEYS = {
    "departure": "sensor", "need_charge": "sensor", "need_range": "sensor", "target_soc": "sensor", "charge_plan": "sensor",
    "readiness": "sensor", "potential": "sensor", "week_plan": "sensor", "reserve_km": "number", "learn_km": "switch",
    "notice_enabled": "switch",
}

TEXT = {
    "de": dict(
        next="Nächste Abfahrt", departure="Erwartete Abfahrt", charge="Noch zu laden", range="Nötige Reichweite",
        target="Ziel-Ladestand", ready="Bereit zur Abfahrt", plan_h="Ladeplan", plan="Ladeplan", pot_h="Potenzial",
        pot="Potenzial durch verteiltes Laden", plugs_h="Steckzeiten", settings="Einstellungen", week_h="Gelernter Wochenplan",
        reserve="Reserve (km), mit der das Auto mindestens losfährt", learn="Kilometer je Wochentag lernen",
        notice="Warnen, wenn das Auto nicht bereit sein wird",
        settings_note="**Reserve** ist die Untergrenze der Reichweite. Ist der Schalter an, hebt der gelernte hohe Wert eines Wochentags sie bei Bedarf an. Aus: nur die Reserve zählt.",
        soc="Ladestand jetzt", plugged="angesteckt", yes="ja", no="nein", unknown="unbekannt", goal="Ziel bei Abfahrt",
        basis="Grundlage", b_learned="gelernter hoher Wert des Wochentags (länger als die Reserve)",
        b_away="nur die Reserve (an diesem Wochentag wird meist unterwegs geladen)", b_plus="Reserve plus gelernter Wert",
        b_reserve="die Reserve", unreachable="Achtung: das Ziel ist mit dem Akku nicht erreichbar.",
        planned="Geplant", in_windows="Fenster", done_at="fertig um", up_to="bis", of_avail="davon", avail_kwh="kWh verfügbarer Strom",
        not_needed="Es muss nichts geladen werden.", infeasible="Das Ziel ist bis zur Abfahrt nicht erreichbar: es fehlen",
        no_dep="Keine Abfahrt bekannt.", dep_from="Abfahrt aus", entity="Entität", learning="Lernen", load="Last-Prognose",
        first_from="Strom zuerst aus", s_solar="Sonne (Solarprognose)", s_entity="Verfügbarkeits-Sensor",
        s_both="Sonne und Verfügbarkeits-Sensor", s_none="nichts (der Rest wird verteilt)",
        plan_note="Zuerst Sonnenüberschuss, solange das Auto zu Hause steht, der Rest gleichmäßig über die Standzeit verteilt.",
        saving="Ersparnis verteilt", per_year="{cur}/Jahr gegen bisher", vs_guard="{cur}/Jahr gegen den Wächter allein",
        way="Ladeweise", peak="höchste Spitze", cost="Leistungspreis/Jahr", not_ready="nicht fertig",
        w_as_is="wie bisher", w_spread="verteilt (Plugwhen)", w_fixed="Wallbox fertig-bis, kleiner Strom", w_guard="nur Spitzenwächter",
        charges="Ladungen in", days="Tagen", with_plug="davon mit echten Steckzeiten", typical="typisch", parking="Standzeit",
        computed="gerechnet", few="Noch zu wenig Daten (nötig sind 14 Tage und 5 Ladungen):", charges_short="Ladungen",
        missing="Es fehlen Daten:",
        pot_note="Schätzung aus dem eigenen Verlauf (90 Tage). „Nicht fertig“ = so oft hätte bei der Abfahrt Energie gefehlt.",
        now="Jetzt", plugged_in="angesteckt", not_plugged="nicht angesteckt", last="In den letzten", times="Mal angesteckt, davon",
        nights="Nächte", typ_in="Typisch angesteckt um", typ_out="abgezogen um", since="Mitgeschrieben seit",
        plugs_note="Normal anstecken genügt: „Bitte anstecken“ kommt nur, wenn die Reserve nicht reicht.",
        no_plug="Kein Stecker-Sensor eingetragen.",
        wd="['Mo','Di','Mi','Do','Fr','Sa','So']", day="Tag", samples="Tage", km_typ="typisch km", km_high="hoch km", drives="fährt",
        dep="Abfahrt", home="zu Hause geladen",
        week_note="Grundlage: die letzten 8 Tage je Wochentag aus der Langzeitstatistik. „hoch“ = 80. Perzentil.",
        learned_from="Gelernt aus", hist_days="Tagen Verlauf", error="Fehler",
    ),
    "en": dict(
        next="Next departure", departure="Expected departure", charge="Still to charge", range="Range needed",
        target="Target state of charge", ready="Ready for departure", plan_h="Charge plan", plan="Charge plan", pot_h="Potential",
        pot="Potential of spreading the charging", plugs_h="Plug-in times", settings="Settings", week_h="Learned week",
        reserve="Reserve (km) the car always leaves with", learn="Learn kilometres per weekday",
        notice="Warn when the car will not be ready",
        settings_note="**Reserve** is the lowest range. With the switch on, a weekday's learned high value raises it when needed. Off: only the reserve counts.",
        soc="State of charge now", plugged="plugged in", yes="yes", no="no", unknown="unknown", goal="Target at departure",
        basis="Based on", b_learned="the weekday's learned high value (longer than the reserve)",
        b_away="only the reserve (on this weekday the car mostly charges elsewhere)", b_plus="reserve plus learned value",
        b_reserve="the reserve", unreachable="Note: the target cannot be reached with this battery.",
        planned="Planned", in_windows="window(s)", done_at="ready at", up_to="up to", of_avail="of it", avail_kwh="kWh available power",
        not_needed="Nothing needs to be charged.", infeasible="The target cannot be reached by departure: missing",
        no_dep="No departure known.", dep_from="Departure from", entity="entity", learning="learning", load="Load forecast",
        first_from="Power first from", s_solar="the sun (solar forecast)", s_entity="availability sensor",
        s_both="the sun and the availability sensor", s_none="nothing (the rest is spread)",
        plan_note="Solar surplus first while the car is at home, the rest spread evenly over the parking time.",
        saving="Saving by spreading", per_year="{cur} per year against as it was", vs_guard="{cur} per year against the peak guard alone",
        way="Way of charging", peak="highest peak", cost="demand charge per year", not_ready="not ready",
        w_as_is="as it was", w_spread="spread (Plugwhen)", w_fixed="wallbox ready-by, low current", w_guard="peak guard only",
        charges="charging sessions in", days="days", with_plug="with real plug-in times", typical="typically", parking="parking time",
        computed="computed", few="Too little data yet (14 days and 5 sessions needed):", charges_short="sessions",
        missing="Data missing:",
        pot_note="An estimate from your own history (90 days). \"Not ready\" = how often energy would have been missing at departure.",
        now="Now", plugged_in="plugged in", not_plugged="not plugged in", last="In the last", times="plug-ins, of them",
        nights="nights", typ_in="Typically plugged in at", typ_out="unplugged at", since="Recorded since",
        plugs_note="Plug in as usual: \"plug in\" only comes when the reserve would not last.",
        no_plug="No plug sensor set.",
        wd="['Mon','Tue','Wed','Thu','Fri','Sat','Sun']", day="Day", samples="days", km_typ="typical km", km_high="high km", drives="drives",
        dep="Departure", home="charged at home",
        week_note="Based on the last 8 days per weekday from the long-term statistics. \"high\" = 80th percentile.",
        learned_from="Learned from", hist_days="days of history", error="Error",
    ),
}


def _s(entity_id: str) -> str:
    """Jinja access to the state object (states.domain.object_id)."""
    return "states." + entity_id


def _vehicle_section(ids: dict[str, str], t: dict[str, str], name: str, multi: bool) -> list[dict[str, Any]]:
    need = _s(ids["need_charge"]) + ".attributes"
    status = (
        "{% set at = " + need + " %}"
        f"**{t['soc']}:** {{{{ at.soc if at.soc is not none else '–' }}}} % · "
        f"**{t['plugged']}:** {{{{ '{t['yes']}' if at.plugged else ('{t['no']}' if at.plugged is false else '{t['unknown']}') }}}} · "
        f"**{t['goal']}:** {{{{ at.target_soc }}}} % ({{{{ at.range_km }}}} km)\n\n"
        f"**{t['basis']}:** "
        f"{{% if at.source == 'learned' %}}{t['b_learned']}{{% elif at.source == 'away' %}}{t['b_away']}"
        f"{{% elif at.source == 'plus' %}}{t['b_plus']}{{% else %}}{t['b_reserve']} ({{{{ at.reserve_km | int }}}} km){{% endif %}}"
        f"{{% if at.reachable is false %}}\n\n**{t['unreachable']}**{{% endif %}}"
    )
    plan = (
        "{% set wd = " + t["wd"] + " %}"
        "{% set a = " + _s(ids["charge_plan"]) + ".attributes %}{% set st = states('" + ids["charge_plan"] + "') %}"
        f"{{% if st == 'planned' %}}**{t['planned']}:** {{{{ a.planned_kwh }}}} kWh, {{{{ a.windows | length }}}} {t['in_windows']}, {t['done_at']} "
        "{{ (a.ready_at | as_datetime | as_local).strftime('%H:%M') if a.ready_at else '-' }}\n\n"
        "{% for w in a.windows %}- {{ wd[(w.start | as_datetime | as_local).weekday()] }} {{ (w.start | as_datetime | as_local).strftime('%H:%M') }}-{{ (w.end | as_datetime | as_local).strftime('%H:%M') }}: "
        f"{{{{ w.energy_kwh }}}} kWh ({t['up_to']} {{{{ w.peak_kw }}}} kW{{% if w.available_kwh > 0 %}}, {t['of_avail']} {{{{ w.available_kwh }}}} {t['avail_kwh']}{{% endif %}})\n{{% endfor %}}"
        f"{{% elif st == 'not_needed' %}}{t['not_needed']}\n"
        f"{{% elif st == 'infeasible' %}}**{t['infeasible']} {{{{ a.shortfall_kwh }}}} kWh.**\n"
        f"{{% else %}}{t['no_dep']}\n{{% endif %}}"
        f"\n{t['dep_from']}: {{{{ '{t['entity']}' if a.departure_source == 'entity' else ('{t['learning']}' if a.departure_source == 'learned' else '-') }}}} · "
        f"{t['load']}: {{{{ '{t['yes']}' if a.load_forecast_used else '{t['no']}' }}}} · "
        f"{t['first_from']}: {{{{ {{'solar': '{t['s_solar']}', 'entity': '{t['s_entity']}', 'entity+solar': '{t['s_both']}'}}.get(a.availability_source, '{t['s_none']}') }}}}\n\n"
        f"*{t['plan_note']}*"
    )
    pot = (
        "{% set a = " + _s(ids["potential"]) + ".attributes %}{% set st = states('" + ids["potential"] + "') %}"
        "{% if st in ['worth_it', 'setting_enough', 'little'] %}{% set s = a.strategies %}"
        f"{{% set n = {{'as_is': '{t['w_as_is']}', 'spread': '{t['w_spread']}', 'fixed': '{t['w_fixed']}', 'guard': '{t['w_guard']}'}} %}}"
        f"{{% if a.saving_spread_per_year is not none %}}**{t['saving']}:** {{{{ a.saving_spread_per_year | int }}}} {t['per_year']}"
        f"{{% if a.saving_spread_vs_guard_per_year is not none %}}, {{{{ a.saving_spread_vs_guard_per_year | int }}}} {t['vs_guard']}{{% endif %}}\n\n{{% endif %}}"
        f"| {t['way']} | {t['peak']} | {t['cost']} | {t['not_ready']} |\n|---|---|---|---|\n"
        "{% for k in ['as_is', 'guard', 'fixed', 'spread'] if k in s %}"
        "| {{ n[k] }} | {{ (s[k].peaks.values() | max) | round(1) if s[k].peaks else '–' }} kW | "
        "{{ (s[k].cost_per_year | int ~ ' " + t["cur"] + "') if s[k].cost_per_year is not none else '–' }} | {{ s[k].not_ready }} |\n{% endfor %}"
        f"\n{{{{ a.sessions }}}} {t['charges']} {{{{ a.days }}}} {t['days']}, {{{{ a.sessions_with_plug_times or 0 }}}} {t['with_plug']} · "
        f"{t['typical']} {{{{ a.session_kwh_median }}}} kWh, {t['parking']} {{{{ a.window_h_median }}}} h · "
        f"{t['computed']} {{{{ (a.computed_at | as_datetime | as_local).strftime('%d.%m. %H:%M') if a.computed_at else '–' }}}}"
        f"{{% elif st == 'too_little_data' %}}{t['few']} {{{{ a.days }}}} {t['days']}, {{{{ a.sessions }}}} {t['charges_short']}."
        f"{{% else %}}{t['missing']} {{{{ a.missing or a.error or '–' }}}}{{% endif %}}\n\n*{t['pot_note']}*"
    )
    plugs = (
        "{% set p = state_attr('" + ids["readiness"] + "', 'plugging') %}"
        f"{{% if p %}}**{t['now']}:** {{{{ '{t['plugged_in']}' if p.plugged_now else '{t['not_plugged']}' }}}}\n\n"
        f"{t['last']} {{{{ p.days }}}} {t['days']}: {{{{ p.plug_ins }}}} {t['times']} {{{{ p.nights_plugged }}}} {t['nights']}. "
        f"{t['typ_in']} {{{{ p.typical_plug_in or '–' }}}}, {t['typ_out']} {{{{ p.typical_unplug or '–' }}}}.\n\n"
        f"*{t['since']} {{{{ (p.recorded_since | as_datetime | as_local).strftime('%d.%m.%Y') if p.recorded_since else '–' }}}}. {t['plugs_note']}*"
        f"{{% else %}}{t['no_plug']}{{% endif %}}"
    )
    week = (
        "{% set w = state_attr('" + ids["week_plan"] + "', 'week') or [] %}{% set n = " + t["wd"] + " %}"
        f"| {t['day']} | {t['samples']} | {t['km_typ']} | {t['km_high']} | {t['drives']} | {t['dep']} | {t['home']} |\n|---|---|---|---|---|---|---|\n"
        "{% for d in w %}| {{ n[d.day] }} | {{ d.samples }} | {{ d.km_typical if d.km_typical is not none else '–' }} | "
        "{{ d.km_high if d.km_high is not none else '–' }} | "
        "{{ ((d.drive_share * 100) | round(0) | int ~ ' %') if d.drive_share is not none else '–' }} | "
        "{{ ('%d:%02d' | format(d.departure_hour | int, ((d.departure_hour % 1) * 60) | round(0) | int)) if d.departure_hour is not none else '–' }} | "
        "{{ ((d.home_charge_share * 100) | round(0) | int ~ ' %') if d.home_charge_share is not none else '–' }} |\n{% endfor %}"
        f"\n*{t['week_note']}*\n\n"
        "{% set s = " + _s(ids["week_plan"]) + " %}"
        f"{t['learned_from']} {{{{ s.attributes.history_days }}}} {t['hist_days']}"
        f"{{% if s.attributes.history_error %}} · **{t['error']}:** {{{{ s.attributes.history_error }}}}{{% endif %}}."
    )
    head = (lambda h: f"{name} · {h}") if multi else (lambda h: h)
    return [
        {"type": "grid", "cards": [
            {"type": "heading", "heading": head(t["next"]), "icon": "mdi:car-clock"},
            {"type": "tile", "entity": ids["departure"], "name": t["departure"]},
            {"type": "tile", "entity": ids["need_charge"], "name": t["charge"]},
            {"type": "tile", "entity": ids["need_range"], "name": t["range"]},
            {"type": "tile", "entity": ids["target_soc"], "name": t["target"]},
            {"type": "tile", "entity": ids["readiness"], "name": t["ready"]},
            {"type": "markdown", "content": status},
            {"type": "heading", "heading": head(t["plan_h"]), "icon": "mdi:calendar-clock"},
            {"type": "tile", "entity": ids["charge_plan"], "name": t["plan"]},
            {"type": "markdown", "content": plan},
        ]},
        {"type": "grid", "cards": [
            {"type": "heading", "heading": head(t["pot_h"]), "icon": "mdi:chart-bell-curve-cumulative"},
            {"type": "tile", "entity": ids["potential"], "name": t["pot"]},
            {"type": "markdown", "content": pot},
            {"type": "heading", "heading": head(t["plugs_h"]), "icon": "mdi:ev-plug-type2"},
            {"type": "markdown", "content": plugs},
        ]},
        {"type": "grid", "cards": [
            {"type": "heading", "heading": head(t["settings"]), "icon": "mdi:tune"},
            {"type": "entities", "entities": [
                {"entity": ids["reserve_km"], "name": t["reserve"]},
                {"entity": ids["learn_km"], "name": t["learn"]},
                {"entity": ids["notice_enabled"], "name": t["notice"]},
            ]},
            {"type": "markdown", "content": t["settings_note"]},
        ]},
        {"type": "grid", "cards": [
            {"type": "heading", "heading": head(t["week_h"]), "icon": "mdi:calendar-week"},
            {"type": "markdown", "content": week},
        ]},
    ]


def build_views(vehicles: list[dict[str, Any]], language: str | None, currency: str | None = None) -> list[dict[str, Any]]:
    t = dict(TEXT["de"] if (language or "").lower().startswith("de") else TEXT["en"])
    cur = {"EUR": "€", "USD": "$", "GBP": "£", "CHF": "CHF"}.get(currency or "EUR", currency or "€")
    t = {k: v.replace("{cur}", cur) for k, v in t.items()}
    t["cur"] = cur
    sections: list[dict[str, Any]] = []
    for v in vehicles:
        sections += _vehicle_section(v["ids"], t, v["name"], len(vehicles) > 1)
    return [{"title": "Plugwhen", "path": "plugwhen", "icon": "mdi:ev-plug-type2", "type": "sections", "max_columns": 2,
             "sections": sections}]
