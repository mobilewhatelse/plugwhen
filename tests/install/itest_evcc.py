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
    for key in ("vehicle_1", "vehicle_2"):   # the demo evcc keeps running between test runs: start without plans
        subprocess.run(["curl", "-s", "-m", "5", "-X", "DELETE", f"http://localhost:17070/api/vehicles/{key}/plan/soc"], capture_output=True)

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
           "capacity_kwh": 44, "reserve_km": 100, "consumption_kwh_100": 20, "charge_kw_max": 11, "charge_kw_min": 4.1, "evcc_vehicle": "vehicle_1",
           "departure_entity": "input_datetime.abfahrt"}   # a fresh installation has no learned departures yet
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
    it.svc("input_datetime", "set_datetime", {"entity_id": "input_datetime.abfahrt", "time": "07:00:00"})   # the next 07:00
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
    log(not (demo_plan or {}).get("soc"),
        "evcc's own plan is untouched (Plugwhen only reads)", json.dumps(demo_plan))

    # ---------- a calendar with a trip, a stock, and writing plans into evcc ----------
    def evcc_vehicle(key):
        out = subprocess.run(["curl", "-s", "-m", "5", "http://localhost:17070/api/state"], capture_output=True, text=True).stdout
        try:
            d = json.loads(out)
            return ((d.get("result", d).get("vehicles") or {}).get(key) or {})
        except ValueError:
            return {}

    cal, err = it.flow_finish("/api/config/config_entries/flow", {"handler": "local_calendar", "show_advanced_options": False}, {"calendar_name": "Fahrten"})
    log(cal is not None, "a local calendar 'Fahrten' is set up", err)
    tomorrow = time.strftime("%Y-%m-%d", time.localtime(time.time() + 86400))
    it.svc("calendar", "create_event", {"entity_id": "calendar.fahrten", "summary": "Linz 200 km", "location": "Linz",
                                         "start_date_time": f"{tomorrow} 05:00:00", "end_date_time": f"{tomorrow} 18:00:00"})
    car2 = {"name": "Kalenderauto", "odometer_entity": "sensor.auto_kilometerstand", "soc_entity": "sensor.auto_ladestand", "capacity_kwh": 80,
            "reserve_km": 100, "consumption_kwh_100": 20, "charge_kw_max": 11, "charge_kw_min": 4.1, "evcc_vehicle": "vehicle_2",
            "trip_calendar": "calendar.fahrten", "stock_soc": 60}
    s, d = it.api("POST", "/api/config/config_entries/subentries/flow", {"handler": [pw_id, "vehicle"]})
    s, d = it.api("POST", f"/api/config/config_entries/subentries/flow/{d['flow_id']}", car2)
    log(s == 200 and d.get("type") == "create_entry", "a second car with the calendar and a stock of 60 % is added", f"{d.get('type')} {d.get('errors')}")
    pa = {}

    def trip_seen():
        nonlocal pa
        pa = ((it.state("sensor.kalenderauto_charge_plan") or {}).get("attributes") or {})
        return bool(pa.get("trips"))
    ok = it.wait_for(trip_seen, 240, step=10)
    tr = (pa.get("trips") or [{}])[0]
    log(bool(ok) and tr.get("km") == 200.0 and tr.get("km_source") == "event" and tr.get("range_km") == 230.0 and pa.get("departure_source") == "calendar",
        "the calendar trip is the departure: 200 km from the title, range 230 km", json.dumps({k: tr.get(k) for k in ("title", "km", "km_source", "range_km")}) + f" {pa.get('departure_source')}")
    need2 = ((it.state("sensor.kalenderauto_energy_to_charge") or {}).get("attributes") or {})
    log((need2.get("target_soc") or 0) >= 60, "the stock of 60 % is the lowest target", str(need2.get("target_soc")))

    # an own plan in evcc for the first car must never be touched; the second car gets Plugwhen's plan
    own_t = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 3 * 86400))
    subprocess.run(["curl", "-s", "-m", "5", "-X", "POST", f"http://localhost:17070/api/vehicles/vehicle_1/plan/soc/90/{own_t}"], capture_output=True)
    own_before = evcc_vehicle("vehicle_1").get("plan")
    sw = it.find("select", "kalenderauto_mode") or {}
    log(sw.get("state") == "learn" and "evcc" in ((sw.get("attributes") or {}).get("options") or [])
        and "direct" not in ((sw.get("attributes") or {}).get("options") or []),
        "the car linked to evcc offers the mode 'via evcc' (default: learn)", json.dumps({"state": sw.get("state"), "options": (sw.get("attributes") or {}).get("options")}))
    it.svc("select", "select_option", {"entity_id": sw.get("entity_id"), "option": "evcc"})
    written = {}

    def plan_written():
        nonlocal written
        written = evcc_vehicle("vehicle_2").get("plan") or {}
        return bool(written.get("soc"))
    ok = it.wait_for(plan_written, 240, step=10)
    ep2 = ((it.state("sensor.kalenderauto_charge_plan") or {}).get("attributes") or {}).get("evcc_plan") or {}
    want = ep2.get("would_write") or {}
    log(bool(ok) and int(written.get("soc", 0)) == int(want.get("soc", -1)) and ep2.get("by_plugwhen") is True,
        "Plugwhen wrote its plan into evcc for the second car (target and time as proposed)", json.dumps({"evcc": written, "proposal": want}))
    own_after = evcc_vehicle("vehicle_1").get("plan")
    ep1 = ((it.state("sensor.blue_e_golf_charge_plan") or {}).get("attributes") or {}).get("evcc_plan") or {}
    log(bool(own_before) and own_after == own_before and ep1.get("own_plan") is True,
        "the own plan in evcc of the first car is left alone", json.dumps({"before": own_before, "after": own_after}))

    # the switch keeps its state over a reload (restart), and a car without evcc has no switch
    it.api("POST", f"/api/config/config_entries/entry/{pw_id}/reload")
    time.sleep(15)
    sw = it.state(sw.get("entity_id")) or {}
    log(sw.get("state") == "evcc", "after a reload the mode is still 'via evcc'", str(sw.get("state")))

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
