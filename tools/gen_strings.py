"""Writes strings.json and translations/{en,de}.json of the integration (one source of truth for both languages)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"

EN = dict(
    f_name="Name", f_odo="Odometer", f_soc="State of charge", f_cap="Battery capacity", f_res="Reserve", f_cons="Consumption (until learned)",
    f_max="Wallbox power (maximum)", f_min="Wallbox power (minimum)", f_plug="Plugged in (optional)", f_chg="Charging (optional)",
    f_wb="Wallbox energy counter (optional)", f_dep="Departure (optional)", f_notify="Notify service (optional)", f_hour="Warn from this hour",
    d_odo="Sensor with the odometer (km or miles). It needs long-term statistics (a state class), that is where Plugwhen learns from.",
    d_soc="Sensor with the state of charge of the battery in percent.",
    d_cap="Usable battery capacity.",
    d_res="The car should leave with at least this range. You can change it later with the Reserve entity.",
    d_cons="Used until the car's own consumption is known (typical: 15 to 25 kWh per 100 km).",
    d_max="What the wallbox can deliver at most. The plan never plans more.",
    d_min="Lowest charging power of the wallbox (1 phase, 6 A is about 1.4 kW).",
    d_plug="On when the car is plugged in. Needed for the warning \"plug in\".",
    d_chg="On while the car is charging. No warning is sent while it charges.",
    d_wb="Energy counter of the wallbox (Wh or kWh). It tells charging at home from charging away.",
    d_dep="A time or date-time entity (for example a helper). If set, it replaces the departure Plugwhen has learned.",
    d_notify="One or more notify services, separated by commas, for example notify.mobile_app_phone, notify.mobile_app_tablet. Used for the warning that the car will not be ready. Leave empty for none.",
    d_hour="The warning is sent from this hour of the evening on, once per departure.",
    v_title="Vehicle", v_desc="Plugwhen learns from the history of this car how far it drives, when it leaves and where it is charged.",
    c_desc="Works out when to plug in so that the car is ready when you leave. Vehicles are added afterwards on the integration page.",
    c_single="Plugwhen is already set up.", entry_type="Vehicle", add="Add vehicle", reconf="Reconfigure vehicle",
    e_same="Odometer and state of charge must be different sensors.", e_minmax="The minimum power is above the maximum.",
    e_notify="Enter each service as domain.name, separated by commas, for example notify.mobile_app_phone.", ok="The vehicle was updated.",
    o_title="Connections", o_desc="Optional. Plugwhen also works alone. Connect it to what you have: the load forecast of the quarter-hour peak guard (keeps the car's charging under the peak target) and a sensor of the availability interface (when power is cheap or free).",
    o_load="Load forecast", o_avail="Availability of power",
    od_load="A sensor with the attributes hours (t, typical, high) and target_kw, for example the forecast sensor of the quarter-hour peak guard. Suggested automatically if it is installed.",
    od_avail="A sensor with the attributes schema (1), valid_until and forecast (a list of start, end, kw), for example from an energy community or a solar forecast.",
    s_charge="Energy to charge", s_range="Range needed", s_soc2="Target state of charge", s_dep2="Expected departure", s_week="Learned days",
    s_plan="Charge plan", s_ready="Ready for departure",
    plan_planned="Planned", plan_not_needed="Not needed", plan_infeasible="Target not reachable", plan_no_departure="No departure", plan_unknown="State of charge unknown",
    r_ready="Ready", r_plug="Plug in", r_low="Too low", r_late="Too late", r_unreach="Not reachable", r_unknown="Unknown",
    sw_learn="Learn kilometres per weekday", sw_notice="Warn when the car will not be ready", n_res="Reserve",
)
DE = dict(
    f_name="Name", f_odo="Kilometerstand", f_soc="Ladestand", f_cap="Batteriekapazität", f_res="Reserve", f_cons="Verbrauch (bis gelernt)",
    f_max="Wallbox-Leistung (höchstens)", f_min="Wallbox-Leistung (mindestens)", f_plug="Angesteckt (optional)", f_chg="Lädt (optional)",
    f_wb="Energiezähler der Wallbox (optional)", f_dep="Abfahrt (optional)", f_notify="Benachrichtigungsdienst (optional)", f_hour="Warnen ab Uhrzeit",
    d_odo="Sensor mit dem Kilometerstand (km oder Meilen). Er braucht Langzeitstatistik (eine Zustandsklasse), daraus lernt Plugwhen.",
    d_soc="Sensor mit dem Ladestand der Batterie in Prozent.",
    d_cap="Nutzbare Batteriekapazität.",
    d_res="Das Auto soll mit mindestens dieser Reichweite losfahren. Später mit der Entität Reserve änderbar.",
    d_cons="Gilt, bis der eigene Verbrauch des Autos bekannt ist (typisch 15 bis 25 kWh je 100 km).",
    d_max="Was die Wallbox höchstens liefern kann. Der Plan plant nie mehr.",
    d_min="Kleinste Ladeleistung der Wallbox (1 Phase, 6 A sind etwa 1,4 kW).",
    d_plug="An, wenn das Auto angesteckt ist. Nötig für die Warnung „bitte anstecken“.",
    d_chg="An, solange das Auto lädt. Währenddessen wird nicht gewarnt.",
    d_wb="Energiezähler der Wallbox (Wh oder kWh). Er unterscheidet Laden zu Hause von Laden unterwegs.",
    d_dep="Eine Zeit- oder Datum-Zeit-Entität (zum Beispiel ein Helfer). Wenn gesetzt, ersetzt sie die gelernte Abfahrt.",
    d_notify="Ein oder mehrere Benachrichtigungsdienste, durch Komma getrennt, zum Beispiel notify.mobile_app_handy, notify.mobile_app_tablet. Für die Warnung, dass das Auto nicht bereit sein wird. Leer lassen für keine.",
    d_hour="Ab dieser Abendstunde wird gewarnt, einmal je Abfahrt.",
    v_title="Fahrzeug", v_desc="Plugwhen lernt aus dem Verlauf dieses Autos, wie weit es fährt, wann es losfährt und wo es geladen wird.",
    c_desc="Berechnet, wann man anstecken soll, damit das Auto bei der Abfahrt bereit ist. Fahrzeuge fügen Sie danach auf der Integrationsseite hinzu.",
    c_single="Plugwhen ist schon eingerichtet.", entry_type="Fahrzeug", add="Fahrzeug hinzufügen", reconf="Fahrzeug ändern",
    e_same="Kilometerstand und Ladestand müssen verschiedene Sensoren sein.", e_minmax="Die kleinste Leistung liegt über der größten.",
    e_notify="Jeden Dienst als domain.name angeben, durch Komma getrennt, zum Beispiel notify.mobile_app_handy.", ok="Das Fahrzeug wurde aktualisiert.",
    o_title="Verbindungen", o_desc="Optional. Plugwhen funktioniert auch allein. Verbinden Sie es mit dem, was Sie haben: die Last-Prognose des Viertelstunden-Wächters (hält das Laden des Autos unter der Spitzengrenze) und ein Sensor der Verfügbarkeits-Schnittstelle (wann Strom günstig oder gratis ist).",
    o_load="Last-Prognose", o_avail="Verfügbarkeit von Strom",
    od_load="Ein Sensor mit den Attributen hours (t, typical, high) und target_kw, zum Beispiel der Prognose-Sensor des Viertelstunden-Wächters. Wird automatisch vorgeschlagen, wenn er installiert ist.",
    od_avail="Ein Sensor mit den Attributen schema (1), valid_until und forecast (Liste aus start, end, kw), zum Beispiel von einer Energiegemeinschaft oder einer Solarprognose.",
    s_charge="Zu ladende Energie", s_range="Nötige Reichweite", s_soc2="Ziel-Ladestand", s_dep2="Erwartete Abfahrt", s_week="Gelernte Tage",
    s_plan="Ladeplan", s_ready="Bereit zur Abfahrt",
    plan_planned="Geplant", plan_not_needed="Nicht nötig", plan_infeasible="Ziel nicht erreichbar", plan_no_departure="Keine Abfahrt", plan_unknown="Ladestand unbekannt",
    r_ready="Bereit", r_plug="Bitte anstecken", r_low="Zu niedrig", r_late="Zu spät", r_unreach="Nicht erreichbar", r_unknown="Unbekannt",
    sw_learn="Kilometer je Wochentag lernen", sw_notice="Warnen, wenn das Auto nicht bereit sein wird", n_res="Reserve",
)


def build(L):
    data = {"name": L["f_name"], "odometer_entity": L["f_odo"], "soc_entity": L["f_soc"], "capacity_kwh": L["f_cap"],
            "reserve_km": L["f_res"], "consumption_kwh_100": L["f_cons"], "charge_kw_max": L["f_max"], "charge_kw_min": L["f_min"],
            "plugged_entity": L["f_plug"], "charging_entity": L["f_chg"], "wallbox_energy_entity": L["f_wb"],
            "departure_entity": L["f_dep"], "notify_service": L["f_notify"], "notify_hour": L["f_hour"]}
    desc = {"odometer_entity": L["d_odo"], "soc_entity": L["d_soc"], "capacity_kwh": L["d_cap"], "reserve_km": L["d_res"],
            "consumption_kwh_100": L["d_cons"], "charge_kw_max": L["d_max"], "charge_kw_min": L["d_min"], "plugged_entity": L["d_plug"],
            "charging_entity": L["d_chg"], "wallbox_energy_entity": L["d_wb"], "departure_entity": L["d_dep"],
            "notify_service": L["d_notify"], "notify_hour": L["d_hour"]}
    step = {"title": L["v_title"], "description": L["v_desc"], "data": data, "data_description": desc}
    return {
        "config": {"step": {"user": {"title": "Plugwhen", "description": L["c_desc"]}}, "abort": {"single_instance_allowed": L["c_single"]}},
        "options": {"step": {"init": {
            "title": L["o_title"], "description": L["o_desc"],
            "data": {"load_entity": L["o_load"], "availability_entity": L["o_avail"]},
            "data_description": {"load_entity": L["od_load"], "availability_entity": L["od_avail"]},
        }}},
        "config_subentries": {"vehicle": {
            "entry_type": L["entry_type"], "initiate_flow": {"user": L["add"], "reconfigure": L["reconf"]},
            "step": {"user": step, "reconfigure": step},
            "error": {"same_entity": L["e_same"], "min_above_max": L["e_minmax"], "notify_format": L["e_notify"]},
            "abort": {"reconfigure_successful": L["ok"]},
        }},
        "entity": {
            "sensor": {
                "need_charge": {"name": L["s_charge"]}, "need_range": {"name": L["s_range"]}, "target_soc": {"name": L["s_soc2"]},
                "departure": {"name": L["s_dep2"]}, "week_plan": {"name": L["s_week"]},
                "charge_plan": {"name": L["s_plan"], "state": {"planned": L["plan_planned"], "not_needed": L["plan_not_needed"],
                                                               "infeasible": L["plan_infeasible"], "no_departure": L["plan_no_departure"],
                                                               "unknown_soc": L["plan_unknown"]}},
                "readiness": {"name": L["s_ready"], "state": {"ready": L["r_ready"], "plug_in": L["r_plug"], "low": L["r_low"],
                                                              "too_late": L["r_late"], "not_reachable": L["r_unreach"], "unknown": L["r_unknown"]}},
            },
            "switch": {"learn_km": {"name": L["sw_learn"]}, "notice_enabled": {"name": L["sw_notice"]}},
            "number": {"reserve_km": {"name": L["n_res"]}},
        },
    }


for path, L in (("strings.json", EN), ("translations/en.json", EN), ("translations/de.json", DE)):
    (ROOT / path).write_text(json.dumps(build(L), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("ok")
