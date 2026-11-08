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
    "mode": "select", "would_switch": "sensor", "learning_check": "sensor", "habit": "sensor",
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
        lc_km="Kilometer", lc_depl="Abfahrt", lc_km_helps="Mit dem Gelernten wären", lc_km_helps_b="Prozentpunkte mehr Tage gedeckt gewesen",
        lc_km_same="Die feste Reserve allein deckt fast genauso viele Tage", lc_km_same_b="das Lernen der Kilometer bringt hier wenig",
        lc_dep_good="Mit dem Plan bis zur frühen Abfahrt wäre das Auto an", lc_dep_good_b="Prozent der Tage rechtzeitig fertig gewesen, bis zur üblichen nur an",
        lc_dep_none="Zur Abfahrt gibt es noch keine Aussage.",
        lc_h="Bringt das Lernen etwas?", lc_tile="Lernen: lohnt es sich?", lc_yes="Ja.", lc_no="Kaum.", lc_some="Wenig.",
        lc_helps_a="Mit dem Gelernten wären", lc_helps_b="Prozentpunkte mehr Tage gedeckt gewesen",
        lc_enough="Die feste Reserve allein hätte fast genauso viele Tage gedeckt", lc_enough_b="Das Lernen schadet nicht, bringt bei der Reichweite hier aber wenig.",
        lc_dep_a="Abfahrtszeit: an", lc_dep_b="Prozent der", lc_dep_c="Fahrtage auf ± 1 Stunde richtig geraten.",
        lc_few_a="Noch zu wenig Daten: geprüft wurden", lc_few_b="Tage, nötig sind 21.",
        lc_note="Geprüft wird Tag für Tag an Ihrem eigenen Verlauf, wobei an jedem Tag nur die Tage davor bekannt sind.",
        shadow_chart_h="Plan gegen Wirklichkeit",
        cal_sun="Sonne", cal_factor="Prognose ×", cal_learned="bei Ihnen gelernt", cal_unchecked="Prognose noch ungeprüft",
        cal_deduct="Abzug fürs Haus", cal_src_learned="gelernt", cal_src_setting="eingestellt", cal_src_default="Vorgabe",
        cal_loss="Ladeverluste", cal_floor="verteilt ab",
        hb_h="Wann laden Sie?", hb_tile="Nachts geladen", hb_a="Nachts (20–7 Uhr) wurden", hb_b="Prozent der Energie geladen, tagsüber (9–17 Uhr)",
        hb_c="Prozent, am Wochenende", hb_d="Prozent. Mo bis Fr nachts:", hb_few="Noch zu wenig Daten für die Ladegewohnheit (28 Tage nötig).",
        hz_covered="Bei normalem Verhalten reicht der Ladestand bis", hz_must="Danach muss geladen werden: spätestens ab", hz_all="Bei normalem Verhalten reicht der Ladestand für alle Abfahrten der nächsten", hz_days="Tage",
        hz_sun_ok="die Sonne kann es decken", hz_forecast="Die Sonnenprognose reicht nur so weit, wie Ihr Anbieter sie liefert.",
        hz_h="Die nächsten Abfahrten", hz_next="Nächstes nötiges Laden", hz_for="für", hz_latest="spätestens ab", hz_at="bei", hz_pre="Mit Sonne vorladen",
        hz_replaces="ersetzt Netzstrom vor", hz_note="Eine Empfehlung: Plugwhen schaltet nichts. Ohne Solaranlage zeigt die Grafik nur den Bedarf je Abfahrt.",
        learn_h="Lernmodus", mode_name="Betriebsart", would="Würde schalten",
        w_charge="Laden", w_pause="Pausieren", w_none="Keine Entscheidung", w_off="Aus",
        r_in_window="im geplanten Fenster", r_waiting_for_window="wartet auf das nächste Fenster", r_plan_done="der Plan ist abgearbeitet",
        r_cannot_reach_target="das Ziel ist knapp: so viel wie möglich sofort", r_unknown_soc="Ladestand unbekannt",
        r_not_plugged="nicht angesteckt", r_not_needed="es muss nichts geladen werden", r_no_plan="kein Plan (keine Abfahrt)",
        until_t="bis", lm_week="Vergleich mit der Wirklichkeit, letzte 7 Tage", lm_agree="Übereinstimmung", lm_days="Tage mit Daten",
        lm_pause_ch="Stunden, in denen die Wallbox lud, obwohl Plugwhen pausiert hätte", lm_kwh_pause="kWh in diesen Zeiten",
        lm_charge_idle="Stunden ohne Laden im geplanten Fenster", lm_kwh_charge="kWh in den geplanten Fenstern",
        lm_journal="Letzte Entscheidungen", lm_none="Noch keine Entscheidungen.", lm_off="Der Lernmodus ist aus.",
        lm_needless="Ohne Bedarf geladen (zum Beispiel mit Sonne)", lm_needless_in="kWh in den letzten 7 Tagen",
        lm_note="Im Lernmodus wird nichts geschaltet: Plugwhen schreibt nur auf, was es tun würde, und vergleicht das mit dem, was die Wallbox wirklich getan hat. Die Wallbox läuft weiter wie bisher.",
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
        lc_km="Kilometres", lc_depl="Departure", lc_km_helps="With what was learned", lc_km_helps_b="percentage points more days would have been covered",
        lc_km_same="The fixed reserve alone covers almost as many days", lc_km_same_b="learning the kilometres brings little here",
        lc_dep_good="With the plan until the early departure the car would have been ready in time on", lc_dep_good_b="percent of the days, with the one until the usual departure only on",
        lc_dep_none="There is no statement about the departure yet.",
        lc_h="Does learning help?", lc_tile="Does learning help?", lc_yes="Yes.", lc_no="Hardly.", lc_some="A little.",
        lc_helps_a="With what was learned", lc_helps_b="percentage points more days would have been covered",
        lc_enough="The fixed reserve alone would have covered almost as many days", lc_enough_b="Learning does no harm, but brings little for the range here.",
        lc_dep_a="Departure hour: on", lc_dep_b="percent of the", lc_dep_c="days with a trip it was guessed right within 1 hour.",
        lc_few_a="Too little data yet: checked", lc_few_b="days, 21 are needed.",
        lc_note="It is checked day by day against your own history, and on each day only the days before it are known.",
        shadow_chart_h="Plan against reality",
        cal_sun="Sun", cal_factor="forecast ×", cal_learned="learned here", cal_unchecked="forecast not checked yet",
        cal_deduct="deduction for the house", cal_src_learned="learned", cal_src_setting="setting", cal_src_default="default",
        cal_loss="charging losses", cal_floor="spread from",
        hb_h="When do you charge?", hb_tile="Charged at night", hb_a="At night (20 to 7 h)", hb_b="percent of the energy were charged, during the day (9 to 17 h)",
        hb_c="percent, at the weekend", hb_d="percent. Mon to Fri at night:", hb_few="Too little data for the charging habit yet (28 days needed).",
        hz_covered="With normal behaviour the charge lasts until", hz_must="After that charging is needed: latest start", hz_all="With normal behaviour the charge is enough for all departures of the next", hz_days="days",
        hz_sun_ok="the sun can cover it", hz_forecast="The solar forecast only reaches as far as your provider delivers it.",
        hz_h="The next departures", hz_next="Next charging needed", hz_for="for", hz_latest="latest start", hz_at="at", hz_pre="Charge ahead with the sun",
        hz_replaces="replaces grid energy before", hz_note="A recommendation: Plugwhen switches nothing. Without a solar plant the chart only shows the need per departure.",
        learn_h="Learn mode", mode_name="Mode", would="Would switch",
        w_charge="Charge", w_pause="Pause", w_none="No decision", w_off="Off",
        r_in_window="in a planned window", r_waiting_for_window="waiting for the next window", r_plan_done="the plan is done",
        r_cannot_reach_target="the target is tight: as much as possible at once", r_unknown_soc="state of charge unknown",
        r_not_plugged="not plugged in", r_not_needed="nothing needs to be charged", r_no_plan="no plan (no departure)",
        until_t="until", lm_week="Comparison with reality, last 7 days", lm_agree="Agreement", lm_days="days with data",
        lm_pause_ch="hours the wallbox charged although Plugwhen would have paused", lm_kwh_pause="kWh in those times",
        lm_charge_idle="hours without charging in a planned window", lm_kwh_charge="kWh in the planned windows",
        lm_journal="Latest decisions", lm_none="No decisions yet.", lm_off="Learn mode is off.",
        lm_needless="Charged although nothing was needed (for example with the sun)", lm_needless_in="kWh in the last 7 days",
        lm_note="Nothing is switched in learn mode: Plugwhen only writes down what it would do and compares it with what the wallbox really did. The wallbox keeps working as before.",
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


def _chart(entity_id: str, attribute: str = "chart") -> str:
    """A markdown card body that shows the SVG chart of an attribute (nothing while it is missing)."""
    return ("{% set c = state_attr('" + entity_id + "', '" + attribute + "') %}"
            "{% if c %}![](data:image/svg+xml;utf8,{{ c | urlencode }}){% endif %}")


def _vehicle_section(ids: dict[str, str], t: dict[str, str], name: str, multi: bool) -> list[dict[str, Any]]:
    """Graphics first, one short line of text where a number needs words; settings stay on the dashboard."""
    need = _s(ids["need_charge"]) + ".attributes"
    status = (
        "{% set at = " + need + " %}"
        f"**{t['soc']}:** {{{{ at.soc if at.soc is not none else '–' }}}} % · "
        f"**{t['plugged']}:** {{{{ '{t['yes']}' if at.plugged else ('{t['no']}' if at.plugged is false else '{t['unknown']}') }}}} · "
        f"**{t['goal']}:** {{{{ at.target_soc }}}} % ({{{{ at.range_km }}}} km)"
        f"{{% if at.reachable is false %}}\n\n**{t['unreachable']}**{{% endif %}}"
    )
    pot_line = (
        "{% set a = " + _s(ids["potential"]) + ".attributes %}"
        f"{{% if a.get('saving_spread_per_year') is not none %}}**{t['saving']}:** {{{{ a.saving_spread_per_year | int }}}} {t['per_year']}"
        f"{{% if a.get('saving_spread_vs_guard_per_year') is not none %}}, {{{{ a.saving_spread_vs_guard_per_year | int }}}} {t['vs_guard']}{{% endif %}}{{% endif %}}"
    )
    plugs_line = (
        "{% set p = state_attr('" + ids["readiness"] + "', 'plugging') %}"
        f"{{% if p %}}**{t['now']}:** {{{{ '{t['plugged_in']}' if p.plugged_now else '{t['not_plugged']}' }}}}"
        f"{{% else %}}{t['no_plug']}{{% endif %}}"
    )
    reasons = "{" + ", ".join(f"'{k}': '{t['r_' + k]}'" for k in (
        "in_window", "waiting_for_window", "plan_done", "cannot_reach_target", "unknown_soc", "not_plugged", "not_needed", "no_plan")) + "}"
    would_names = "{" + ", ".join(f"'{k}': '{t['w_' + k]}'" for k in ("charge", "pause", "none", "off")) + "}"
    learn_line = (
        "{% set a = " + _s(ids["would_switch"]) + ".attributes %}{% set st = states('" + ids["would_switch"] + "') %}"
        "{% set rs = " + reasons + " %}{% set wn = " + would_names + " %}"
        f"{{% if st == 'off' %}}{t['lm_off']}{{% else %}}"
        f"**{t['would']}:** {{{{ wn.get(st, st) }}}} · {{{{ rs.get(a.reason, a.reason) }}}}"
        f"{{% if a.until %}} · {t['until_t']} {{{{ (a.until | as_datetime | as_local).strftime('%H:%M') }}}}{{% endif %}}{{% endif %}}"
        f"{{% if a.summary and a.summary.kwh_needless %}}\n\n{t['lm_needless']}: **{{{{ a.summary.kwh_needless }}}}** {t['lm_needless_in']}{{% endif %}}"
    )
    lc_id = ids["learning_check"]
    lc_line = (
        "{% set a = " + _s(lc_id) + ".attributes %}{% set st = states('" + lc_id + "') %}"
        f"{{% if st == 'too_little_data' %}}{t['lc_few_a']} {{{{ a.days }}}} {t['lc_few_b']}{{% else %}}"
        f"**{t['lc_km']}:** {{% if st == 'learning_helps' %}}{t['lc_km_helps']} {{{{ a.gain_points }}}} {t['lc_km_helps_b']}."
        f"{{% else %}}{t['lc_km_same']} ({{{{ a.coverage_reserve_pct }}}} → {{{{ a.coverage_learned_pct }}}} %): {t['lc_km_same_b']}.{{% endif %}}\n\n"
        f"**{t['lc_depl']}:** {{% if a.ready_early_pct is not none %}}{t['lc_dep_good']} {{{{ a.ready_early_pct }}}} {t['lc_dep_good_b']} {{{{ a.ready_median_pct }}}} %."
        f"{{% else %}}{t['lc_dep_none']}{{% endif %}}{{% endif %}}"
    )
    calib_line = (
        "{% set a = " + _s(ids["charge_plan"]) + ".attributes %}{% set n = " + need + " %}"
        "{% if a.solar_deduct_kw is not none %}"
        f"{t['cal_sun']}: {{% if a.solar_factor %}}{t['cal_factor']} {{{{ a.solar_factor }}}} ({t['cal_learned']}){{% else %}}{t['cal_unchecked']}{{% endif %}} · "
        f"{t['cal_deduct']} {{{{ a.solar_deduct_kw }}}} kW ({{{{ {{'learned': '{t['cal_src_learned']}', 'setting': '{t['cal_src_setting']}', 'default': '{t['cal_src_default']}'}}.get(a.solar_deduct_source, '') }}}}) · "
        f"{t['cal_loss']} {{{{ ((1 - (n.efficiency or 0.9)) * 100) | round(0) | int }}}} % ({{{{ '{t['cal_src_learned']}' if n.efficiency_learned else '{t['cal_src_default']}' }}}})"
        f"{{% if a.spread_floor_kw %}} · {t['cal_floor']} {{{{ a.spread_floor_kw }}}} kW{{% endif %}}{{% endif %}}"
    )
    hz_tpl = (
        "{% set wd = " + t["wd"] + " %}{% set a = " + _s(ids["charge_plan"]) + ".attributes %}{% set h = a.horizon %}"
        "{% if h and h.status == 'ok' %}"
        "{% set fn = h.first_need %}"
        "{% if fn %}"
        "{% if h.lasts_until %}{% set lu = h.lasts_until | as_datetime | as_local %}**@COVERED@** {{ wd[lu.weekday()] }} {{ lu.strftime('%H:%M') }}. {% endif %}"
        "{% set dp = fn.departure | as_datetime | as_local %}{% set ls = (fn.latest_start_pref or fn.latest_start) | as_datetime | as_local %}"
        "**@MUST@** {{ wd[ls.weekday()] }} {{ ls.strftime('%H:%M') }}"
        "{% if fn.latest_start_pref %} @AT@ {{ a.pref_kw }} kW{% endif %} (@FOR@ {{ wd[dp.weekday()] }} {{ dp.strftime('%H:%M') }}: {{ fn.need_kwh }} kWh"
        "{% if fn.covered_by_sun %}, @SUNOK@{% endif %})"
        "{% else %}@ALL@ {{ h.trips_looked_at }} @DAYS@."
        "{% endif %}"
        "{% for p in h.precharge %}{% set sf = p.sun_from | as_datetime | as_local %}{% set st = p.sun_to | as_datetime | as_local %}{% set fd = p.for_departure | as_datetime | as_local %}"
        "\n\n**@PRE@:** {{ wd[sf.weekday()] }} {{ sf.strftime('%H:%M') }}–{{ st.strftime('%H:%M') }}: {{ p.kwh }} kWh (@REPL@ {{ wd[fd.weekday()] }} {{ fd.strftime('%H:%M') }})"
        "{% endfor %}"
        "{% endif %}"
    )
    for key, text in (("@COVERED@", t["hz_covered"]), ("@MUST@", t["hz_must"]), ("@ALL@", t["hz_all"]), ("@DAYS@", t["hz_days"]), ("@SUNOK@", t["hz_sun_ok"]), ("@NEXT@", t["hz_next"]), ("@FOR@", t["hz_for"]), ("@LATEST@", t["hz_latest"]), ("@AT@", t["hz_at"]), ("@PRE@", t["hz_pre"]), ("@REPL@", t["hz_replaces"])):
        hz_tpl = hz_tpl.replace(key, text)
    hb_id = ids["habit"]
    habit_line = (
        "{% set a = " + _s(hb_id) + ".attributes %}"
        f"{{% if a.status == 'ok' %}}{t['hb_a']} **{{{{ a.night_share_pct }}}}** {t['hb_b']} **{{{{ a.day_share_pct }}}}**"
        f" {t['hb_c']} **{{{{ a.weekend_share_pct }}}}** {t['hb_d']} **{{{{ a.weekdays_night_share_pct }}}} %**."
        f"{{% else %}}{t['hb_few']}{{% endif %}}"
    )
    head = (lambda h: f"{name} · {h}") if multi else (lambda h: h)
    return [
        {"type": "grid", "cards": [
            {"type": "heading", "heading": head(t["next"]), "icon": "mdi:car-clock"},
            {"type": "tile", "entity": ids["departure"], "name": t["departure"]},
            {"type": "tile", "entity": ids["need_charge"], "name": t["charge"]},
            {"type": "tile", "entity": ids["readiness"], "name": t["ready"]},
            {"type": "markdown", "content": status},
            {"type": "heading", "heading": head(t["plan_h"]), "icon": "mdi:calendar-clock"},
            {"type": "markdown", "content": _chart(ids["charge_plan"])},
            {"type": "markdown", "content": calib_line},
            {"type": "heading", "heading": head(t["hz_h"]), "icon": "mdi:calendar-arrow-right"},
            {"type": "markdown", "content": _chart(ids["charge_plan"], "horizon_chart")},
            {"type": "markdown", "content": _chart(ids["charge_plan"], "sun_chart")},
            {"type": "markdown", "content": hz_tpl},
        ]},
        {"type": "grid", "cards": [
            {"type": "heading", "heading": head(t["pot_h"]), "icon": "mdi:chart-bell-curve-cumulative"},
            {"type": "tile", "entity": ids["potential"], "name": t["pot"]},
            {"type": "markdown", "content": _chart(ids["potential"])},
            {"type": "markdown", "content": pot_line},
            {"type": "heading", "heading": head(t["plugs_h"]), "icon": "mdi:ev-plug-type2"},
            {"type": "markdown", "content": _chart(ids["readiness"], "plug_chart")},
            {"type": "markdown", "content": plugs_line},
        ]},
        {"type": "grid", "cards": [
            {"type": "heading", "heading": head(t["hb_h"]), "icon": "mdi:chart-bar-stacked"},
            {"type": "tile", "entity": hb_id, "name": t["hb_tile"]},
            {"type": "markdown", "content": _chart(hb_id)},
            {"type": "markdown", "content": habit_line},
        ]},
        {"type": "grid", "cards": [
            {"type": "heading", "heading": head(t["learn_h"]), "icon": "mdi:school-outline"},
            {"type": "tile", "entity": ids["would_switch"], "name": t["would"]},
            {"type": "entities", "show_header_toggle": False, "entities": [{"entity": ids["mode"], "name": t["mode_name"]}]},
            {"type": "markdown", "content": learn_line},
            {"type": "markdown", "content": _chart(ids["would_switch"])},
        ]},
        {"type": "grid", "cards": [
            {"type": "heading", "heading": head(t["lc_h"]), "icon": "mdi:school-outline"},
            {"type": "tile", "entity": ids["learning_check"], "name": t["lc_tile"]},
            {"type": "markdown", "content": lc_line},
            {"type": "markdown", "content": _chart(lc_id)},
        ]},
        {"type": "grid", "cards": [
            {"type": "heading", "heading": head(t["settings"]), "icon": "mdi:tune"},
            {"type": "entities", "show_header_toggle": False, "entities": [
                {"entity": ids["reserve_km"], "name": t["reserve"]},
                {"entity": ids["learn_km"], "name": t["learn"]},
                {"entity": ids["notice_enabled"], "name": t["notice"]},
            ]},
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
