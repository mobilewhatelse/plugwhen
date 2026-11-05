"""Plugwhen and the quarter-hour peak guard in ONE fresh Home Assistant: they find each other by choosing the integration.

Run (from the repository root, the guard is expected next to it in ../viertelstunden-waechter):
  see tests/install/README.md, section "Both integrations". Takes a few minutes.
"""
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import itest as it  # noqa: E402  (the helpers of the single test)

it.BASE = "http://localhost:18125"
it.CONTAINER = "both-test"


def log(ok, name, detail=""):
    it.log(ok, name, detail)


def option_suggestion(entry_id, field):
    """The value the options form suggests for a field (None if nothing)."""
    s, d = it.api("POST", "/api/config/config_entries/options/flow", {"handler": entry_id})
    suggested = None
    for f in d.get("data_schema", []):
        if f.get("name") == field:
            suggested = (f.get("description") or {}).get("suggested_value")
    it.api("DELETE", f"/api/config/config_entries/options/flow/{d.get('flow_id')}")
    return suggested


def main():
    if not it.wait_ready():
        log(False, "Home Assistant starts")
        return
    ok, msg = it.onboard()
    log(ok, "Home Assistant starts and the test user exists", msg)
    if not ok:
        return
    it.wait_for(lambda: it.state("sensor.auto_ladestand") and it.state("sensor.auto_ladestand")["state"] not in ("unknown", "unavailable"), 120)

    # ---------- set up both ----------
    pw, err = it.flow_finish("/api/config/config_entries/flow", {"handler": "plugwhen", "show_advanced_options": False}, {})
    log(pw is not None, "Plugwhen is set up", err)
    wa, err = it.flow_finish("/api/config/config_entries/flow", {"handler": "viertelstunden_waechter", "show_advanced_options": False},
                             {"name": "Viertelstunden-Wächter", "grid_power": "sensor.netzbezug", "limit_kw": 10.0, "margin_kw": 0.5})
    log(wa is not None, "the quarter-hour peak guard is set up", err)
    if not (pw and wa):
        return
    pw_id = it.api("GET", "/api/config/config_entries/entry?domain=plugwhen")[1][0]["entry_id"]
    wa_id = it.api("GET", "/api/config/config_entries/entry?domain=viertelstunden_waechter")[1][0]["entry_id"]
    car = {"name": "Testauto", "odometer_entity": "sensor.auto_kilometerstand", "soc_entity": "sensor.auto_ladestand",
           "capacity_kwh": 60, "reserve_km": 100, "consumption_kwh_100": 20, "departure_entity": "input_datetime.abfahrt",
           "charge_kw_max": 11, "charge_kw_min": 1.4, "plugged_entity": "binary_sensor.auto_stecker"}
    res, err = it.flow_finish("/api/config/config_entries/subentries/flow", {"handler": [pw_id, "vehicle"]}, car)
    log(res is not None, "a vehicle is added to Plugwhen", err)
    it.svc("input_number", "set_value", {"entity_id": "input_number.auto_soc", "value": 10})

    plan = it.wait_for(lambda: it.find("sensor", "testauto_charge_plan"), 60)
    log(bool(plan), "Plugwhen has a charge plan sensor")
    if not plan:
        return
    pid = plan["entity_id"]
    ok = it.wait_for(lambda: it.state(pid)["state"] == "planned", 60)
    log(bool(ok), "the plan is made (battery low)", it.state(pid)["state"])

    # ---------- the options suggest each other ----------
    log(option_suggestion(pw_id, "waechter_entry") == wa_id, "Plugwhen suggests the installed quarter-hour peak guard", str(option_suggestion(pw_id, "waechter_entry")))
    log(option_suggestion(wa_id, "planner_entry") == pw_id, "the guard suggests the installed Plugwhen", str(option_suggestion(wa_id, "planner_entry")))

    # ---------- Plugwhen chooses the guard ----------
    s, d = it.api("POST", "/api/config/config_entries/options/flow", {"handler": pw_id})
    s2, d2 = it.api("POST", f"/api/config/config_entries/options/flow/{d['flow_id']}", {"waechter_entry": wa_id})
    log(s == 200 and d2.get("type") == "create_entry", "Plugwhen: the guard is chosen (no entities picked)", f"{d.get('type')} / {d2.get('type')}")

    forecast = None
    for e in it.states_like("viertelstunden_wachter"):
        if e["entity_id"].startswith("sensor.") and "hours" in e["attributes"] and "target_kw" in e["attributes"]:
            forecast = e["entity_id"]
    log(bool(forecast), "the guard has its forecast sensor", str(forecast))

    ok = it.wait_for(lambda: (it.state(pid) or {}).get("attributes", {}).get("load_entity") == forecast, 90)
    log(bool(ok), "Plugwhen found the forecast sensor of the guard by itself", str((it.state(pid) or {}).get("attributes", {}).get("load_entity")))

    # ---------- the guard chooses Plugwhen ----------
    s, d = it.api("POST", "/api/config/config_entries/options/flow", {"handler": wa_id})
    s2, d2 = it.api("POST", f"/api/config/config_entries/options/flow/{d['flow_id']}",
                    {"grid_power": "sensor.netzbezug", "mains_voltage": 230, "startup_mode": "restore", "planner_entry": pw_id})
    log(s == 200 and d2.get("type") == "create_entry", "the guard: Plugwhen is chosen (no entities picked)", f"{d.get('type')} / {d2.get('type')}")

    fc = "sensor.viertelstunden_wachter_typischer_bezug_jetzt_prognose"
    fc_entity = None
    for e in it.states_like("viertelstunden_wachter"):
        if e["entity_id"].startswith("sensor.") and "car_plan" in e["attributes"]:
            fc_entity = e["entity_id"]
    ok = it.wait_for(lambda: (it.state(fc_entity) or {}).get("attributes", {}).get("car_plan", {}).get("used") is True, 180) if fc_entity else None
    cp = (it.state(fc_entity) or {}).get("attributes", {}).get("car_plan", {}) if fc_entity else {}
    log(bool(ok) and cp.get("windows", 0) >= 1, "the guard reads the plan of Plugwhen (windows found by itself)", json.dumps(cp))

    # ---------- a second vehicle is found without any setting ----------
    car2 = dict(car, name="Zweitauto")
    res, err = it.flow_finish("/api/config/config_entries/subentries/flow", {"handler": [pw_id, "vehicle"]}, car2)
    log(res is not None, "a second vehicle is added to Plugwhen", err)
    time.sleep(20)
    ok = it.wait_for(lambda: (it.state(fc_entity) or {}).get("attributes", {}).get("car_plan", {}).get("configured") == 2, 420)  # the forecast is recomputed every 5 minutes
    log(bool(ok), "the guard counts both vehicles (found automatically, nothing set)",
        str((it.state(fc_entity) or {}).get("attributes", {}).get("car_plan", {})))

    logs = subprocess.run(["docker", "logs", it.CONTAINER], capture_output=True, text=True).stdout
    errs = [ln for ln in logs.splitlines() if ("plugwhen" in ln.lower() or "viertelstunden" in ln.lower()) and (" ERROR " in ln or "Traceback" in ln)]
    log(not errs, "no errors of either integration in the log", "; ".join(errs[:3]))


if __name__ == "__main__":
    try:
        main()
    finally:
        fails = [ln for ok, ln in it.REPORT if not ok]
        print(f"\n{len(it.REPORT) - len(fails)} of {len(it.REPORT)} checks passed")
        with open("tests/install/report_both.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(ln for _, ln in it.REPORT) + "\n")
        sys.exit(1 if fails else 0)
