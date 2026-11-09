"""Installation test: an evcc on the same machine as Home Assistant (like the add-on) is found and suggested, by the guard and Plugwhen.

The Home Assistant container `pw-local-test` (port 18128, config: tests/install/config_both, both integrations) is started by the runner.
This test starts a demo evcc INSIDE the network of that container (`--network container:pw-local-test`), so Home Assistant reaches it
at http://localhost:7070 exactly as it reaches an evcc add-on. First without evcc (nothing may be suggested), then with it.
evcc is only read. Takes about three minutes.
"""
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import itest as it  # noqa: E402  (the helpers of the single test)

it.BASE = "http://localhost:18128"
it.CONTAINER = "pw-local-test"
EVCC_CONTAINER = "evcc-local"
LOCAL = "http://localhost:7070"
log = it.log


def form_values(d):
    out = {}
    for f in (d or {}).get("data_schema", []) if isinstance(d, dict) else []:
        v = f.get("default", (f.get("description") or {}).get("suggested_value"))
        if v is not None:
            out[f["name"]] = v
    return out


def open_form(path, body):
    """Starts a flow, returns (status, answer, values shown) and cancels it again."""
    s, d = it.api("POST", path, body)
    vals = form_values(d)
    if isinstance(d, dict) and d.get("flow_id") and d.get("type") == "form":
        it.api("DELETE", f"{path}/{d['flow_id']}")
    return s, d, vals


def entry_id(domain):
    s, lst = it.api("GET", f"/api/config/config_entries/entry?domain={domain}")
    return lst[0]["entry_id"] if s == 200 and lst else None


def main():
    if not it.wait_ready():
        log(False, "Home Assistant starts")
        return
    ok, msg = it.onboard()
    log(ok, "Home Assistant starts and the test user exists", msg)
    if not ok:
        return

    # ---------- 1) no evcc on this machine: nothing is suggested ----------
    s, d, vals = open_form("/api/config/config_entries/flow", {"handler": "viertelstunden_waechter", "show_advanced_options": False})
    log(s == 200 and not vals.get("evcc_site_url"), "without evcc the guard suggests no evcc address", json.dumps(vals.get("evcc_site_url")))
    pw, err = it.flow_finish("/api/config/config_entries/flow", {"handler": "plugwhen", "show_advanced_options": False}, {})
    log(pw is not None, "Plugwhen is set up", err)
    pw_id = entry_id("plugwhen")
    s, d, vals = open_form("/api/config/config_entries/options/flow", {"handler": pw_id})
    log(s == 200 and not vals.get("evcc_url"), "without evcc Plugwhen suggests no evcc address", json.dumps(vals.get("evcc_url")))

    # ---------- 2) evcc starts on this machine (in the network of Home Assistant, like the add-on) ----------
    subprocess.run(["docker", "rm", "-f", EVCC_CONTAINER], capture_output=True)
    r = subprocess.run(["docker", "run", "-d", "--name", EVCC_CONTAINER, "--network", f"container:{it.CONTAINER}",
                        "evcc/evcc:latest", "evcc", "--demo"], capture_output=True, text=True)
    log(r.returncode == 0, "a demo evcc runs on the same machine as Home Assistant", r.stderr.strip()[:200])

    found = {}

    def plugwhen_suggests():
        nonlocal found
        _, _, found = open_form("/api/config/config_entries/options/flow", {"handler": pw_id})
        return found.get("evcc_url") == LOCAL
    ok = it.wait_for(plugwhen_suggests, 120, step=5)
    log(bool(ok), "Plugwhen suggests the local evcc in its settings", json.dumps(found.get("evcc_url")))

    s, d, vals = open_form("/api/config/config_entries/flow", {"handler": "viertelstunden_waechter", "show_advanced_options": False})
    log(s == 200 and vals.get("evcc_site_url") == LOCAL, "the guard suggests the local evcc at set-up", json.dumps(vals.get("evcc_site_url")))
    wa, err = it.flow_finish("/api/config/config_entries/flow", {"handler": "viertelstunden_waechter", "show_advanced_options": False},
                             {"name": "Viertelstunden-Wächter", "grid_power": "sensor.netzbezug", "evcc_site_url": LOCAL, "limit_kw": 10.0, "margin_kw": 0.5})
    log(wa is not None, "the guard is set up with the local evcc (its grid meter is checked)", err)
    wa_id = entry_id("viertelstunden_waechter")

    s, d, vals = open_form("/api/config/config_entries/subentries/flow", {"handler": [wa_id, "evcc"]})
    log(s == 200 and vals.get("evcc_url") == LOCAL, "a new evcc loadpoint of the guard takes the address from the general settings",
        json.dumps(vals.get("evcc_url")))

    # ---------- 3) Plugwhen set up after the guard: connected at once, and the evcc address comes from the guard ----------
    it.api("DELETE", f"/api/config/config_entries/entry/{pw_id}")
    time.sleep(3)
    pw, err = it.flow_finish("/api/config/config_entries/flow", {"handler": "plugwhen", "show_advanced_options": False}, {})
    pw_id = entry_id("plugwhen")
    s, lst = it.api("GET", "/api/config/config_entries/entry?domain=plugwhen")
    log(pw is not None and pw_id is not None, "Plugwhen is set up again after the guard", err)
    s, d, vals = open_form("/api/config/config_entries/options/flow", {"handler": pw_id})
    log(vals.get("waechter_entry") == wa_id and not vals.get("evcc_url"),
        "Plugwhen set up after the guard is connected to it at once (and needs no own evcc address)",
        json.dumps({k: vals.get(k) for k in ("waechter_entry", "evcc_url")}))
    s, d, vals = open_form("/api/config/config_entries/subentries/flow", {"handler": [pw_id, "vehicle"]})
    log(s == 200 and vals.get("evcc_vehicle") == "vehicle_1" and vals.get("name") == "blue e-Golf",
        "adding a vehicle offers the evcc cars through the guard's address", json.dumps({k: vals.get(k) for k in ("name", "evcc_vehicle", "capacity_kwh")}))

    # ---------- 4) everything set up with evcc, then evcc is removed: both keep working ----------
    car = {"name": "blue e-Golf", "odometer_entity": "sensor.auto_kilometerstand", "soc_entity": "sensor.auto_ladestand", "capacity_kwh": 44,
           "reserve_km": 100, "consumption_kwh_100": 20, "charge_kw_max": 11, "charge_kw_min": 1.4, "evcc_vehicle": "vehicle_1"}
    res, err = it.flow_finish("/api/config/config_entries/subentries/flow", {"handler": [pw_id, "vehicle"]}, car)
    log(res is not None, "a vehicle linked to evcc is added (no plug sensor: plugged in comes from evcc)", err)
    need = None

    def evcc_read():
        nonlocal need
        need = (it.find("sensor", "energy_to_charge") or {}).get("attributes", {})
        return (need.get("evcc") or {}).get("ok") is True and need.get("plugged_source") == "evcc"
    ok = it.wait_for(evcc_read, 400, step=10)
    log(bool(ok), "with evcc: plugged in is read from evcc", json.dumps({k: need.get(k) for k in ("plugged", "plugged_source", "evcc")}))

    subprocess.run(["docker", "rm", "-f", EVCC_CONTAINER], capture_output=True)   # evcc is gone (add-on removed or stopped)
    log(True, "evcc is removed")

    def evcc_gone():
        nonlocal need
        need = (it.find("sensor", "energy_to_charge") or {}).get("attributes", {})
        return (need.get("evcc") or {}).get("ok") is False
    ok = it.wait_for(evcc_gone, 420, step=10)
    plan = it.find("sensor", "blue_e_golf_charge_plan") or {}   # Plugwhen's plan (the guard has a charge plan sensor too)
    ep = (plan.get("attributes") or {}).get("evcc_plan") or {}
    log(bool(ok) and need.get("plugged") is None and need.get("plugged_source") is None and plan.get("state") not in (None, "unavailable", "unknown")
        and ep.get("evcc_known") is False and ep.get("written") is False,
        "without evcc Plugwhen keeps planning: evcc marked as not answering, plugged in unknown, the proposal stays visible",
        json.dumps({"plan": plan.get("state"), "plugged": need.get("plugged"), "evcc": need.get("evcc"), "evcc_known": ep.get("evcc_known")}))
    st = it.state("sensor.viertelstunden_wachter_status") or {}
    log(st.get("state") not in (None, "unavailable", "unknown") and (st.get("attributes") or {}).get("grid_source") == "sensor",
        "without evcc the guard keeps regulating with its own sensor", json.dumps({"state": st.get("state"), "grid_source": (st.get("attributes") or {}).get("grid_source")}))
    # a restart of both while evcc is gone (Home Assistant restarts, evcc is still uninstalled)
    for eid in (pw_id, wa_id):
        it.api("POST", f"/api/config/config_entries/entry/{eid}/reload")
    time.sleep(20)
    s, lst = it.api("GET", "/api/config/config_entries/entry")
    states = {e["domain"]: e["state"] for e in (lst if isinstance(lst, list) else []) if e["domain"] in ("plugwhen", "viertelstunden_waechter")}
    log(states.get("plugwhen") == "loaded" and states.get("viertelstunden_waechter") == "loaded",
        "both start again without evcc (reload while evcc is gone)", json.dumps(states))
    s, d, vals = open_form("/api/config/config_entries/subentries/flow", {"handler": [pw_id, "vehicle"]})
    log(s == 200 and isinstance(d, dict) and d.get("type") == "form", "adding a vehicle still works without evcc (no evcc field, no error)",
        json.dumps({"evcc_field": "evcc_vehicle" in [f["name"] for f in d.get("data_schema", [])] if isinstance(d, dict) else None}))

    logs = subprocess.run(["docker", "logs", it.CONTAINER], capture_output=True, text=True).stdout
    errs = [ln for ln in logs.splitlines() if ("plugwhen" in ln.lower() or "viertelstunden" in ln.lower()) and (" ERROR " in ln or "Traceback" in ln)]
    log(not errs, "no errors of either integration in the log", "; ".join(errs[:3]))


if __name__ == "__main__":
    try:
        main()
    finally:
        subprocess.run(["docker", "rm", "-f", EVCC_CONTAINER], capture_output=True)
        fails = [ln for ok, ln in it.REPORT if not ok]
        print(f"\n{len(it.REPORT) - len(fails)} of {len(it.REPORT)} checks passed")
        with open("tests/install/report_local_evcc.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(ln for _, ln in it.REPORT) + "\n")
        sys.exit(1 if fails else 0)
