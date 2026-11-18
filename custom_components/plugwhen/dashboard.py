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
    "notice_enabled": "switch", "switch_ready": "sensor",
    "weekly_full": "switch", "weekly_target": "number", "days_ahead": "number", "daily_cap": "number",
    **{f"weekly_day_{d}": "switch" for d in range(7)},
}

TEXT = {
    "de": dict(
        next="Nächste Abfahrt", departure="Erwartete Abfahrt", charge="Noch zu laden", range="Nötige Reichweite",
        target="Ziel-Ladestand", ready="Bereit zur Abfahrt", plan_h="Ladeplan", plan="Ladeplan", pot_h="Potenzial",
        pot="Potenzial", plugs_h="Steckzeiten", settings="Einstellungen", week_h="Gelernter Wochenplan",
        reserve="Reserve beim Losfahren", learn="Kilometer je Wochentag lernen",
        notice="Warnen, wenn nicht bereit",
        days_ahead="Tage auf einmal laden", daily_cap="Grenze für mehrere Tage",
        wf="Einmal pro Woche voll laden", wf_days="An diesen Tagen (mit PV: der sonnigste)", wf_target="Ziel beim Volladen",
        wf_days_names="Montag,Dienstag,Mittwoch,Donnerstag,Freitag,Samstag,Sonntag", wf_days_short="Mo,Di,Mi,Do,Fr,Sa,So",
        wf_days_hint="Tage antippen. Mehrere Tage: mit Solarprognose der sonnigste, sonst der erste.",
        wf_active="**Volladen läuft:** Ziel {t} %, zuerst mit Sonne, der Rest aus dem Netz.", wf_planned="Volladen geplant für {d}.",
        wf_done="Volladen diese Woche erledigt (einen Tag aus- und wieder einschalten für noch einmal).", wf_none="Diese Woche ist kein erlaubter Tag mehr übrig.",
        settings_note="**Reserve** ist die Untergrenze der Reichweite. Ist der Schalter an, hebt der gelernte hohe Wert eines Wochentags sie bei Bedarf an. Aus: nur die Reserve zählt.",
        lc_km="Kilometer", lc_depl="Abfahrt", lc_km_helps="Mit dem Gelernten wären", lc_km_helps_b="Prozentpunkte mehr Tage gedeckt gewesen",
        lc_km_same="Die feste Reserve allein deckt fast genauso viele Tage", lc_km_same_b="das Lernen der Kilometer bringt hier wenig",
        lc_dep_good="Mit dem Plan bis zur frühen Abfahrt wäre das Auto an", lc_dep_good_b="Prozent der Tage rechtzeitig fertig gewesen, bis zur üblichen nur an",
        lc_dep_none="Zur Abfahrt gibt es noch keine Aussage.",
        lc_h="Bringt das Lernen etwas?", lc_tile="Nutzt das Lernen?", lc_yes="Ja.", lc_no="Kaum.", lc_some="Wenig.",
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
        msg_h="Letzte Hinweise", msg_none="Noch keine Hinweise. Hier stehen die Meldungen ans Handy, auch wenn sie dort weggeklickt wurden.",
        w_charge="Laden", w_pause="Pausieren", w_none="Keine Entscheidung", w_off="Aus",
        r_in_window="im geplanten Fenster", r_waiting_for_window="wartet auf das nächste Fenster", r_plan_done="der Plan ist abgearbeitet",
        r_cannot_reach_target="das Ziel ist knapp: so viel wie möglich sofort", r_unknown_soc="Ladestand unbekannt",
        r_not_plugged="nicht angesteckt", r_not_needed="es muss nichts geladen werden", r_no_plan="kein Plan (keine Abfahrt)",
        until_t="bis", lm_week="Vergleich mit der Wirklichkeit, letzte 7 Tage", lm_agree="Übereinstimmung", lm_days="Tage mit Daten",
        lm_pause_ch="Stunden, in denen die Wallbox lud, obwohl Plugwhen pausiert hätte", lm_kwh_pause="kWh in diesen Zeiten",
        lm_charge_idle="Stunden ohne Laden im geplanten Fenster", lm_kwh_charge="kWh in den geplanten Fenstern",
        lm_journal="Letzte Entscheidungen", lm_none="Noch keine Entscheidungen.", lm_off="Probelauf aus. Fahrten und Verbrauch lernt Plugwhen trotzdem weiter.",
        lm_needless="Ohne Bedarf geladen (zum Beispiel mit Sonne)", lm_needless_in="kWh in den letzten 7 Tagen",
        lm_note="Im Lernmodus wird nichts geschaltet: Plugwhen schreibt nur auf, was es tun würde, und vergleicht das mit dem, was die Wallbox wirklich getan hat. Die Wallbox läuft weiter wie bisher.",
        soc="Ladestand jetzt", plugged="angesteckt", yes="ja", no="nein", unknown="unbekannt", goal="Ziel bei Abfahrt", ahead_fill="lädt im Voraus bis", ahead_days="Tage", ahead_sun="der Sonne überlassen",
        basis="Grundlage", b_learned="gelernter hoher Wert des Wochentags (länger als die Reserve)",
        b_away="nur die Reserve (an diesem Wochentag wird meist unterwegs geladen)", b_plus="Reserve plus gelernter Wert",
        b_reserve="die Reserve", unreachable="Achtung: das Ziel ist mit dem Akku nicht erreichbar.",
        planned="Geplant", in_windows="Fenster", done_at="fertig um", up_to="bis", of_avail="davon", avail_kwh="kWh verfügbarer Strom",
        not_needed="Es muss nichts geladen werden.", infeasible="Das Ziel ist bis zur Abfahrt nicht erreichbar: es fehlen",
        no_dep="Keine Abfahrt bekannt.", dep_from="Abfahrt aus", entity="Entität", learning="Lernen", load="Last-Prognose",
        first_from="Strom zuerst aus", s_solar="Sonne (Solarprognose)", s_entity="Verfügbarkeits-Sensor",
        s_both="Sonne und Verfügbarkeits-Sensor", s_none="nichts (der Rest wird verteilt)",
        plan_note="Zuerst Sonnenüberschuss, solange das Auto zu Hause steht, der Rest gleichmäßig über die Standzeit verteilt.",
        plan_wallbox="Die Fenster sind ein Vorschlag: Die Wallbox hat Abfahrtszeit und Energie bekommen und entscheidet selbst, wann sie lädt.",
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
        src_h="Woher die Daten kommen", src_soc="Ladestand", src_odo="Kilometerstand", src_plug="Angesteckt", src_chg="Lädt",
        src_wb="Energiezähler Wallbox", src_dep="Abfahrt", src_plan="Ladeplan", src_evcc="evcc", src_set="Eingerichtet mit Werten aus",
        src_sensor="Sensor", src_from_evcc="evcc (Ladepunkt)", src_none="nicht bekannt", src_learned="gelernt",
        src_rec="nur Empfehlung, es wird nichts geschaltet", src_exec="wird ausgeführt", src_own="eigene Adresse",
        src_guard_addr="Adresse aus dem Wächter", src_ok="antwortet", src_fail="antwortet nicht", src_unused="kein Auto in evcc gewählt",
        src_guard="Wächter", src_manual="von Hand",
        ep_h="Plan für evcc", ep_would="Plugwhen würde schreiben", ep_now="In evcc jetzt", ep_none="kein Plan", ep_nothing="nichts",
        ep_until="bis", ep_unreach="evcc antwortet nicht", ep_same="gleich wie in evcc", ep_own="eigener Plan in evcc, würde nicht überschrieben",
        ep_not_written="Noch nicht geschrieben (Lernmodus).", ep_no_evcc="Ohne evcc schaltet Plugwhen die Wallbox später selbst; im Lernmodus siehe „Würde schalten“.",
        ep_r_not_needed="Ladung reicht", ep_r_unknown_soc="Ladestand unbekannt", ep_r_no_departure="keine Abfahrt", ep_r_no_target="kein Ziel",
        ep_r_covered="Ladung reicht bis", ep_r_covered_all="Ladung reicht für alle gelernten Abfahrten", ep_next="nächste nötige Ladung",
        ep_week="Wochenpläne (Vorschlag)", ep_week_now="Wochenpläne in evcc", ep_week_none="noch zu wenig gelernt", ep_week_same="gleich wie in evcc",
        ep_follow="Der Plan wird laufend angepasst (mehr Kilometer, Sonne, nächste Abfahrt).",
        ep_expired="der alte Plan ist abgelaufen", ep_written="In evcc geschrieben.", ep_write_off="Geschrieben wird erst in der Betriebsart „Über evcc“ (oben); dann lädt evcc nach diesem Plan.",
        ep_write_err="Schreiben fehlgeschlagen", ep_mine="von Plugwhen geschrieben",
        tr_h="Eingetragene Fahrten", tr_none="Keine Fahrten im Kalender.", tr_nocal="Kein Kalender eingetragen. Fahrten können Sie in einem Kalender von Home Assistant eintragen (Titel z. B. „Linz 200 km“).",
        tr_km_event="aus dem Termin", tr_km_route="Strecke über Waze, hin und zurück", tr_km_route1="Strecke über Waze, einfach", tr_km_none="Kilometer unbekannt, gelernter Tag zählt",
        tr_range="Ziel bei Abfahrt", tr_why_res="Reserve", tr_why_km="Strecke + 15 %", tr_err="Kalender nicht lesbar",
        v_overview="Übersicht", v_learning="Lernen", v_details="Details", sun_h="Sonne und gelernte Werte",
        rd_h="Bereit zum Schalten?", rd_trips="Fahrten gelernt", rd_cmp="Tage mit Vergleich (Lernmodus)", rd_agree="Gleich entschieden",
        rd_solar="Sonnenprognose geprüft", rd_days="Tage", rd_wd="Wochentage", rd_est="voraussichtlich ab",
        rd_ready="Bereit: Plugwhen hat oft genug gleich entschieden wie die Wirklichkeit. Ohne evcc kann jetzt die Betriebsart „Direkt“ (Plugwhen schaltet die Wallbox) gewählt werden.",
        rd_wait="Noch nicht bereit. Bis dahin plant und warnt Plugwhen, und in der Betriebsart „Über evcc“ lädt evcc nach dem Plan.",
        rd_low="Die Entscheidungen passen noch nicht gut genug zur Wirklichkeit (Reiter Lernen).",
        rd_wb="Wallbox-Steuerung erkannt", rd_wb_trip="Abfahrtsmodus der Wallbox (Zeit und Energie, Sonne bleibt zuerst)",
        rd_wb_mode="Moduswechsel (Netz in den geplanten Fenstern, sonst Sonnenmodus)", rd_wb_buttons="Start und Stopp in den geplanten Fenstern",
        rd_wb_none="keine (die Wallbox braucht einen Lademodus oder Start/Stopp in Home Assistant)",
        rd_evcc_note="Dieses Auto ist mit evcc verknüpft: Dann steuert evcc (Betriebsart „Über evcc“). „Direkt“ gibt es nur für ein Auto ohne evcc-Verknüpfung.",
        tr_how="**So tragen Sie eine Fahrt ein:** im Kalender auf den Tag tippen, Titel mit Ziel und Kilometern („Linz 200 km“), "
               "Beginn = Abfahrtszeit. Ohne Kilometer zählt der **Ort** (über Waze, falls eingeschaltet), hin und zurück; „einfach“ im Titel = nur eine Richtung. "
               "Ganztägige Termine zählen nicht.",
        tr_setup="**Kalender einrichten:** Einstellungen → Geräte & Dienste → Integration hinzufügen → „Lokaler Kalender“ (z. B. „Fahrten“), "
                 "dann bei Plugwhen am Fahrzeug unter Konfigurieren „Kalender mit Fahrten“ wählen.",
        wd="['Mo','Di','Mi','Do','Fr','Sa','So']", day="Tag", samples="Tage", km_typ="typisch km", km_high="hoch km", drives="fährt",
        dep="Abfahrt", home="zu Hause geladen",
        week_note="Grundlage: die letzten 8 Tage je Wochentag aus der Langzeitstatistik. „hoch“ = 80. Perzentil.",
        learned_from="Gelernt aus", hist_days="Tagen Verlauf", error="Fehler",
    ),
    "en": dict(
        next="Next departure", departure="Expected departure", charge="Still to charge", range="Range needed",
        target="Target state of charge", ready="Ready for departure", plan_h="Charge plan", plan="Charge plan", pot_h="Potential",
        pot="Potential", plugs_h="Plug-in times", settings="Settings", week_h="Learned week",
        reserve="Reserve at departure", learn="Learn kilometres per weekday",
        notice="Warn if not ready in time",
        days_ahead="Days charged at once", daily_cap="Limit for several days",
        wf="Once a week full", wf_days="On these days (with PV: the sunniest)", wf_target="Target of the full charge",
        wf_days_names="Monday,Tuesday,Wednesday,Thursday,Friday,Saturday,Sunday", wf_days_short="Mo,Tu,We,Th,Fr,Sa,Su",
        wf_days_hint="Tap the days. Several days: the sunniest with a solar forecast, otherwise the first.",
        wf_active="**Full charge running:** target {t} %, sun first, the rest from the grid.", wf_planned="Full charge planned for {d}.",
        wf_done="Full charge done this week (switch a day off and on again for one more).", wf_none="No allowed day is left this week.",
        settings_note="**Reserve** is the lowest range. With the switch on, a weekday's learned high value raises it when needed. Off: only the reserve counts.",
        lc_km="Kilometres", lc_depl="Departure", lc_km_helps="With what was learned", lc_km_helps_b="percentage points more days would have been covered",
        lc_km_same="The fixed reserve alone covers almost as many days", lc_km_same_b="learning the kilometres brings little here",
        lc_dep_good="With the plan until the early departure the car would have been ready in time on", lc_dep_good_b="percent of the days, with the one until the usual departure only on",
        lc_dep_none="There is no statement about the departure yet.",
        lc_h="Does learning help?", lc_tile="Learning useful?", lc_yes="Yes.", lc_no="Hardly.", lc_some="A little.",
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
        msg_h="Latest messages", msg_none="No messages yet. The messages to the phone appear here, even when swiped away there.",
        w_charge="Charge", w_pause="Pause", w_none="No decision", w_off="Off",
        r_in_window="in a planned window", r_waiting_for_window="waiting for the next window", r_plan_done="the plan is done",
        r_cannot_reach_target="the target is tight: as much as possible at once", r_unknown_soc="state of charge unknown",
        r_not_plugged="not plugged in", r_not_needed="nothing needs to be charged", r_no_plan="no plan (no departure)",
        until_t="until", lm_week="Comparison with reality, last 7 days", lm_agree="Agreement", lm_days="days with data",
        lm_pause_ch="hours the wallbox charged although Plugwhen would have paused", lm_kwh_pause="kWh in those times",
        lm_charge_idle="hours without charging in a planned window", lm_kwh_charge="kWh in the planned windows",
        lm_journal="Latest decisions", lm_none="No decisions yet.", lm_off="Trial run off. Plugwhen still keeps learning trips and consumption.",
        lm_needless="Charged although nothing was needed (for example with the sun)", lm_needless_in="kWh in the last 7 days",
        lm_note="Nothing is switched in learn mode: Plugwhen only writes down what it would do and compares it with what the wallbox really did. The wallbox keeps working as before.",
        soc="State of charge now", plugged="plugged in", yes="yes", no="no", unknown="unknown", goal="Target at departure", ahead_fill="charging ahead to", ahead_days="days", ahead_sun="left to the sun",
        basis="Based on", b_learned="the weekday's learned high value (longer than the reserve)",
        b_away="only the reserve (on this weekday the car mostly charges elsewhere)", b_plus="reserve plus learned value",
        b_reserve="the reserve", unreachable="Note: the target cannot be reached with this battery.",
        planned="Planned", in_windows="window(s)", done_at="ready at", up_to="up to", of_avail="of it", avail_kwh="kWh available power",
        not_needed="Nothing needs to be charged.", infeasible="The target cannot be reached by departure: missing",
        no_dep="No departure known.", dep_from="Departure from", entity="entity", learning="learning", load="Load forecast",
        first_from="Power first from", s_solar="the sun (solar forecast)", s_entity="availability sensor",
        s_both="the sun and the availability sensor", s_none="nothing (the rest is spread)",
        plan_note="Solar surplus first while the car is at home, the rest spread evenly over the parking time.",
        plan_wallbox="The windows are a proposal: the wallbox was given the departure and the energy and decides itself when to charge.",
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
        src_h="Where the data comes from", src_soc="State of charge", src_odo="Odometer", src_plug="Plugged in", src_chg="Charging",
        src_wb="Wallbox energy counter", src_dep="Departure", src_plan="Charge plan", src_evcc="evcc", src_set="Set up with values from",
        src_sensor="sensor", src_from_evcc="evcc (loadpoint)", src_none="not known", src_learned="learned",
        src_rec="recommendation only, nothing is switched", src_exec="executed", src_own="own address",
        src_guard_addr="address of the guard", src_ok="answers", src_fail="does not answer", src_unused="no car chosen in evcc",
        src_guard="guard", src_manual="by hand",
        ep_h="Plan for evcc", ep_would="Plugwhen would write", ep_now="In evcc now", ep_none="no plan", ep_nothing="nothing",
        ep_until="until", ep_unreach="evcc does not answer", ep_same="same as in evcc", ep_own="own plan in evcc, would not be overwritten",
        ep_not_written="Not written yet (learn mode).", ep_no_evcc="Without evcc Plugwhen will switch the wallbox itself later; in learn mode see \u201cWould switch\u201d.",
        ep_r_not_needed="charge is enough", ep_r_unknown_soc="state of charge unknown", ep_r_no_departure="no departure", ep_r_no_target="no target",
        ep_r_covered="charge lasts until", ep_r_covered_all="charge lasts for all learned departures", ep_next="next charging needed",
        ep_week="Repeating plans (proposal)", ep_week_now="Repeating plans in evcc", ep_week_none="too little learned yet", ep_week_same="same as in evcc",
        ep_follow="The plan follows what happens (more kilometres, sun, the next departure).",
        ep_expired="the old plan has expired", ep_written="Written into evcc.", ep_write_off="It is written only in the mode \u201cVia evcc\u201d (above); evcc then charges by this plan.",
        ep_write_err="Writing failed", ep_mine="written by Plugwhen",
        tr_h="Planned trips", tr_none="No trips in the calendar.", tr_nocal="No calendar set. Trips can be entered in a calendar of Home Assistant (title e.g. \u201cLinz 200 km\u201d).",
        tr_km_event="from the event", tr_km_route="route via Waze, there and back", tr_km_route1="route via Waze, one way", tr_km_none="kilometres unknown, the learned day counts",
        tr_range="target at departure", tr_why_res="reserve", tr_why_km="trip + 15 %", tr_err="calendar not readable",
        v_overview="Overview", v_learning="Learning", v_details="Details", sun_h="Sun and learned values",
        rd_h="Ready to switch?", rd_trips="Trips learned", rd_cmp="Days with a comparison (learn mode)", rd_agree="Decided the same",
        rd_solar="Solar forecast checked", rd_days="days", rd_wd="weekdays", rd_est="expected from",
        rd_ready="Ready: Plugwhen decided like reality often enough. Without evcc the mode \u201cdirect\u201d (Plugwhen switches the wallbox) can be chosen now.",
        rd_wait="Not ready yet. Until then Plugwhen plans and warns, and in the mode \u201cvia evcc\u201d evcc charges by the plan.",
        rd_low="The decisions do not match reality well enough yet (tab Learning).",
        rd_wb="Wallbox control found", rd_wb_trip="the next-trip mode of the wallbox (time and energy, the sun stays first)",
        rd_wb_mode="mode change (grid in the planned windows, else the sun mode)", rd_wb_buttons="start and stop in the planned windows",
        rd_wb_none="none (the wallbox needs a charging mode or start/stop in Home Assistant)",
        rd_evcc_note="This car is linked to evcc: then evcc controls (mode “via evcc”). “Direct” is only for a car without an evcc link.",
        tr_how="**How to enter a trip:** tap the day in the calendar, title with destination and kilometres (\u201cLinz 200 km\u201d), "
               "start = departure time. Without kilometres the **location** counts (via Waze, if switched on), there and back; \u201cone way\u201d in the title = one direction. "
               "All-day events are ignored.",
        tr_setup="**Set up a calendar:** Settings \u2192 Devices & services \u2192 Add integration \u2192 \u201cLocal Calendar\u201d (e.g. \u201cTrips\u201d), "
                 "then choose it at the vehicle in Plugwhen under Reconfigure: \u201cCalendar with trips\u201d.",
        wd="['Mon','Tue','Wed','Thu','Fri','Sat','Sun']", day="Day", samples="days", km_typ="typical km", km_high="high km", drives="drives",
        dep="Departure", home="charged at home",
        week_note="Based on the last 8 days per weekday from the long-term statistics. \"high\" = 80th percentile.",
        learned_from="Learned from", hist_days="days of history", error="Error",
    ),
}


def _attrs(entity_id: str) -> str:
    """Jinja access to the attributes; an empty dict while the entity does not exist yet (right after a restart the dashboard
    draws before the sensors are back: 'None' has no attribute 'attributes' in the log, 18.11.2026)."""
    return "(states." + entity_id + ".attributes if states." + entity_id + " else {})"


def _chart(entity_id: str, attribute: str = "chart") -> str:
    """A markdown card body that shows the SVG chart of an attribute (nothing while it is missing)."""
    return ("{% set c = state_attr('" + entity_id + "', '" + attribute + "') %}"
            "{% if c %}![](data:image/svg+xml;utf8,{{ c | urlencode }}){% endif %}")


def _vehicle_section(ids: dict[str, str], t: dict[str, str], name: str, multi: bool, calendar: str | None = None,
                     evcc: bool = False) -> dict[str, list[dict[str, Any]]]:
    """Graphics first, one short line of text where a number needs words; settings stay on the dashboard."""
    need = _attrs(ids["need_charge"])
    status = (
        "{% set at = " + need + " %}"
        f"**{t['soc']}:** {{{{ at.soc if at.soc is not none else '–' }}}} % · "
        f"**{t['plugged']}:** {{{{ '{t['yes']}' if at.plugged else ('{t['no']}' if at.plugged is false else '{t['unknown']}') }}}} · "
        f"**{t['goal']}:** {{{{ at.get('must_soc') or at.target_soc }}}} % ({{{{ at.range_km }}}} km)"
        "{% set ah = at.get('ahead') %}{% if ah and ah.filling %}"
        f" · **{t['ahead_fill']}:** {{{{ ah.target_soc }}}} % ({{{{ ah.days }}}} {t['ahead_days']})"
        f"{{% if ah.sun_kwh > 0 %}} · {t['ahead_sun']} {{{{ ah.sun_kwh }}}} kWh{{% endif %}}"
        "{% endif %}"
        f"{{% if at.reachable is false %}}\n\n**{t['unreachable']}**{{% endif %}}"
        "{% set tip = state_attr('" + ids["charge_plan"] + "', 'tip') %}{% if tip %}\n\n**{{ tip }}**{% endif %}"
    )
    pot_line = (
        "{% set a = " + _attrs(ids["potential"]) + " %}"
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
        "{% set a = " + _attrs(ids["would_switch"]) + " %}{% set st = states('" + ids["would_switch"] + "') %}"
        "{% set rs = " + reasons + " %}{% set wn = " + would_names + " %}"
        f"{{% if st == 'off' %}}{t['lm_off']}{{% else %}}"
        f"**{t['would']}:** {{{{ wn.get(st, st) }}}} · {{{{ rs.get(a.reason, a.reason) if a.reason is defined else '' }}}}"
        f"{{% if a.until is defined and a.until %}} · {t['until_t']} {{{{ (a.until | as_datetime | as_local).strftime('%H:%M') }}}}{{% endif %}}{{% endif %}}"
        f"{{% if a.summary is defined and a.summary and a.summary.kwh_needless %}}\n\n{t['lm_needless']}: **{{{{ a.summary.kwh_needless }}}}** {t['lm_needless_in']}{{% endif %}}"
    )
    lc_id = ids["learning_check"]
    lc_line = (
        "{% set a = " + _attrs(lc_id) + " %}{% set st = states('" + lc_id + "') %}"
        f"{{% if st == 'too_little_data' %}}{t['lc_few_a']} {{{{ a.days }}}} {t['lc_few_b']}{{% else %}}"
        f"**{t['lc_km']}:** {{% if st == 'learning_helps' %}}{t['lc_km_helps']} {{{{ a.gain_points }}}} {t['lc_km_helps_b']}."
        f"{{% else %}}{t['lc_km_same']} ({{{{ a.coverage_reserve_pct }}}} → {{{{ a.coverage_learned_pct }}}} %): {t['lc_km_same_b']}.{{% endif %}}\n\n"
        f"**{t['lc_depl']}:** {{% if a.ready_early_pct is not none %}}{t['lc_dep_good']} {{{{ a.ready_early_pct }}}} {t['lc_dep_good_b']} {{{{ a.ready_median_pct }}}} %."
        f"{{% else %}}{t['lc_dep_none']}{{% endif %}}{{% endif %}}"
    )
    calib_line = (
        "{% set a = " + _attrs(ids["charge_plan"]) + " %}{% set n = " + need + " %}"
        "{% if a.solar_deduct_kw is not none %}"
        f"{t['cal_sun']}: {{% if a.solar_factor %}}{t['cal_factor']} {{{{ a.solar_factor }}}} ({t['cal_learned']}){{% else %}}{t['cal_unchecked']}{{% endif %}} · "
        f"{t['cal_deduct']} {{{{ a.solar_deduct_kw }}}} kW ({{{{ {{'learned': '{t['cal_src_learned']}', 'setting': '{t['cal_src_setting']}', 'default': '{t['cal_src_default']}'}}.get(a.solar_deduct_source, '') }}}}) · "
        f"{t['cal_loss']} {{{{ ((1 - (n.efficiency or 0.89)) * 100) | round(0) | int }}}} % ({{{{ '{t['cal_src_learned']}' if n.efficiency_learned else '{t['cal_src_default']}' }}}})"
        f"{{% if a.spread_floor_kw %}} · {t['cal_floor']} {{{{ a.spread_floor_kw }}}} kW{{% endif %}}{{% endif %}}"
    )
    hz_tpl = (
        "{% set wd = " + t["wd"] + " %}{% set a = " + _attrs(ids["charge_plan"]) + " %}{% set h = a.horizon %}"
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
        "{% for p in h.precharge if p.sun_from and p.sun_to and p.for_departure %}{% set sf = p.sun_from | as_datetime | as_local %}{% set st = p.sun_to | as_datetime | as_local %}{% set fd = p.for_departure | as_datetime | as_local %}"
        "\n\n**@PRE@:** {{ wd[sf.weekday()] }} {{ sf.strftime('%H:%M') }}–{{ st.strftime('%H:%M') }}: {{ p.kwh }} kWh (@REPL@ {{ wd[fd.weekday()] }} {{ fd.strftime('%H:%M') }})"
        "{% endfor %}"
        "{% endif %}"
    )
    for key, text in (("@COVERED@", t["hz_covered"]), ("@MUST@", t["hz_must"]), ("@ALL@", t["hz_all"]), ("@DAYS@", t["hz_days"]), ("@SUNOK@", t["hz_sun_ok"]), ("@NEXT@", t["hz_next"]), ("@FOR@", t["hz_for"]), ("@LATEST@", t["hz_latest"]), ("@AT@", t["hz_at"]), ("@PRE@", t["hz_pre"]), ("@REPL@", t["hz_replaces"])):
        hz_tpl = hz_tpl.replace(key, text)
    hb_id = ids["habit"]
    habit_line = (
        "{% set a = " + _attrs(hb_id) + " %}"
        f"{{% if a.status == 'ok' %}}{t['hb_a']} **{{{{ a.night_share_pct }}}}** {t['hb_b']} **{{{{ a.day_share_pct }}}}**"
        f" {t['hb_c']} **{{{{ a.weekend_share_pct }}}}** {t['hb_d']} **{{{{ a.weekdays_night_share_pct }}}} %**."
        f"{{% else %}}{t['hb_few']}{{% endif %}}"
    )
    src = (
        "{% set s = " + need + ".sources %}{% if s %}"
        "{% macro row(label, x) %}| " + "{{ label }}" + " | {% if x['from'] == 'sensor' %}" + t["src_sensor"] + " `{{ x.entity }}`"
        "{% elif x['from'] == 'evcc' %}" + t["src_from_evcc"] + "{% elif x['from'] == 'learned' %}" + t["src_learned"]
        + "{% else %}" + t["src_none"] + "{% endif %} |\n{% endmacro %}"
        "| | |\n|---|---|\n"
        "{{ row('" + t["src_soc"] + "', s.soc) }}{{ row('" + t["src_odo"] + "', s.odometer) }}"
        "{{ row('" + t["src_plug"] + "', s.plugged) }}{{ row('" + t["src_chg"] + "', s.charging) }}"
        "{{ row('" + t["src_wb"] + "', s.wallbox_energy) }}{{ row('" + t["src_dep"] + "', s.departure) }}"
        "| " + t["src_plan"] + " | {{ '" + t["src_exec"] + "' if s.plan == 'executed' else '" + t["src_rec"] + "' }} |\n"
        "{% if s.evcc %}| " + t["src_evcc"] + " | {{ '" + t["src_own"] + "' if s.evcc.address == 'own' else '" + t["src_guard_addr"] + "' }}"
        "{% if s.evcc.vehicle %} · {{ s.evcc.vehicle }}{% endif %} · "
        "{% if s.evcc.ok is none %}" + t["src_unused"] + "{% elif s.evcc.ok %}" + t["src_ok"] + "{% else %}" + t["src_fail"] + "{% endif %} |\n{% endif %}"
        "| " + t["src_set"] + " | {% set tf = s.taken_from %}{% if tf %}{{ tf | map('replace', 'guard', '" + t["src_guard"]
        + "') | join(', ') }}{% else %}" + t["src_manual"] + "{% endif %} |"
        "{% endif %}"
    )
    ep_reasons = "{" + ", ".join(f"'{k}': '{t['ep_r_' + k]}'" for k in ("not_needed", "unknown_soc", "no_departure", "no_target")) + "}"
    week_tpl = ("{% for p in @LIST@ %}{% if not loop.first %} · {% endif %}{% set d = p.weekdays %}"
                "{% if d | length > 2 and d[-1] - d[0] == d | length - 1 %}{{ wd[d[0]] }}–{{ wd[d[-1]] }}"
                "{% else %}{% for x in d %}{{ wd[x] }}{% if not loop.last %}, {% endif %}{% endfor %}{% endif %}"
                " {{ p.time }} {{ p.soc }} %{% endfor %}")
    ep = (
        "{% set wd = " + t["wd"] + " %}{% set e = state_attr('" + ids["charge_plan"] + "', 'evcc_plan') %}{% set rs = " + ep_reasons + " %}"
        "{% if e %}"
        "**" + t["ep_would"] + "** (" + t["ep_next"] + "): {% if e.would_write %}{% set w = e.would_write.time | as_datetime | as_local %}"
        "{{ e.would_write.soc }} % " + t["ep_until"] + " {{ wd[w.weekday()] }} {{ w.strftime('%d.%m. %H:%M') }}"
        "{% elif e.reason == 'covered' %}{% if e.lasts_until %}{% set lu = e.lasts_until | as_datetime | as_local %}" + t["ep_r_covered"]
        + " {{ wd[lu.weekday()] }} {{ lu.strftime('%d.%m.') }}{% else %}" + t["ep_r_covered_all"] + "{% endif %}"
        "{% else %}" + t["ep_nothing"] + " ({{ rs.get(e.reason, e.reason) }}){% endif %}\n\n"
        "**" + t["ep_now"] + ":** {% if e.current %}{% set c = e.current.time | as_datetime | as_local %}"
        "{{ e.current.soc }} % " + t["ep_until"] + " {{ wd[c.weekday()] }} {{ c.strftime('%H:%M') }}"
        "{% elif e.evcc_known %}" + t["ep_none"] + "{% if e.expired %} (" + t["ep_expired"] + "){% endif %}{% else %}" + t["ep_unreach"] + "{% endif %}"
        "{% if e.by_plugwhen %} · " + t["ep_mine"] + "{% elif e.same %} · " + t["ep_same"] + "{% elif e.own_plan %} · " + t["ep_own"] + "{% endif %}\n\n"
        "**" + t["ep_week"] + ":** {% if e.weekly %}" + week_tpl.replace("@LIST@", "e.weekly") + "{% else %}" + t["ep_week_none"] + "{% endif %}\n\n"
        "{% if e.evcc_known %}**" + t["ep_week_now"] + ":** {% if e.weekly_current %}" + week_tpl.replace("@LIST@", "e.weekly_current")
        + "{% else %}" + t["ep_none"] + "{% endif %}{% if e.weekly_same %} · " + t["ep_week_same"] + "{% endif %}\n\n{% endif %}"
        "{% if e.last_write and e.last_write.error %}**" + t["ep_write_err"] + ":** {{ e.last_write.error }}\n\n{% endif %}"
        "{% if e.written %}_" + t["ep_written"] + " " + t["ep_follow"] + "_{% elif e.write_enabled %}_" + t["ep_follow"] + "_"
        "{% else %}_" + t["ep_not_written"] + " " + t["ep_write_off"] + "_{% endif %}"
        "{% else %}" + t["ep_no_evcc"] + "{% endif %}"
    )
    trips_md = (
        "{% set wd = " + t["wd"] + " %}{% set a = " + _attrs(ids["charge_plan"]) + " %}"
        "{% if not a.trip_calendar %}" + t["tr_nocal"] + "{% elif a.trips_error %}" + t["tr_err"] + ": {{ a.trips_error }}"
        "{% elif not a.trips %}" + t["tr_none"] + "{% else %}"
        "{% for x in a.trips[:6] %}{% set d = x.departure | as_datetime | as_local %}"
        "- **{{ wd[d.weekday()] }} {{ d.strftime('%d.%m. %H:%M') }}** {{ x.title }}"
        "{% if x.km %} · {{ x.km | round(0) | int }} km ({{ {'event': '" + t["tr_km_event"] + "', 'route': ('" + t["tr_km_route1"]
        + "' if x.one_way else '" + t["tr_km_route"] + "')}.get(x.km_source, '') }}) · " + t["tr_range"] + " {{ x.range_km | round(0) | int }} km ({{ '" + t["tr_why_res"] + "' if (x.range_km | float(0)) > (x.km | float(0)) * 1.15 + 0.5 else '" + t["tr_why_km"] + "' }})"
        "{% else %} · " + t["tr_km_none"] + "{% endif %}\n{% endfor %}{% endif %}"
    )
    rd = (
        "{% set a = " + _attrs(ids["switch_ready"]) + " %}{% set checks = a.checks or [] %}"
        "{% macro row(checks, key, label, unit) %}{% set x = checks | selectattr('key', 'eq', key) | list | first %}"
        "{% if x %}{{ '✅' if x.ok else '⏳' }} {{ label }}: {{ x.value if x.value is not none else '–' }}"
        "{% if x.need %} / {{ x.need }}{% endif %} {{ unit }}\n\n{% endif %}{% endmacro %}"
        "{{ row(checks, 'trips', '" + t["rd_trips"] + "', '" + t["rd_wd"] + "') }}"
        "{{ row(checks, 'compare_days', '" + t["rd_cmp"] + "', '" + t["rd_days"] + "') }}"
        "{{ row(checks, 'agree', '" + t["rd_agree"] + "', '%') }}"
        "{{ row(checks, 'solar', '" + t["rd_solar"] + "', '" + t["rd_days"] + "') }}"
        "**" + t["rd_wb"] + ":** {{ {'trip': '" + t["rd_wb_trip"] + "', 'mode': '" + t["rd_wb_mode"] + "', 'buttons': '"
        + t["rd_wb_buttons"] + "'}.get(a.wallbox_control, '" + t["rd_wb_none"] + "') }}\n\n"
        + ("_" + t["rd_evcc_note"] + "_\n\n" if evcc else "")
        + "{% set cd = checks | selectattr('key', 'eq', 'compare_days') | list | first %}"
        "{% if states('" + ids["switch_ready"] + "') == 'ready' %}" + t["rd_ready"] + "{% else %}" + t["rd_wait"]
        + "{% if a.estimate %} " + t["rd_est"] + " **{{ (a.estimate | as_datetime).strftime('%d.%m.') }}**.{% elif cd and cd.ok %} "
        + t["rd_low"] + "{% endif %}{% endif %}"
    )
    head = (lambda h: f"{name} · {h}") if multi else (lambda h: h)
    overview = [
        {"type": "grid", "cards": [   # what matters now: ready for the next departure?
            {"type": "heading", "heading": head(t["next"]), "icon": "mdi:car-clock"},
            {"type": "tile", "entity": ids["readiness"], "name": t["ready"]},
            {"type": "tile", "entity": ids["departure"], "name": t["departure"]},
            {"type": "tile", "entity": ids["need_charge"], "name": t["charge"]},
            {"type": "markdown", "content": status},
            {"type": "heading", "heading": head(t["plan_h"]), "icon": "mdi:calendar-clock"},
            {"type": "markdown", "content": _chart(ids["charge_plan"])
             + "{% if state_attr('" + ids["charge_plan"] + "', 'wallbox_decides') %}\n\n_" + t["plan_wallbox"] + "_{% endif %}"},
            {"type": "heading", "heading": head(t["rd_h"]), "icon": "mdi:clipboard-check-outline"},
            {"type": "tile", "entity": ids["switch_ready"], "name": t["rd_h"]},
            {"type": "markdown", "content": rd},
        ]},
        {"type": "grid", "cards": [   # the messages to the phone, readable after they were swiped away (field 17.11.2026)
            {"type": "heading", "heading": head(t["msg_h"]), "icon": "mdi:message-text-clock-outline"},
            {"type": "markdown", "content": (
                "{% set m = state_attr('" + ids["notice_enabled"] + "', 'recent') or [] %}{% for x in m[:5] %}"
                "- **{{ (x.t | as_datetime | as_local).strftime('%d.%m. %H:%M') }}** {{ x.text }}\n"
                "{% else %}" + t["msg_none"] + "{% endfor %}")},
        ]},
        {"type": "grid", "cards": [
            {"type": "heading", "heading": head(t["tr_h"]), "icon": "mdi:calendar-month"},
            *([{"type": "calendar", "entities": [calendar], "initial_view": "listWeek"}] if calendar else []),
            {"type": "markdown", "content": trips_md},
            {"type": "markdown", "content": t["tr_how"] if calendar else t["tr_setup"]},
        ]},
        {"type": "grid", "cards": [
            {"type": "heading", "heading": head(t["hz_h"]), "icon": "mdi:calendar-arrow-right"},
            {"type": "markdown", "content": _chart(ids["charge_plan"], "horizon_chart")},
            {"type": "markdown", "content": hz_tpl},
        ]},
        {"type": "grid", "cards": [
            {"type": "heading", "heading": head(t["ep_h"]), "icon": "mdi:calendar-sync"},
            *([_setting(ids["mode"], t["mode_name"])] if evcc else []),
            {"type": "markdown", "content": ep},
        ]},
    ]
    learning = [
        {"type": "grid", "cards": [
            {"type": "heading", "heading": head(t["learn_h"]), "icon": "mdi:school-outline"},
            # 'would switch: off' only puzzled (field 17.11.2026): the tile appears while the trial run is on
            {"type": "conditional", "conditions": [{"condition": "state", "entity": ids["would_switch"], "state_not": "off"}],
             "card": {"type": "tile", "entity": ids["would_switch"], "name": t["would"]}},
            _setting(ids["mode"], t["mode_name"]),
            {"type": "markdown", "content": learn_line},
            # the chart is empty while the learn mode is off (for example in the mode 'direct'): no empty card then
            {"type": "conditional", "conditions": [{"condition": "state", "entity": ids["would_switch"], "state_not": "off"}],
             "card": {"type": "markdown", "content": _chart(ids["would_switch"])}},
        ]},
        {"type": "grid", "cards": [
            {"type": "heading", "heading": head(t["lc_h"]), "icon": "mdi:school-outline"},
            {"type": "tile", "entity": ids["learning_check"], "name": t["lc_tile"]},
            {"type": "markdown", "content": lc_line},
            {"type": "markdown", "content": _chart(lc_id)},
        ]},
        {"type": "grid", "cards": [
            {"type": "heading", "heading": head(t["hb_h"]), "icon": "mdi:chart-bar-stacked"},
            {"type": "tile", "entity": hb_id, "name": t["hb_tile"]},
            {"type": "markdown", "content": _chart(hb_id)},
            {"type": "markdown", "content": habit_line},
        ]},
        {"type": "grid", "cards": [
            {"type": "heading", "heading": head(t["plugs_h"]), "icon": "mdi:ev-plug-type2"},
            {"type": "markdown", "content": _chart(ids["readiness"], "plug_chart")},
            {"type": "markdown", "content": plugs_line},
        ]},
    ]
    details = [
        {"type": "grid", "cards": [
            {"type": "heading", "heading": head(t["pot_h"]), "icon": "mdi:chart-bell-curve-cumulative"},
            {"type": "tile", "entity": ids["potential"], "name": t["pot"]},
            {"type": "markdown", "content": _chart(ids["potential"])},
            {"type": "markdown", "content": pot_line},
        ]},
        {"type": "grid", "cards": [
            {"type": "heading", "heading": head(t["sun_h"]), "icon": "mdi:white-balance-sunny"},
            {"type": "markdown", "content": _chart(ids["charge_plan"], "sun_chart")},
            {"type": "markdown", "content": calib_line},
        ]},
        {"type": "grid", "cards": [
            {"type": "heading", "heading": head(t["src_h"]), "icon": "mdi:source-branch"},
            {"type": "markdown", "content": src},
        ]},
        {"type": "grid", "cards": [
            {"type": "heading", "heading": head(t["settings"]), "icon": "mdi:tune"},
            # one full-width tile per setting: the name gets the whole line (in an entities row it was cut off on a phone)
            _setting(ids["reserve_km"], t["reserve"]),
            _setting(ids["learn_km"], t["learn"]),
            _setting(ids["notice_enabled"], t["notice"]),
            *[_setting(ids[k], t[k], slider=k == "days_ahead") for k in ("days_ahead", "daily_cap") if ids.get(k)],
        ]},
    ]
    if ids.get("weekly_full"):   # once a week full (0.9.2)
        sw, tg = ids["weekly_full"], ids.get("weekly_target")
        names = "['" + "','".join(t["wf_days_names"].split(",")) + "']"
        status = ("{% if is_state('" + sw + "', 'on') %}{% set a = states['" + sw + "'].attributes %}"
                  "{% if a.active %}" + t["wf_active"].replace("{t}", "{{ states('" + str(tg) + "') | int(100) }}")
                  + "{% elif a.day %}" + t["wf_planned"].replace("{d}", "{{ " + names + "[as_datetime(a.day).weekday()] }}")
                  + "{% elif a.done %}" + t["wf_done"] + "{% else %}" + t["wf_none"] + "{% endif %}{% endif %}")
        # only the switch while it is off; the target, the days and the status appear when it is switched on (the ticked days
        # are kept all the same) - field test 16.11.2026: days ticked while nothing happens only puzzle
        cards: list[dict[str, Any]] = []
        if tg:
            cards.append(_setting(tg, t["wf_target"]))
        day_ids = [ids.get(f"weekly_day_{d}") for d in range(7)]
        if all(day_ids):   # the day bar: seven buttons Mo..So, tap to tick
            short = t["wf_days_short"].split(",")
            cards += [
                {"type": "markdown", "content": "**" + t["wf_days"] + "**  \n" + t["wf_days_hint"]},
                {"type": "grid", "columns": 7, "square": False, "cards": [
                    # a ticked day: green check; not ticked: grey empty circle (the icon comes from the switch)
                    {"type": "tile", "entity": eid, "name": short[d], "color": "green", "hide_state": True,
                     "vertical": True, "tap_action": {"action": "toggle"}, "icon_tap_action": {"action": "toggle"},
                     "hold_action": {"action": "more-info"}}
                    for d, eid in enumerate(day_ids)]},
            ]
        details[-1]["cards"] += [
            _setting(sw, t["wf"]),
            {"type": "conditional", "conditions": [{"condition": "state", "entity": sw, "state": "on"}],
             "card": {"type": "vertical-stack", "cards": cards + [{"type": "markdown", "content": status}]}},
        ]
    return {"overview": overview, "learning": learning, "details": details}


def _setting(entity_id: str, name: str, slider: bool = False) -> dict[str, Any]:
    """A setting as a full-width tile: the name on its own line, the value below it. A number gets +/- buttons (or a slider),
    a switch is toggled with a tap."""
    tile: dict[str, Any] = {"type": "tile", "entity": entity_id, "name": name, "grid_options": {"columns": "full"}}
    if entity_id.startswith("number."):
        tile.update(features=[{"type": "numeric-input", "style": "slider" if slider else "buttons"}], features_position="bottom")
    elif entity_id.startswith("select."):
        tile.update(features=[{"type": "select-options"}], features_position="bottom")
    else:
        tile.update(tap_action={"action": "toggle"}, icon_tap_action={"action": "toggle"}, hold_action={"action": "more-info"})
    return tile


def _wait_for_sensors(node: Any) -> None:
    """A markdown card that reads attributes is drawn only once its sensors exist: right after a restart the dashboard draws
    before the sensors are back, and a value read from the empty attributes wrote a template error to the log (18.11.2026)."""
    import re

    if isinstance(node, list):
        for x in node:
            _wait_for_sensors(x)
    elif isinstance(node, dict):
        content = node.get("content")
        if node.get("type") == "markdown" and isinstance(content, str):
            ids = sorted(set(re.findall(r"\(states\.([a-z_]+\.[a-z0-9_]+)\.attributes if states\.", content)))
            if ids:
                node["content"] = "{% if " + " and ".join(f"states.{i}" for i in ids) + " %}" + content + "{% endif %}"
        for x in node.values():
            if isinstance(x, (list, dict)):
                _wait_for_sensors(x)


def build_views(vehicles: list[dict[str, Any]], language: str | None, currency: str | None = None,
                main_ids: dict[str, str] | None = None, waechter: bool | None = None) -> list[dict[str, Any]]:
    """Three tabs: Overview (ready for the next departure, plan, trips, look-ahead, plan for evcc), Learning, Details.
    `waechter` False (the peak guard is not installed) adds the card 'Goes well with' at the end of the overview."""
    t = dict(TEXT["de"] if (language or "").lower().startswith("de") else TEXT["en"])
    cur = {"EUR": "€", "USD": "$", "GBP": "£", "CHF": "CHF"}.get(currency or "EUR", currency or "€")
    t = {k: v.replace("{cur}", cur) for k, v in t.items()}
    t["cur"] = cur
    tabs: dict[str, list[dict[str, Any]]] = {"overview": [], "learning": [], "details": []}
    for v in vehicles:
        parts = _vehicle_section(v["ids"], t, v["name"], len(vehicles) > 1, v.get("calendar"), bool(v.get("evcc")))
        for key in tabs:
            tabs[key] += parts[key]
    if main_ids and all(k in main_ids for k in ("feedback_text", "feedback_send", "share_usage")):
        tabs["details"].append(feedback_section(main_ids, language))
    if main_ids and "share_usage" in main_ids:   # quiet, only while sharing is off: what the fleet values would bring
        tabs["learning"].insert(0, fleet_off_section(main_ids["share_usage"], language))
    if waechter is False:   # only when we know it is missing; it disappears with "Create the dashboard" after installing it
        tabs["overview"].append(waechter_section(language))
    for tab in tabs.values():
        _wait_for_sensors(tab)
    return [
        {"title": t["v_overview"], "path": "plugwhen", "icon": "mdi:ev-plug-type2", "type": "sections", "max_columns": 2, "sections": tabs["overview"]},
        {"title": t["v_learning"], "path": "lernen", "icon": "mdi:school-outline", "type": "sections", "max_columns": 2, "sections": tabs["learning"]},
        {"title": t["v_details"], "path": "details", "icon": "mdi:tune-variant", "type": "sections", "max_columns": 2, "sections": tabs["details"]},
    ]


FEEDBACK_TEXT = {'de': ('Rückmeldung', 'Etwas funktioniert nicht, fehlt oder gefällt Ihnen? Text eingeben, Enter, dann bei *Rückmeldung senden* auf *Drücken*. Sie geht an den Autor; mitgesendet wird nur eine Übersicht der Einrichtung, keine Namen oder Messwerte. Läuft etwas nicht, *Fehlerbericht senden* drücken (Text optional): Er hilft beim Finden des Fehlers, ohne Namen oder Adressen; danach steht in der Glocke, was gesendet wurde.', 'Text', 'Senden', 'Anonyme Daten teilen', 'Fehlerbericht senden'), 'en': ('Feedback', 'Something does not work, is missing or you like it? Type it, press Enter, then *Press* at *Send feedback*. It goes to the author; only an overview of the setup goes along, no names or measurements. If something does not work, press *Send bug report* (text optional): it helps to find the error, without names or addresses; afterwards the bell shows what was sent.', 'Text', 'Send', 'Share anonymous data', 'Send bug report')}


FLEET_OFF_TEXT = {
    "de": ("**Flottenwerte sind aus.** Plugwhen lernt dann nur von Ihrem Auto, das dauert ein paar Wochen.\n\n"
           "Mit *Anonyme Daten teilen* startet es mit dem Verbrauch vieler gleicher Autos, bei Kälte und Wärme, schon ab dem ersten Tag.",
           "Anonyme Daten teilen"),
    "en": ("**Fleet values are off.** Plugwhen then learns from your car alone, which takes a few weeks.\n\n"
           "With *Share anonymous data* it starts with the consumption of many cars of the same model, in cold and warm weather, "
           "from the first day.", "Share anonymous data"),
}


WAECHTER_LINK = "https://my.home-assistant.io/redirect/hacs_repository/?owner=mobilewhatelse&repository=viertelstunden-waechter&category=integration"
WAECHTER_TEXT = {
    "de": ("Passt dazu: Viertelstunden-Wächter",
           "Der **Viertelstunden-Wächter** hält die Viertelstunden-Spitze Ihres Hauses unter einer Grenze: Er schaltet Wallbox, "
           "Wärmepumpe oder Boiler kurz zurück, bevor eine teure Spitze entsteht. Plugwhen findet ihn automatisch und plant das "
           "Laden dann unter dieser Grenze.\n\n"
           f"Kostenlos im [HACS-Marketplace]({WAECHTER_LINK}) · mehr auf [aiwhatelse.eu/spitzenwaechter](https://www.aiwhatelse.eu/spitzenwaechter/)\n\n"
           "*Nach der Installation: Dashboard neu erstellen, dann verschwindet diese Karte.*"),
    "en": ("Goes well with: Viertelstunden-Wächter",
           "The **Viertelstunden-Wächter** (quarter-hour peak guard) keeps the quarter-hour peak of your house below a limit: it "
           "turns the wallbox, heat pump or water heater down for a moment before an expensive peak builds up. Plugwhen finds it "
           "automatically and then plans the charging below that limit.\n\n"
           f"Free in the [HACS marketplace]({WAECHTER_LINK}) · more at [aiwhatelse.eu/spitzenwaechter](https://www.aiwhatelse.eu/spitzenwaechter/?lang=en)\n\n"
           "*After installing it: create the dashboard again, then this card disappears.*"),
}


def waechter_section(lang: str | None) -> dict:
    """A quiet card at the end of the overview, only while the quarter-hour peak guard is not installed."""
    head, text = WAECHTER_TEXT["de" if str(lang or "").lower().startswith("de") else "en"]
    return {"type": "grid", "cards": [
        {"type": "heading", "heading": head, "icon": "mdi:shield-check-outline"},
        {"type": "markdown", "content": text}]}


def fleet_off_section(share_id: str, lang: str | None) -> dict:
    """A quiet card, shown only while sharing is off (no pop-up, no question): what the fleet values would bring."""
    text, name = FLEET_OFF_TEXT["de" if str(lang or "").lower().startswith("de") else "en"]
    return {"type": "grid", "cards": [{
        "type": "conditional", "conditions": [{"condition": "state", "entity": share_id, "state": "off"}],
        "card": {"type": "vertical-stack", "cards": [
            {"type": "markdown", "content": text},
            {"type": "entities", "show_header_toggle": False, "entities": [{"entity": share_id, "name": name}]}]}}]}


def feedback_section(ids: dict[str, str], lang: str | None) -> dict:
    """The card 'Feedback': text field, button and the switch of the voluntary usage statistics."""
    head, text, f_text, f_send, f_share, f_report = FEEDBACK_TEXT["de" if str(lang or "").lower().startswith("de") else "en"]
    report = [{"entity": ids["feedback_report"], "name": f_report}] if ids.get("feedback_report") else []
    return {"type": "grid", "cards": [
        {"type": "heading", "heading": head, "icon": "mdi:message-text-outline"},
        {"type": "markdown", "content": text},
        {"type": "entities", "show_header_toggle": False, "entities": [
            {"entity": ids["feedback_text"], "name": f_text}, {"entity": ids["feedback_send"], "name": f_send}, *report,
            {"entity": ids["share_usage"], "name": f_share}]},
    ]}
