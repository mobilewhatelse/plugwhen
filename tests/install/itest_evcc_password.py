"""Installation test: Plugwhen with an evcc that has an admin PASSWORD (fresh Home Assistant in Docker).

Needs a real evcc (the demo refuses a password) with tests/install/evcc_password/evcc.yaml:
  docker run -d --name evcc-pw -p 17071:7070 -v <repo>/tests/install/evcc_password/evcc.yaml:/etc/evcc.yaml evcc/evcc:latest evcc -c /etc/evcc.yaml
and the Home Assistant container `pw-evcc-pw` on port 18131 with `--add-host=host.docker.internal:host-gateway` (config: tests/install/config).
The test sets the password itself. Checks: a wrong password is refused, the right one accepted, reading and writing a plan work
with the password set, the password shows nowhere (states, log). Takes about five minutes.
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import itest as it  # noqa: E402  (the helpers of the single test)

it.BASE = "http://localhost:18131"
it.CONTAINER = "pw-evcc-pw"
EVCC_LOCAL = "http://localhost:17071"
EVCC = "http://host.docker.internal:17071"
PASSWORD = "Pw-only-for-this-test-7"
log = it.log


def evcc(method, path, body=None):
    req = urllib.request.Request(EVCC_LOCAL + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return 0, str(e)


def vehicle(key):
    _, body = evcc("GET", "/api/state")
    try:
        d = json.loads(body)
        return (d.get("result", d).get("vehicles") or {}).get(key) or {}
    except ValueError:
        return {}


def form_values(d):
    out = {}
    for f in (d or {}).get("data_schema", []) if isinstance(d, dict) else []:
        v = f.get("default", (f.get("description") or {}).get("suggested_value"))
        if v is not None:
            out[f["name"]] = v
    return out


def main():
    # ---------- evcc with a password ----------
    ok = it.wait_for(lambda: evcc("GET", "/api/state")[0] == 200, 90, step=3)
    s, _ = evcc("PUT", "/api/auth/password", {"current": "", "new": PASSWORD})
    s_cfg, _ = evcc("GET", "/api/config/site")
    log(bool(ok) and s in (200, 201, 202, 204) and s_cfg == 401, "evcc runs and has an admin password (its settings want a login)",
        f"set {s}, settings without login {s_cfg}")
    s_bad, _ = evcc("POST", "/api/auth/login", {"password": "wrong"})
    s_ok, _ = evcc("POST", "/api/auth/login", {"password": PASSWORD})
    log(s_bad == 401 and s_ok == 200, "evcc refuses a wrong password and takes the right one", f"wrong {s_bad}, right {s_ok}")
    evcc("DELETE", "/api/vehicles/testauto/plan/soc")

    if not it.wait_ready():
        log(False, "Home Assistant starts")
        return
    ok, msg = it.onboard()
    log(ok, "Home Assistant starts and the test user exists", msg)
    if not ok:
        return
    it.wait_for(lambda: it.state("sensor.auto_ladestand") and it.state("sensor.auto_ladestand")["state"] not in ("unknown", "unavailable"), 120)

    # ---------- the first step of the setup already checks the password ----------
    s, d = it.api("POST", "/api/config/config_entries/flow", {"handler": "plugwhen", "show_advanced_options": False})
    s2, d2 = it.api("POST", f"/api/config/config_entries/flow/{d['flow_id']}", {"evcc_url": EVCC, "evcc_password": "wrong"})
    log(s2 == 200 and (d2.get("errors") or {}).get("evcc_password") == "evcc_auth", "setup: a wrong evcc password is refused right away",
        str(d2.get("errors")))
    it.api("DELETE", f"/api/config/config_entries/flow/{d['flow_id']}")
    pw, err = it.flow_finish("/api/config/config_entries/flow", {"handler": "plugwhen", "show_advanced_options": False}, {})
    log(pw is not None, "Plugwhen is set up (evcc comes in the options)", err)
    if not pw:
        return
    pw_id = it.api("GET", "/api/config/config_entries/entry?domain=plugwhen")[1][0]["entry_id"]

    # ---------- the options: a wrong password is refused, the right one accepted ----------
    s, d = it.api("POST", "/api/config/config_entries/options/flow", {"handler": pw_id})
    s2, d2 = it.api("POST", f"/api/config/config_entries/options/flow/{d['flow_id']}",
                    {"use_solar_forecast": True, "evcc_url": EVCC, "evcc_password": "wrong"})
    log(s2 == 200 and (d2.get("errors") or {}).get("evcc_password") == "evcc_auth", "options: a wrong evcc password is refused",
        str(d2.get("errors")))
    s3, d3 = it.api("POST", f"/api/config/config_entries/options/flow/{d['flow_id']}",
                    {"use_solar_forecast": True, "evcc_url": EVCC, "evcc_password": PASSWORD})
    log(s3 == 200 and d3.get("type") == "create_entry", "options: the right password is accepted and saved", f"{d3.get('type')} {d3.get('errors')}")
    time.sleep(8)   # the entry reloads

    # ---------- the vehicle is filled in from evcc (read with the password set) ----------
    s, d = it.api("POST", "/api/config/config_entries/subentries/flow", {"handler": [pw_id, "vehicle"]})
    vals = form_values(d)
    log(s == 200 and vals.get("evcc_vehicle") == "testauto" and vals.get("capacity_kwh") == 60,
        "the vehicle form is filled in from evcc", json.dumps({k: vals.get(k) for k in ("name", "capacity_kwh", "evcc_vehicle")}))
    car = {"name": "Testauto", "odometer_entity": "sensor.auto_kilometerstand", "soc_entity": "sensor.auto_ladestand",
           "capacity_kwh": 60, "reserve_km": 100, "consumption_kwh_100": 20, "charge_kw_max": 11, "charge_kw_min": 4.1,
           "evcc_vehicle": "testauto", "departure_entity": "input_datetime.abfahrt"}
    s, d = it.api("POST", f"/api/config/config_entries/subentries/flow/{d['flow_id']}", car)
    log(s == 200 and d.get("type") == "create_entry", "the vehicle is added with its evcc car", f"{d.get('type')} {d.get('errors')}")

    need = {}

    def plugged_from_evcc():
        nonlocal need
        need = ((it.state("sensor.testauto_energy_to_charge") or {}).get("attributes") or {})
        return need.get("plugged_source") == "evcc" and need.get("plugged") is True
    ok = it.wait_for(plugged_from_evcc, 180, step=10)
    log(bool(ok) and (need.get("evcc") or {}).get("ok") is True, "at run time evcc is read (plugged in from its loadpoint)",
        json.dumps({k: need.get(k) for k in ("plugged", "plugged_source", "evcc")}))

    # ---------- writing the plan into evcc works with the password set ----------
    it.svc("input_number", "set_value", {"entity_id": "input_number.auto_soc", "value": 10})
    it.svc("input_datetime", "set_datetime", {"entity_id": "input_datetime.abfahrt", "time": "07:00:00"})
    sel = (it.find("select", "testauto_mode") or {}).get("entity_id", "select.testauto_mode")
    it.svc("select", "select_option", {"entity_id": sel, "option": "evcc"})
    written = {}

    def plan_written():
        nonlocal written
        it.api("POST", "/api/services/homeassistant/update_entity", {"entity_id": "sensor.testauto_charge_plan"})
        written = vehicle("testauto").get("plan") or {}
        return bool(written.get("soc"))
    ok = it.wait_for(plan_written, 300, step=10)
    ep = ((it.state("sensor.testauto_charge_plan") or {}).get("attributes") or {}).get("evcc_plan") or {}
    log(bool(ok) and ep.get("by_plugwhen") is True, "Plugwhen writes its plan into the evcc with a password",
        json.dumps({"evcc": written, "plugwhen": ep.get("would_write")}))
    it.svc("select", "select_option", {"entity_id": sel, "option": "learn"})
    ok = it.wait_for(lambda: not (vehicle("testauto").get("plan") or {}).get("soc"), 180, step=10)
    log(bool(ok), "back to learning, Plugwhen removes its own plan again", json.dumps(vehicle("testauto").get("plan")))

    # ---------- the password shows nowhere ----------
    s, states = it.api("GET", "/api/states")
    log(s == 200 and PASSWORD not in json.dumps(states), "the password is in no state or attribute")
    logs = subprocess.run(["docker", "logs", it.CONTAINER], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace").stdout
    log(PASSWORD not in logs, "the password is not in the log")
    errs = [ln for ln in logs.splitlines() if "plugwhen" in ln.lower() and (" ERROR " in ln or "Traceback" in ln)]
    log(not errs, "no errors of Plugwhen in the log", "; ".join(errs[:3]))


if __name__ == "__main__":
    try:
        main()
    finally:
        fails = [ln for ok, ln in it.REPORT if not ok]
        print(f"\n{len(it.REPORT) - len(fails)} of {len(it.REPORT)} checks passed")
        with open("tests/install/report_evcc_password.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(ln for _, ln in it.REPORT) + "\n")
        sys.exit(1 if fails else 0)
