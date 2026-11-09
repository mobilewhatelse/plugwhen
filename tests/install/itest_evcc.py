"""Installation test: Plugwhen with evcc and WITHOUT the peak guard (fresh Home Assistant in Docker, demo evcc on the host).

Needs: `docker run -d --name evcc-test -p 17070:7070 evcc/evcc:latest evcc --demo` and the Home Assistant container
`pw-evcc-test` on port 18127 with `--add-host=host.docker.internal:host-gateway` (config: tests/install/config).
evcc is only read. Takes about two minutes.
"""
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import itest as it  # noqa: E402  (the helpers of the single test)

it.BASE = "http://localhost:18127"
it.CONTAINER = "pw-evcc-test"
EVCC = "http://host.docker.internal:17070"
log = it.log


def form_values(d):
    out = {}
    for f in (d or {}).get("data_schema", []) if isinstance(d, dict) else []:
        v = f.get("default", (f.get("description") or {}).get("suggested_value"))
        if v is not None:
            out[f["name"]] = v
    return out


def main():
    if not it.wait_ready():
        log(False, "Home Assistant starts")
        return
    ok, msg = it.onboard()
    log(ok, "Home Assistant starts and the test user exists", msg)
    if not ok:
        return
    it.wait_for(lambda: it.state("sensor.auto_ladestand") and it.state("sensor.auto_ladestand")["state"] not in ("unknown", "unavailable"), 120)

    pw, err = it.flow_finish("/api/config/config_entries/flow", {"handler": "plugwhen", "show_advanced_options": False}, {})
    log(pw is not None, "Plugwhen is set up (no guard installed)", err)
    if not pw:
        return
    pw_id = it.api("GET", "/api/config/config_entries/entry?domain=plugwhen")[1][0]["entry_id"]

    # ---------- without an evcc address the vehicle form is empty and has no evcc field ----------
    s, d = it.api("POST", "/api/config/config_entries/subentries/flow", {"handler": [pw_id, "vehicle"]})
    vals, names = form_values(d), [f["name"] for f in (d or {}).get("data_schema", [])]
    log(s == 200 and "name" not in vals and "evcc_vehicle" not in names, "without evcc: empty vehicle form, no evcc field",
        json.dumps({"name": vals.get("name"), "evcc_field": "evcc_vehicle" in names}))
    it.api("DELETE", f"/api/config/config_entries/subentries/flow/{d.get('flow_id')}")

    # ---------- the options: a wrong address is refused, the right one accepted ----------
    s, d = it.api("POST", "/api/config/config_entries/options/flow", {"handler": pw_id})
    s2, d2 = it.api("POST", f"/api/config/config_entries/options/flow/{d['flow_id']}", {"use_solar_forecast": True, "evcc_url": "http://host.docker.internal:1"})
    log(s2 == 200 and (d2.get("errors") or {}).get("evcc_url") == "evcc_unreachable", "an evcc address that does not answer is refused", str(d2.get("errors")))
    s3, d3 = it.api("POST", f"/api/config/config_entries/options/flow/{d['flow_id']}", {"use_solar_forecast": True, "evcc_url": EVCC})
    log(s3 == 200 and d3.get("type") == "create_entry", "the address of evcc is saved in the options", f"{d3.get('type')} {d3.get('errors')}")
    time.sleep(8)   # the entry reloads

    # ---------- adding a vehicle: filled in from evcc ----------
    s, d = it.api("POST", "/api/config/config_entries/subentries/flow", {"handler": [pw_id, "vehicle"]})
    vals, names = form_values(d), [f["name"] for f in (d or {}).get("data_schema", [])]
    note = ((d or {}).get("description_placeholders") or {}).get("taken_over", "")
    log(s == 200 and vals.get("name") == "blue e-Golf" and vals.get("capacity_kwh") == 44 and vals.get("evcc_vehicle") == "vehicle_1"
        and vals.get("charge_kw_max") == 11.0 and "evcc_vehicle" in names and "e-Golf" in note,
        "the vehicle form is filled in from evcc (name, capacity, power of the loadpoint, evcc vehicle)",
        json.dumps({k: vals.get(k) for k in ("name", "capacity_kwh", "charge_kw_min", "charge_kw_max", "evcc_vehicle")}) + " | " + note)
    car = {"name": vals.get("name", "blue e-Golf"), "odometer_entity": "sensor.auto_kilometerstand", "soc_entity": "sensor.auto_ladestand",
           "capacity_kwh": 44, "reserve_km": 100, "consumption_kwh_100": 20, "charge_kw_max": 11, "charge_kw_min": 4.1, "evcc_vehicle": "vehicle_1"}
    s, d = it.api("POST", f"/api/config/config_entries/subentries/flow/{d['flow_id']}", car)
    log(s == 200 and d.get("type") == "create_entry", "the vehicle is added with its evcc car and without a plug sensor", f"{d.get('type')} {d.get('errors')}")

    # ---------- at run time: plugged in comes from evcc ----------
    need = None

    def plugged_from_evcc():
        nonlocal need
        need = it.find("sensor", "energy_to_charge")
        a = (need or {}).get("attributes", {})
        return a.get("plugged_source") == "evcc" and a.get("plugged") is True
    ok = it.wait_for(plugged_from_evcc, 180)
    a = (need or {}).get("attributes", {})
    log(bool(ok) and (a.get("evcc") or {}).get("ok") is True and (a.get("evcc") or {}).get("source") == "own",
        "plugged in is read from evcc (the demo car is at its loadpoint)",
        json.dumps({k: a.get(k) for k in ("plugged", "plugged_source", "evcc")}))
    plan = it.find("sensor", "charge_plan")
    log(plan is not None and plan["state"] not in ("unknown", "unavailable") and plan["attributes"].get("executed") is False,
        "a charge plan is computed and says it is not executed", f"{(plan or {}).get('state')}")

    # ---------- a second vehicle gets the next evcc car ----------
    s, d = it.api("POST", "/api/config/config_entries/subentries/flow", {"handler": [pw_id, "vehicle"]})
    vals = form_values(d)
    log(s == 200 and vals.get("evcc_vehicle") not in (None, "vehicle_1") and vals.get("name") != "blue e-Golf",
        "a second vehicle is offered the next evcc car", json.dumps({k: vals.get(k) for k in ("name", "evcc_vehicle")}))
    it.api("DELETE", f"/api/config/config_entries/subentries/flow/{d.get('flow_id')}")

    # ---------- the plan Plugwhen would write into evcc: shown, never written ----------
    it.svc("input_number", "set_value", {"entity_id": "input_number.auto_soc", "value": 10})   # low charge: a plan is needed
    ep = None

    def has_proposal():
        nonlocal ep
        it.api("POST", "/api/services/homeassistant/update_entity", {"entity_id": (plan or {}).get("entity_id")})
        ep = ((it.find("sensor", "charge_plan") or {}).get("attributes") or {}).get("evcc_plan")
        return isinstance(ep, dict) and ep.get("would_write") is not None
    ok = it.wait_for(has_proposal, 360, step=10)
    log(bool(ok) and ep.get("written") is False and ep.get("evcc_known") is True and ep["would_write"].get("soc", 0) > 10,
        "the plan for evcc is shown (target and time) and nothing is written", json.dumps(ep))
    st = subprocess.run(["curl", "-s", "-m", "5", "http://localhost:17070/api/state"], capture_output=True, text=True).stdout
    try:
        demo_plan = ((json.loads(st).get("result", json.loads(st)).get("vehicles") or {}).get("vehicle_1") or {}).get("plan")
    except ValueError:
        demo_plan = "?"
    log(not demo_plan or (ep or {}).get("current") == demo_plan or not (demo_plan or {}).get("soc"),
        "evcc's own plan is untouched (Plugwhen only reads)", json.dumps(demo_plan))

    logs = subprocess.run(["docker", "logs", it.CONTAINER], capture_output=True, text=True).stdout
    errs = [ln for ln in logs.splitlines() if "plugwhen" in ln.lower() and (" ERROR " in ln or "Traceback" in ln)]
    log(not errs, "no errors of Plugwhen in the log", "; ".join(errs[:3]))


if __name__ == "__main__":
    try:
        main()
    finally:
        fails = [ln for ok, ln in it.REPORT if not ok]
        print(f"\n{len(it.REPORT) - len(fails)} of {len(it.REPORT)} checks passed")
        with open("tests/install/report_evcc.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(ln for _, ln in it.REPORT) + "\n")
        sys.exit(1 if fails else 0)
