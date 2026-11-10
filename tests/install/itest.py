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
           "plugged_entity": "binary_sensor.auto_stecker", "wallbox_energy_entity": "sensor.wallbox_zaehler",
           "departure_entity": "input_datetime.abfahrt", "charge_kw_max": 11, "charge_kw_min": 1.4,
           "notify_service": "script.notify_sink, script.notify_sink_2", "notify_hour": 0}
    s, d = api("POST", "/api/config/config_entries/subentries/flow", {"handler": [entry_id, "vehicle"]})
    fields = {f.get("name"): f for f in (d.get("data_schema") or [])}
    sels = {k: ((fields.get(k) or {}).get("selector") or {}).get("entity") or {} for k in ("odometer_entity", "soc_entity", "wallbox_energy_entity")}
    log(all(v and "device_class" not in str(v) for v in sels.values()), "odometer, state of charge and wallbox counter do not filter by device class", str(sels))
    s3, d3 = api("POST", f"/api/config/config_entries/subentries/flow/{d['flow_id']}", dict(car, odometer_entity="sensor.wallbox_zaehler"))
    log(s3 == 200 and (d3.get("errors") or {}).get("odometer_entity") == "not_distance", "a sensor with a wrong unit (kWh as odometer) is refused with a clear error", str(d3.get("errors")))
    s2, d2 = api("POST", f"/api/config/config_entries/subentries/flow/{d['flow_id']}", dict(car, soc_entity="sensor.auto_kilometerstand"))
    log(s2 == 200 and (d2.get("errors") or {}).get("soc_entity") == "same_entity", "the same sensor twice is refused", str(d2.get("errors")))
    api("DELETE", f"/api/config/config_entries/subentries/flow/{d['flow_id']}")
    res, err = flow_finish("/api/config/config_entries/subentries/flow", {"handler": [entry_id, "vehicle"]}, car)
    log(res is not None, "vehicle added as subentry", err)

    time.sleep(15)
    ents = states_like("testauto")
    log(len(ents) == 15, "entities of the vehicle exist", f"{len(ents)}: " + ", ".join(sorted(e["entity_id"].split(".")[1] for e in ents)))
    charge = find("sensor", "energy_to_charge")
    rng = find("sensor", "range_needed")
    soc_t = find("sensor", "target_state_of_charge")
    reserve = find("number", "reserve")
    learn = find("switch", "learn_kilometres")
    week = find("sensor", "learned_days")
    plan_s = find("sensor", "charge_plan")
    ready_s = find("sensor", "ready_for_departure")
    notice_sw = find("switch", "warn_when")
    everything = [charge, rng, soc_t, reserve, learn, week, plan_s, ready_s, notice_sw]
    log(all(everything), "all kinds of entities are there")
    if not all(everything):
        return
    pid, rdid, nid = plan_s["entity_id"], ready_s["entity_id"], notice_sw["entity_id"]
    cid, rid, tid, lid, resid = (e["entity_id"] for e in (charge, rng, soc_t, learn, reserve))

    ok = wait_for(lambda: num(cid) is not None, 60)
    log(bool(ok), "first computation done", str((state(cid) or {}).get("state")))
    pa0 = (state(pid) or {}).get("attributes") or {}
    log("evcc_plan" in pa0 and pa0.get("evcc_plan") is None and pa0.get("executed") is False,
        "without evcc there is no plan for evcc, and the plan says it is not executed", json.dumps({k: pa0.get(k) for k in ("evcc_plan", "executed")}))
    modes = [e for e in states_like("_mode") if e["entity_id"].startswith("select.")]
    log(bool(modes) and all("evcc" not in ((e.get("attributes") or {}).get("options") or []) for e in modes),
        "without evcc the mode 'via evcc' is not offered", json.dumps([(e.get("attributes") or {}).get("options") for e in modes]))
    # state of charge 40 %, reserve 100 km, 20 kWh/100 km, 60 kWh: target 33.3 %, nothing to charge
    log(num(cid) == 0.0 and abs((num(tid) or 0) - 33.3) < 0.2 and num(rid) == 100.0,
        "enough charge: 100 km, target 33 %, charge 0 kWh", f"{num(cid)} / {num(tid)} / {num(rid)}")
    log(state(lid)["state"] == "on", "kilometre learning is on by default")
    ca, pa0 = state(cid)["attributes"], state(pid)["attributes"]
    log("efficiency" in ca and ca.get("efficiency_learned") is False and pa0.get("solar_deduct_source") == "default" and pa0.get("pref_kw") == 4.0,
        "house numbers start as defaults (efficiency, solar deduction, preferred power) and say so",
        f"eff {ca.get('efficiency')} learned {ca.get('efficiency_learned')} deduct {pa0.get('solar_deduct_source')} pref {pa0.get('pref_kw')}")
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

    # ---------- plan and warning (0.2) ----------
    log(state(nid)["state"] == "on", "warning switch is on by default")
    log(state(pid)["state"] == "planned" and state(pid)["attributes"].get("departure_source") == "entity",
        "charge plan exists, departure from the entity", str(state(pid)["state"]))
    pa = state(pid)["attributes"]
    log(abs(pa["needed_kwh"] - 26.7) < 0.3 and abs(pa["planned_kwh"] - pa["needed_kwh"]) < 0.3 and len(pa["windows"]) >= 1,
        "plan covers the need with at least one window", f"needed {pa['needed_kwh']} planned {pa['planned_kwh']} windows {len(pa['windows'])}")
    log(pa["load_forecast_used"] is False and pa["availability_used"] is False, "without connections no load forecast and no availability is used")

    # plugged in and a plan: ready; unplug: the warning to plug in
    ok = wait_for(lambda: state(rdid)["state"] == "ready", 30)
    log(bool(ok), "plugged in with a plan: ready for departure", state(rdid)["state"])

    # learn mode: default on, says what it would switch, switches nothing
    mode_s = find("select", "mode")
    would_s = find("sensor", "would_switch")
    log(bool(mode_s) and bool(would_s), "mode select and the sensor 'would switch' exist")
    if mode_s and would_s:
        mid, wid = mode_s["entity_id"], would_s["entity_id"]
        log(state(mid)["state"] == "learn", "the mode is learn by default", state(mid)["state"])
        lc = find("sensor", "does_learning_help")
        log(bool(lc), "the sensor 'does learning help' exists")
        if lc:
            ok = wait_for(lambda: state(lc["entity_id"])["state"] in ("too_little_data", "learning_helps", "reserve_enough", "little"), 30)
            la = state(lc["entity_id"])["attributes"]
            log(bool(ok) and state(lc["entity_id"])["state"] == "too_little_data" and str(la.get("chart", "")).startswith("<svg"),
                "no history yet: too little data, and the chart says so (valid SVG)", f"{state(lc['entity_id'])['state']} / {str(la.get('chart'))[:40]}")
        pa_h = state(pid)["attributes"]
        log("horizon" in pa_h and str(pa_h.get("horizon_chart", "")).startswith("<svg"),
            "the charge plan carries the look-ahead and its chart (valid SVG), also without a solar plant", f"{(pa_h.get('horizon') or {}).get('status')} / {str(pa_h.get('horizon_chart'))[:30]}")
        log(str(pa_h.get("sun_chart", "")).startswith("<svg") and "sun_windows" in (pa_h.get("horizon") or {}),
            "the charge plan carries the sun windows and their chart (valid SVG), also without a solar plant", f"{len((pa_h.get('horizon') or {}).get('sun_windows') or [])} windows / {str(pa_h.get('sun_chart'))[:30]}")
        hb = find("sensor", "charging_habit")
        hba = state(hb["entity_id"])["attributes"] if hb else {}
        log(bool(hb) and hba.get("status") in ("too_little_data", "ok", "no_data") and str(hba.get("chart", "")).startswith("<svg"),
            "the charging habit sensor exists and delivers a chart (valid SVG), also without any history", f"{hba.get('status')} / {str(hba.get('chart'))[:30]}")
        wa0 = state(wid)["attributes"] if would_s else {}
        log(str(wa0.get("chart", "")).startswith("<svg"), "learn mode: the chart of plan against reality is delivered as SVG", str(wa0.get("chart"))[:40])
        ok = wait_for(lambda: state(wid)["state"] in ("charge", "pause"), 30)
        wa = state(wid)["attributes"]
        log(bool(ok) and wa.get("reason") in ("in_window", "waiting_for_window", "plan_done", "cannot_reach_target") and "summary" in wa,
            "plugged in with a plan: it says charge or pause with a reason and a summary", f"{state(wid)['state']} / {wa.get('reason')}")
    # the first plug-in warning went out earlier, while the battery was low and the car not plugged in
    log((num("counter.meldungen") or 0) == 1, "the warning went out once while the car was unplugged and short", f"counter {num('counter.meldungen')}")
    svc("input_boolean", "turn_off", {"entity_id": "input_boolean.auto_angesteckt"})
    ok = wait_for(lambda: state(rdid)["state"] == "plug_in", 30)
    log(bool(ok), "unplugged: readiness says plug in", state(rdid)["state"])
    if mode_s and would_s:
        ok = wait_for(lambda: state(wid)["state"] == "none" and state(wid)["attributes"].get("reason") == "not_plugged", 30)
        log(bool(ok), "unplugged: no decision (the wallbox keeps doing what it does)", f"{state(wid)['state']} / {state(wid)['attributes'].get('reason')}")
        svc("select", "select_option", {"entity_id": mid, "option": "off"})
        ok = wait_for(lambda: state(wid)["state"] == "off", 30)
        log(bool(ok), "mode off: the sensor says off", state(wid)["state"])
        svc("select", "select_option", {"entity_id": mid, "option": "learn"})
        ok = wait_for(lambda: state(wid)["state"] != "off", 30)
        log(bool(ok), "mode learn again: it decides again", state(wid)["state"])
    text = state("input_text.meldung")["state"].lower()
    log("anstecken" in text or "plug in" in text, "text of the warning", text[:90])
    svc("number", "set_value", {"entity_id": resid, "value": 150})
    time.sleep(6)
    log((num("counter.meldungen") or 0) == 1, "the same warning is not sent twice (same day, same kind)", f"counter {num('counter.meldungen')}")

    # departure in half an hour, plugged in, 26.7 kWh to charge at 11 kW: too late
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    tzv = ZoneInfo("Europe/Vienna")
    svc("input_boolean", "turn_on", {"entity_id": "input_boolean.auto_angesteckt"})
    soon = (datetime.now(tzv) + timedelta(minutes=30)).strftime("%H:%M:00")
    svc("input_datetime", "set_datetime", {"entity_id": "input_datetime.abfahrt", "time": soon})
    ok = wait_for(lambda: state(rdid)["state"] == "too_late", 30)
    log(bool(ok), "departure in 30 minutes: too late", state(rdid)["state"])
    ok = wait_for(lambda: (num("counter.meldungen") or 0) == 2, 30)
    log(bool(ok), "a worse warning is a new one", f"counter {num('counter.meldungen')}")
    log(num("counter.meldungen_2") == num("counter.meldungen"), "both services get every warning (two phones)",
        f"{num('counter.meldungen')} / {num('counter.meldungen_2')}")
    svc("switch", "turn_off", {"entity_id": nid})
    later = (datetime.now(tzv) + timedelta(minutes=20)).strftime("%H:%M:00")
    svc("input_datetime", "set_datetime", {"entity_id": "input_datetime.abfahrt", "time": later})
    time.sleep(8)
    log((num("counter.meldungen") or 0) == 2 and state(rdid)["state"] == "too_late", "warning switched off: nothing sent, sensor still shows it",
        f"counter {num('counter.meldungen')}, {state(rdid)['state']}")
    svc("switch", "turn_on", {"entity_id": nid})
    svc("input_datetime", "set_datetime", {"entity_id": "input_datetime.abfahrt", "time": "07:00:00"})

    # the state of charge is not known (at the start of Home Assistant): no need, no plan, no warning
    n_unknown = num("counter.meldungen") or 0
    svc("input_boolean", "turn_off", {"entity_id": "input_boolean.auto_angesteckt"})
    svc("input_boolean", "turn_on", {"entity_id": "input_boolean.soc_ausfall"})
    ok = wait_for(lambda: state(rdid)["state"] == "unknown", 30)
    log(bool(ok), "state of charge unknown: readiness is unknown", state(rdid)["state"])
    log(state(cid)["state"] in ("unknown", "unavailable") and state(pid)["state"] == "unknown_soc",
        "state of charge unknown: no energy to charge, no plan", f"{state(cid)['state']} / {state(pid)['state']}")
    time.sleep(8)
    log((num("counter.meldungen") or 0) == n_unknown, "state of charge unknown: no warning is sent", f"counter {num('counter.meldungen')}")
    svc("input_boolean", "turn_off", {"entity_id": "input_boolean.soc_ausfall"})
    svc("input_boolean", "turn_on", {"entity_id": "input_boolean.auto_angesteckt"})
    ok = wait_for(lambda: state(rdid)["state"] != "unknown", 30)
    log(bool(ok), "state of charge back: normal again", state(rdid)["state"])

    # the dashboard comes with the integration: a service builds it with this installation's entity ids
    s_d, d_d = api("POST", "/api/services/plugwhen/create_dashboard?return_response", {})
    dash = ((d_d or {}).get("service_response") or {}) if isinstance(d_d, dict) else {}
    text = json.dumps(dash.get("config") or {})
    log(s_d == 200 and "views" in (dash.get("config") or {}) and rdid in text and pid in text and "yaml" in dash,
        "the dashboard service builds the dashboard with this installation's entities", f"{s_d} {len(text)} chars")
    log("evcc_plan" in text and ("Ohne evcc" in text or "Without evcc" in text) and ".sources" in text,
        "the dashboard has the cards 'plan for evcc' (says what happens without evcc) and 'where the data comes from'")
    cards_md = [c for v in (dash.get("config") or {}).get("views", []) for sec in v.get("sections", []) for c in sec.get("cards", [])
                if c.get("type") == "markdown"]
    bad = []
    for c in cards_md:
        sc, body = api("POST", "/api/template", {"template": c["content"]})
        if sc != 200 or "Error" in str(body)[:60] or "UndefinedError" in str(body):
            bad.append(f"{c['content'][:50]!r}: {str(body)[-160:]}")
    log(len(cards_md) >= 12 and not bad, f"all {len(cards_md)} markdown cards of the dashboard render in Home Assistant", "; ".join(bad)[:1200])

    # plug-in times are written down (short flickers under 2 minutes are dropped, the open one counts)
    ok = wait_for(lambda: ((state(rdid)["attributes"].get("plugging") or {}).get("plugged_now") is True), 30)
    plg = state(rdid)["attributes"].get("plugging") or {}
    log(bool(ok) and plg.get("plug_ins", 0) >= 1 and plg.get("recorded_since"), "plug-in times are recorded", json.dumps(plg))
    log(state(pid)["attributes"].get("availability_source") is None, "no solar forecast set up: nothing counts as available (the rest is spread)",
        str(state(pid)["attributes"].get("availability_source")))

    # a state of charge that is too old counts as unknown: a second vehicle with a very short maximum age (about 100 s)
    old_car = {"name": "Altauto", "odometer_entity": "sensor.auto_kilometerstand", "soc_entity": "sensor.auto_ladestand",
               "soc_max_age_h": 0.03, "capacity_kwh": 60, "reserve_km": 100, "consumption_kwh_100": 20,
               "departure_entity": "input_datetime.abfahrt", "charge_kw_max": 11, "charge_kw_min": 1.4}
    res_old, err_old = flow_finish("/api/config/config_entries/subentries/flow", {"handler": [entry_id, "vehicle"]}, old_car)
    log(res_old is not None, "a vehicle with a maximum age of the state of charge is added", err_old)
    old_ready = wait_for(lambda: find("sensor", "altauto_ready_for_departure"), 60)
    log(bool(old_ready), "its readiness sensor exists")
    if old_ready:
        oid = old_ready["entity_id"]
        wait_for(lambda: (state(oid) or {}).get("state") not in (None, "unknown", "unavailable"), 60)  # first computation done
        fresh_attr = (state(oid) or {}).get("attributes", {})
        log(fresh_attr.get("soc_stale") is False and state(oid)["state"] != "unknown", "a fresh state of charge is believed", f"{state(oid)['state']} / {fresh_attr.get('soc_stale')}")
        ok = wait_for(lambda: (state(oid) or {}).get("attributes", {}).get("soc_stale") is True, 540)  # checked at every computation, at the latest every 5 minutes
        log(bool(ok) and state(oid)["state"] == "unknown", "an old state of charge counts as unknown (no plan, no warning)", f"{state(oid)['state']}")
        log(state(rdid)["state"] != "unknown" and (state(rdid)["attributes"].get("soc_stale") is False), "the other vehicle (12 h limit) is not affected", state(rdid)["state"])
        svc("input_number", "set_value", {"entity_id": "input_number.auto_soc", "value": 26})
        ok = wait_for(lambda: (state(oid) or {}).get("attributes", {}).get("soc_stale") is False and state(oid)["state"] != "unknown", 60)
        log(bool(ok), "a new value: believed again", state(oid)["state"])
        svc("input_number", "set_value", {"entity_id": "input_number.auto_soc", "value": 25})

    # ---------- potential calculator ----------
    pot = wait_for(lambda: find("sensor", "testauto_potential"), 60)
    log(bool(pot), "the potential sensor exists")
    if pot:
        ok = wait_for(lambda: state(pot["entity_id"])["state"] == "no_data", 60)
        log(bool(ok), "without a grid counter the potential says: data missing", state(pot["entity_id"])["state"] + " " + str(state(pot["entity_id"])["attributes"].get("missing")))
        s_p, d_p = api("POST", "/api/services/plugwhen/calculate_potential?return_response", {"days": 30})
        resp = (d_p or {}).get("service_response", {}).get("vehicles", {}) if isinstance(d_p, dict) else {}
        log(s_p == 200 and resp.get("Testauto", {}).get("status") == "no_data" and "grid_energy" in (resp.get("Testauto", {}).get("missing") or []),
            "the service answers and names what is missing", str(resp.get("Testauto")))

    # connections: load forecast and availability as options
    svc("input_number", "set_value", {"entity_id": "input_number.auto_soc", "value": 25})   # (33.3 - 25) % of 60 kWh / 0.9 = 5.5 kWh
    svc("number", "set_value", {"entity_id": resid, "value": 100})
    s, d = api("POST", "/api/config/config_entries/options/flow", {"handler": entry_id})
    s2, d2 = api("POST", f"/api/config/config_entries/options/flow/{d['flow_id']}",
                 {"load_entity": "sensor.test_last", "availability_entity": "sensor.test_verfuegbar",
                  "grid_energy_entity": "sensor.netz_zaehler", "price_low": 33.82, "price_high": 67.64, "price_threshold": 10})
    log(s == 200 and d.get("type") == "form" and d2.get("type") == "create_entry", "connections can be set in the options", f"{d.get('type')} / {d2.get('type')}")
    ok = wait_for(lambda: ((state(pid) or {}).get("attributes") or {}).get("availability_used") is True, 90)
    pa = (state(pid) or {}).get("attributes") or {}
    log(bool(ok) and pa.get("load_forecast_used") is True, "load forecast and availability are used",
        json.dumps({k: pa.get(k) for k in ("load_forecast_used", "availability_used")}))
    if ok:
        log(abs(pa["available_kwh"] - pa["needed_kwh"]) < 0.3 and pa["grid_kwh"] < 0.3, "the plan uses the available power first",
            f"needed {pa['needed_kwh']} available {pa['available_kwh']} grid {pa['grid_kwh']}")
        starts = [datetime.fromisoformat(w["start"]).astimezone(tzv) for w in pa["windows"]]
        ends = [datetime.fromisoformat(w["end"]).astimezone(tzv) for w in pa["windows"]]
        a0 = datetime.now(tzv).replace(minute=0, second=0, microsecond=0) + timedelta(hours=2)
        log(all(a0 <= s0 and e0 <= a0 + timedelta(hours=3) for s0, e0 in zip(starts, ends)), "all windows lie inside the availability window",
            str([x.strftime("%H:%M") for x in starts]))

    if pot:
        s_p, d_p = api("POST", "/api/services/plugwhen/calculate_potential?return_response", {"days": 30})
        resp = (d_p or {}).get("service_response", {}).get("vehicles", {}) if isinstance(d_p, dict) else {}
        log(s_p == 200 and resp.get("Testauto", {}).get("status") == "too_little_data",
            "with all entities but no history yet: too little data (no made-up numbers)", str(resp.get("Testauto")))
        ok = wait_for(lambda: state(pot["entity_id"])["state"] == "too_little_data", 30)
        log(bool(ok), "the potential sensor shows it", state(pot["entity_id"])["state"])

    wk = state(week["entity_id"])
    log(isinstance(wk["attributes"].get("week"), list) and len(wk["attributes"]["week"]) == 7, "weekly plan has seven days", str(wk["state"]))
    log("history_error" in wk["attributes"], "history state is reported", str(wk["attributes"].get("history_error")))

    # ---------- restart: settings are restored ----------
    svc("switch", "turn_off", {"entity_id": lid})
    if mode_s:
        svc("select", "select_option", {"entity_id": mid, "option": "off"})
    time.sleep(2)
    subprocess.run(["docker", "restart", CONTAINER], check=False, capture_output=True)
    time.sleep(20)
    log(bool(wait_api(300)), "Home Assistant is back after the restart")
    ok = wait_for(lambda: num(resid) is not None, 120)
    log(bool(ok) and num(resid) == 100.0, "reserve is restored (the value set last)", str(num(resid)))
    log(state(lid)["state"] == "off", "learning switch state is restored (off)")
    if mode_s:
        ok = wait_for(lambda: (state(mid) or {}).get("state") == "off", 30)
        log(bool(ok), "the mode is restored after the restart (off, as chosen)", str((state(mid) or {}).get("state")))
    ok = wait_for(lambda: (state(rdid)["attributes"].get("plugging") or {}).get("recorded_since") is not None, 60)
    plg2 = state(rdid)["attributes"].get("plugging") or {}
    log(bool(ok) and plg2.get("recorded_since") == plg.get("recorded_since") and plg2.get("plug_ins", 0) >= plg.get("plug_ins", 0),
        "the plug-in times survive the restart", f"{plg.get('recorded_since')} -> {plg2.get('recorded_since')}, {plg2.get('plug_ins')}")
    n_before = num("counter.meldungen") or 0
    time.sleep(70)
    log((num("counter.meldungen") or 0) == n_before, "after the restart the same warning is not repeated", f"counter {num('counter.meldungen')} (before {n_before})")

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
