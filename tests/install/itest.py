"""Installation test of Plugwhen against a fresh Home Assistant (Docker, localhost). Takes about five minutes."""
import json
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://localhost:18124"
CONTAINER = "pw-test"
REPORT = []
TOKEN = None


def log(ok, name, detail=""):
    line = ("PASS" if ok else "FAIL") + "  " + name + (f"  [{detail}]" if detail else "")
    REPORT.append((ok, line))
    print(line, flush=True)


def api(method, path, body=None, form=None, token=True):
    data, headers = None, {}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if token and TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            txt = r.read().decode()
            return r.status, (json.loads(txt) if txt.strip().startswith(("{", "[")) else txt)
    except urllib.error.HTTPError as e:
        txt = e.read().decode()
        try:
            return e.code, json.loads(txt)
        except ValueError:
            return e.code, txt


def wait_ready(timeout=420):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if api("GET", "/api/onboarding", token=False)[0] == 200:
                return True
        except Exception:
            pass
        time.sleep(5)
    return False


def wait_api(timeout=300):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if api("GET", "/api/config")[0] == 200:
                return True
        except Exception:
            pass
        time.sleep(5)
    return False


def onboard():
    global TOKEN
    pw = secrets.token_urlsafe(16)
    cid = BASE + "/"
    s, d = api("POST", "/api/onboarding/users", {"client_id": cid, "name": "Test", "username": "testuser", "password": pw, "language": "en"}, token=False)
    if s != 200:
        return False, f"onboarding users {s} {d}"
    s, d = api("POST", "/auth/token", form={"grant_type": "authorization_code", "code": d["auth_code"], "client_id": cid}, token=False)
    if s != 200:
        return False, f"token {s} {d}"
    TOKEN = d["access_token"]
    return True, ""


def state(eid):
    s, d = api("GET", f"/api/states/{eid}")
    return d if s == 200 else None


def states_like(sub):
    s, d = api("GET", "/api/states")
    return [x for x in d if sub in x["entity_id"]]


def svc(domain, service, data=None):
    return api("POST", f"/api/services/{domain}/{service}", data or {})


def wait_for(pred, timeout, step=3):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            v = pred()
        except Exception:
            v = None
        if v:
            return v
        time.sleep(step)
    return None


def flow_finish(path, init_body, user_input):
    s, d = api("POST", path, init_body)
    if s != 200:
        return None, f"init {s} {d}"
    for _ in range(4):
        if d.get("type") == "create_entry":
            return d, ""
        if d.get("type") == "abort":
            return None, f"abort {d.get('reason')}"
        if d.get("type") == "form":
            s, d = api("POST", f"{path}/{d['flow_id']}", user_input)
            if s != 200:
                return None, f"step {s} {d}"
            if d.get("errors"):
                return None, f"errors {d['errors']}"
        else:
            return None, f"unexpected {d.get('type')}"
    return (d if d.get("type") == "create_entry" else None), "no create_entry"


def find(domain, fragment):
    for e in states_like(fragment):
        if e["entity_id"].startswith(domain + "."):
            return e
    return None


def num(eid):
    st = state(eid)
    return float(st["state"]) if st and st["state"] not in ("unknown", "unavailable") else None


def main():
    if not wait_ready():
        log(False, "Home Assistant starts")
        return
    log(True, "Home Assistant starts (fresh instance)")
    ok, msg = onboard()
    log(ok, "test user and token created", msg)
    if not ok:
        return
    ok = wait_for(lambda: state("sensor.auto_ladestand") and state("sensor.auto_ladestand")["state"] not in ("unknown", "unavailable"), 120)
    log(bool(ok), "simulated car (odometer, state of charge, plug) runs")

    s, d = api("POST", "/api/config/config_entries/flow", {"handler": "plugwhen", "show_advanced_options": False})
    log(s == 200 and d.get("type") == "form" and d.get("step_id") == "user", "integration is offered in the dialog", f"{s} {d.get('type')} {d.get('step_id')}")
    entry, err = flow_finish("/api/config/config_entries/flow", {"handler": "plugwhen", "show_advanced_options": False}, {})
    log(entry is not None, "integration set up from scratch", err)
    if not entry:
        return
    s, lst = api("GET", "/api/config/config_entries/entry?domain=plugwhen")
    entry_id = lst[0]["entry_id"]
    s, d = api("POST", "/api/config/config_entries/flow", {"handler": "plugwhen"})
    log(s == 200 and d.get("type") == "abort", "a second entry is refused", f"{d.get('type')} {d.get('reason')}")

    car = {"name": "Testauto", "odometer_entity": "sensor.auto_kilometerstand", "soc_entity": "sensor.auto_ladestand",
           "capacity_kwh": 60, "reserve_km": 100, "consumption_kwh_100": 20,
           "plugged_entity": "binary_sensor.auto_stecker", "wallbox_energy_entity": "sensor.wallbox_zaehler"}
    s, d = api("POST", "/api/config/config_entries/subentries/flow", {"handler": [entry_id, "vehicle"]})
    s2, d2 = api("POST", f"/api/config/config_entries/subentries/flow/{d['flow_id']}", dict(car, soc_entity="sensor.auto_kilometerstand"))
    log(s2 == 200 and (d2.get("errors") or {}).get("soc_entity") == "same_entity", "the same sensor twice is refused", str(d2.get("errors")))
    api("DELETE", f"/api/config/config_entries/subentries/flow/{d['flow_id']}")
    res, err = flow_finish("/api/config/config_entries/subentries/flow", {"handler": [entry_id, "vehicle"]}, car)
    log(res is not None, "vehicle added as subentry", err)

    time.sleep(15)
    ents = states_like("testauto")
    log(len(ents) == 7, "entities of the vehicle exist", f"{len(ents)}: " + ", ".join(sorted(e["entity_id"].split(".")[1] for e in ents)))
    charge = find("sensor", "energy_to_charge")
    rng = find("sensor", "range_needed")
    soc_t = find("sensor", "target_state_of_charge")
    reserve = find("number", "reserve")
    learn = find("switch", "learn_kilometres")
    week = find("sensor", "learned_days")
    log(all([charge, rng, soc_t, reserve, learn, week]), "all kinds of entities are there")
    if not all([charge, rng, soc_t, reserve, learn, week]):
        return
    cid, rid, tid, lid, resid = (e["entity_id"] for e in (charge, rng, soc_t, learn, reserve))

    ok = wait_for(lambda: num(cid) is not None, 60)
    log(bool(ok), "first computation done", str((state(cid) or {}).get("state")))
    # state of charge 40 %, reserve 100 km, 20 kWh/100 km, 60 kWh: target 33.3 %, nothing to charge
    log(num(cid) == 0.0 and abs((num(tid) or 0) - 33.3) < 0.2 and num(rid) == 100.0,
        "enough charge: 100 km, target 33 %, charge 0 kWh", f"{num(cid)} / {num(tid)} / {num(rid)}")
    log(state(lid)["state"] == "on", "kilometre learning is on by default")
    log(num(resid) == 100.0, "reserve starts at the value of the set-up")

    # a low battery: 10 % -> (33.3 - 10) % of 60 kWh / 0.9 = 15.6 kWh (recomputed when a setting changes)
    svc("input_number", "set_value", {"entity_id": "input_number.auto_soc", "value": 10})
    time.sleep(3)
    svc("switch", "turn_off", {"entity_id": lid})
    svc("switch", "turn_on", {"entity_id": lid})
    ok = wait_for(lambda: abs((num(cid) or 0) - 15.6) < 0.2, 30)
    log(bool(ok), "low battery: 15.6 kWh to charge", str(num(cid)))
    a = state(cid)["attributes"]
    log(a.get("plugged") is False and a.get("soc") == 10.0 and a.get("source") == "reserve", "attributes: plug, state of charge, source",
        json.dumps({k: a.get(k) for k in ("plugged", "soc", "source")}))

    # reserve 150 km = 30 kWh = 50 %: (50 - 10) % of 60 kWh / 0.9 = 26.7 kWh
    svc("number", "set_value", {"entity_id": resid, "value": 150})
    ok = wait_for(lambda: abs((num(cid) or 0) - 26.7) < 0.2, 30)
    log(bool(ok), "reserve 150 km: 26.7 kWh to charge", str(num(cid)))

    svc("input_boolean", "turn_on", {"entity_id": "input_boolean.auto_angesteckt"})
    time.sleep(2)
    svc("number", "set_value", {"entity_id": resid, "value": 150})
    ok = wait_for(lambda: state(cid)["attributes"].get("plugged") is True, 30)
    log(bool(ok), "plug state is followed")

    wk = state(week["entity_id"])
    log(isinstance(wk["attributes"].get("week"), list) and len(wk["attributes"]["week"]) == 7, "weekly plan has seven days", str(wk["state"]))
    log("history_error" in wk["attributes"], "history state is reported", str(wk["attributes"].get("history_error")))

    # ---------- restart: settings are restored ----------
    svc("switch", "turn_off", {"entity_id": lid})
    time.sleep(2)
    subprocess.run(["docker", "restart", CONTAINER], check=False, capture_output=True)
    time.sleep(20)
    log(bool(wait_api(300)), "Home Assistant is back after the restart")
    ok = wait_for(lambda: num(resid) is not None, 120)
    log(bool(ok) and num(resid) == 150.0, "reserve is restored", str(num(resid)))
    log(state(lid)["state"] == "off", "learning switch state is restored (off)")

    # ---------- remove ----------
    s, d = api("DELETE", f"/api/config/config_entries/entry/{entry_id}")
    log(s == 200, "integration can be removed", str(s))
    time.sleep(5)
    left = states_like("testauto")
    log(not left or all(e["state"] == "unavailable" for e in left), "entities are gone after removal")

    logs = subprocess.run(["docker", "logs", CONTAINER], capture_output=True, text=True).stdout
    errs = [ln for ln in logs.splitlines() if "plugwhen" in ln.lower() and (" ERROR " in ln or "Traceback" in ln)]
    log(not errs, "no errors of the integration in the log", "; ".join(errs[:3]))


if __name__ == "__main__":
    try:
        main()
    finally:
        fails = [ln for ok, ln in REPORT if not ok]
        print(f"\n{len(REPORT) - len(fails)} of {len(REPORT)} checks passed")
        with open("tests/install/report.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(ln for _, ln in REPORT) + "\n")
        sys.exit(1 if fails else 0)
