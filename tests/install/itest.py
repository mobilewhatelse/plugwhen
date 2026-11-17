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


def notification(nid):
    """Message of a persistent notification (only over the websocket since HA 2023.6), or None."""
    from websockets.sync.client import connect

    with connect(BASE.replace("http", "ws") + "/api/websocket", max_size=None) as ws:
        ws.recv()
        ws.send(json.dumps({"type": "auth", "access_token": TOKEN}))
        if json.loads(ws.recv()).get("type") != "auth_ok":
            return None
        ws.send(json.dumps({"id": 1, "type": "persistent_notification/get"}))
        for _ in range(5):
            m = json.loads(ws.recv())
            if m.get("id") == 1 and m.get("type") == "result":
                for n in m.get("result") or []:
                    if n.get("notification_id") == nid:
                        return n.get("message")
                return None
    return None


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
    """Runs a flow to its end: every form gets the values of `user_input` it has fields for (the rest stay at their defaults);
    a menu takes `user_input["_menu"]` or else "finish"."""
    s, d = api("POST", path, init_body)
    if s != 200:
        return None, f"init {s} {d}"
    for _ in range(12):
        if d.get("type") == "create_entry":
            return d, ""
        if d.get("type") == "abort":
            return None, f"abort {d.get('reason')}"
        if d.get("type") == "menu":
            opts = list(d.get("menu_options") or [])
            pick = user_input.get("_menu") if user_input.get("_menu") in opts else ("finish" if "finish" in opts else opts[-1])
            s, d = api("POST", f"{path}/{d['flow_id']}", {"next_step_id": pick})
        elif d.get("type") == "form":
            names = {f.get("name") for f in (d.get("data_schema") or [])}
            s, d = api("POST", f"{path}/{d['flow_id']}", {k: v for k, v in user_input.items() if k in names})
        else:
            return None, f"unexpected {d.get('type')}"
        if s != 200:
            return None, f"step {s} {d}"
        if d.get("errors"):
            return None, f"errors {d['errors']}"
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
    # the assistant: what is there -> cars (menu) -> a car form with odometer and state of charge
    log({"guard", "evcc"} <= set((d.get("description_placeholders") or {})), "assistant step 1 says what was found (guard, evcc)", str(d.get("description_placeholders")))
    s, d = api("POST", f"/api/config/config_entries/flow/{d['flow_id']}", {})
    opts = list(d.get("menu_options") or [])
    log(d.get("type") == "menu" and d.get("step_id") == "cars" and {"add_car", "finish"} <= set(opts), "assistant step 2: cars menu (add a car, finish)", f"{d.get('type')} {opts}")
    s, d = api("POST", f"/api/config/config_entries/flow/{d['flow_id']}", {"next_step_id": "add_car"})
    car_fields = {f.get("name") for f in (d.get("data_schema") or [])}
    log(d.get("step_id") == "add_car" and {"odometer_entity", "soc_entity"} <= car_fields or (d.get("step_id") == "add_car" and len(car_fields) > 5),
        "assistant: car form with odometer and state of charge", str(sorted(car_fields))[:200])
    api("DELETE", f"/api/config/config_entries/flow/{d['flow_id']}")
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
    log(len(ents) == 25, "entities of the vehicle exist (25 with 'ready to switch', the weekly full charge and its seven day switches)",
        f"{len(ents)}: " + ", ".join(sorted(e["entity_id"].split(".")[1] for e in ents)))
    wf = find("switch", "once_a_week_full")
    wt = find("number", "target_of_the_weekly")
    day_names = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
    days = [find("switch", f"weekly_full_charge_on_{d}") for d in day_names]
    log(bool(wf and wf["state"] == "off" and wt and float(wt["state"]) == 100 and all(days)
             and [x["state"] for x in days] == ["off"] * 5 + ["on"] * 2),
        "weekly full charge: off by default, day bar Saturday and Sunday, 100 %",
        str([(x or {}).get("state") for x in days]) + " " + str([(x or {}).get("entity_id") for x in (wf, wt)]))
    log(find("select", "days_for_the_weekly") is None, "the former day selection is gone")
    if days[2]:   # tap Wednesday on and off again
        svc("switch", "turn_on", {"entity_id": days[2]["entity_id"]})
        on = wait_for(lambda: (state(days[2]["entity_id"]) or {}).get("state") == "on", 20)
        svc("switch", "turn_off", {"entity_id": days[2]["entity_id"]})
        off = wait_for(lambda: (state(days[2]["entity_id"]) or {}).get("state") == "off", 20)
        log(bool(on and off), "a day of the bar can be tapped on and off")
    if wf:   # switched on: the plan counts it (the car is full, or a day is chosen, or none is left this week)
        svc("switch", "turn_on", {"entity_id": wf["entity_id"]})
        ok = wait_for(lambda: (state(wf["entity_id"]) or {}).get("state") == "on"
                      and "done_week" in ((state(wf["entity_id"]) or {}).get("attributes") or {}), 30)
        a = (state(wf["entity_id"]) or {}).get("attributes") or {}
        log(bool(ok), "weekly full charge: switch on, its state tells day, active and done", str({k: a.get(k) for k in ("day", "active", "done_week")}))
        svc("switch", "turn_off", {"entity_id": wf["entity_id"]})
    charge = find("sensor", "energy_to_charge")
    if charge:   # 0.10: the reserve is left after the trip (default), and the sensor tells must and the charge ahead
        a = (state(charge["entity_id"]) or {}).get("attributes", {})
        log("must_soc" in a and "ahead" in a, "need sensor tells the target of the next trip and the charge ahead",
            str({k: a.get(k) for k in ("target_soc", "must_soc", "ahead")}))
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
    main = states_like("plugwhen_")
    share = [e for e in main if e["entity_id"].startswith("switch.") and "share_anonymous_data" in e["entity_id"]]
    log(len(share) == 1 and share[0]["state"] == "off", "share anonymous data: switch there and off (only with consent)", str([(e["entity_id"], e["state"]) for e in main]))
    fb = [e["entity_id"] for e in main if e["entity_id"].startswith(("text.", "button.")) and "feedback" in e["entity_id"]]
    log(len(fb) == 2, "feedback: text field and button there", str(fb))
    rep = [e["entity_id"] for e in main if e["entity_id"].startswith("button.") and "bug_report" in e["entity_id"]]
    log(len(rep) == 1, "bug report: button there", str([e["entity_id"] for e in main]))
    if rep:   # the test container cannot reach the real server (--add-host): the notification shows what would have been sent
        svc("button", "press", {"entity_id": rep[0]})
        msg = wait_for(lambda: notification("plugwhen_feedback"), 30, 2) or ""
        log("would have been sent" in msg and "Testauto" not in msg and "sensor.auto_" not in msg and "Home Assistant" in msg
            and "Auto 1" in msg, "bug report: one press builds it; without the car's name or entity ids", msg[:400])
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
    log(bool(modes) and all("direct" not in ((e.get("attributes") or {}).get("options") or []) for e in modes),
        "the mode 'direct' is not offered before the learn mode is through (and without a controllable wallbox)")
    # state of charge 40 %, reserve 100 km, 20 kWh/100 km, 60 kWh: target 33.3 %, nothing to charge
    log(num(cid) == 0.0 and abs((num(tid) or 0) - 33.3) < 0.2 and num(rid) == 100.0,
        "enough charge: 100 km, target 33 %, charge 0 kWh", f"{num(cid)} / {num(tid)} / {num(rid)}")
    log(state(lid)["state"] == "on", "kilometre learning is on by default")
    ca, pa0 = state(cid)["attributes"], state(pid)["attributes"]
    log(abs((ca.get("efficiency") or 0) - 0.889) < 0.002 and ca.get("efficiency_learned") is False and pa0.get("solar_deduct_source") == "default" and pa0.get("pref_kw") == 4.0,
        "house numbers start as defaults (efficiency, solar deduction, preferred power) and say so",
        f"eff {ca.get('efficiency')} learned {ca.get('efficiency_learned')} deduct {pa0.get('solar_deduct_source')} pref {pa0.get('pref_kw')}")
    log(num(resid) == 100.0, "reserve starts at the value of the set-up")

    # a low battery: 10 % -> (33.3 - 10) % of 60 kWh / 0.889 = 15.7 kWh (start value of the charge loss at the preferred 4 kW;
    # recomputed when a setting changes)
    svc("input_number", "set_value", {"entity_id": "input_number.auto_soc", "value": 10})
    time.sleep(3)
    svc("switch", "turn_off", {"entity_id": lid})
    svc("switch", "turn_on", {"entity_id": lid})
    ok = wait_for(lambda: abs((num(cid) or 0) - 15.7) < 0.2, 30)
    log(bool(ok), "low battery: 15.7 kWh to charge", str(num(cid)))
    a = state(cid)["attributes"]
    log(a.get("plugged") is False and a.get("soc") == 10.0 and a.get("source") == "reserve", "attributes: plug, state of charge, source",
        json.dumps({k: a.get(k) for k in ("plugged", "soc", "source")}))

    # reserve 150 km = 30 kWh = 50 %: (50 - 10) % of 60 kWh / 0.889 = 27.0 kWh
    svc("number", "set_value", {"entity_id": resid, "value": 150})
    ok = wait_for(lambda: abs((num(cid) or 0) - 27.0) < 0.2, 30)
    log(bool(ok), "reserve 150 km: 27.0 kWh to charge", str(num(cid)))

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
    log(abs(pa["needed_kwh"] - 27.0) < 0.3 and abs(pa["planned_kwh"] - pa["needed_kwh"]) < 0.3 and len(pa["windows"]) >= 1,
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

    # departure in half an hour, plugged in, 27.0 kWh to charge at 11 kW: too late
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
    text = json.dumps(dash)
    log(s_d == 200 and list(dash) == ["views"] and rdid in text and pid in text,
        "the dashboard service builds the dashboard with this installation's entities", f"{s_d} {len(text)} chars")
    log("evcc_plan" in text and ("Ohne evcc" in text or "Without evcc" in text) and ".sources" in text,
        "the dashboard has the cards 'plan for evcc' (says what happens without evcc) and 'where the data comes from'")
    log("repository=viertelstunden-waechter" in text,
        "without the quarter-hour peak guard the dashboard has the card 'Goes well with: Viertelstunden-Waechter' (link to the marketplace)")
    cards_md = [c for v in dash.get("views", []) for sec in v.get("sections", []) for c in sec.get("cards", [])
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
    svc("input_number", "set_value", {"entity_id": "input_number.auto_soc", "value": 25})   # (33.3 - 25) % of 60 kWh / 0.889 = 5.6 kWh
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

    # ---------- several cars and wallboxes ----------
    def wins(eid):
        a = (state(eid) or {}).get("attributes") or {}
        return [(datetime.fromisoformat(w["start"]), datetime.fromisoformat(w["end"]), float(w["peak_kw"])) for w in a.get("windows") or []]

    def overlaps(a, b):
        return [(x, y) for x in a for y in b if x[0] < y[1] and y[0] < x[1]]

    def sun_kw(t):
        """The available power of the test (sensor.test_verfuegbar, 5 kW for three hours) at time t."""
        fc = ((state("sensor.test_verfuegbar") or {}).get("attributes") or {}).get("forecast") or []
        return sum(float(f["kw"]) for f in fc if datetime.fromisoformat(f["start"]) <= t < datetime.fromisoformat(f["end"]))

    base2 = {"odometer_entity": "sensor.auto_kilometerstand", "capacity_kwh": 60, "reserve_km": 100, "consumption_kwh_100": 20,
             "plugged_entity": "binary_sensor.auto_stecker", "departure_entity": "input_datetime.abfahrt", "charge_kw_max": 11, "charge_kw_min": 1.4}
    r2, e2 = flow_finish("/api/config/config_entries/subentries/flow", {"handler": [entry_id, "vehicle"]},
                         dict(base2, name="Zweitauto", soc_entity="sensor.auto2_ladestand", wallbox_energy_entity="sensor.wallbox_zaehler"))
    log(r2 is not None, "a second car at the same wallbox is added", e2)
    z = wait_for(lambda: find("sensor", "zweitauto_charge_plan"), 60)
    zid = z["entity_id"] if z else None
    ok = wait_for(lambda: zid and state(zid)["state"] in ("planned", "infeasible") and wins(zid) and wins(pid), 180)
    zw, tw = (wins(zid), wins(pid)) if zid else ([], [])
    log(bool(ok) and not overlaps(zw, tw), "two cars at one wallbox are never planned at the same time",
        f"{[(a.strftime('%H:%M'), b.strftime('%H:%M')) for a, b, _ in tw]} / {[(a.strftime('%H:%M'), b.strftime('%H:%M')) for a, b, _ in zw]}")
    za = (state(zid) or {}).get("attributes") or {} if zid else {}
    log(za.get("wallbox") == "sensor.wallbox_zaehler" and (za.get("other_cars_kwh") or 0) > 0,
        "the second car sees the plan of the first and its wallbox", json.dumps({k: za.get(k) for k in ("wallbox", "other_cars_kwh")}))
    # from the grid (outside the sun) at least 0.75 x the maximum, apart from one remainder quarter; with sun it follows the sun
    grid_w = [p for a, _, p in zw if sun_kw(a) <= 0]
    log(bool(zw) and sum(1 for p in grid_w if p < 0.75 * 11 - 0.05) <= 1, "at a shared wallbox it charges compactly from the grid (so both fit into the night)",
        str([(a.strftime("%H:%M"), p, sun_kw(a)) for a, _, p in zw]))

    r3, e3 = flow_finish("/api/config/config_entries/subentries/flow", {"handler": [entry_id, "vehicle"]},
                         dict(base2, name="Drittauto", soc_entity="sensor.auto3_ladestand", wallbox_energy_entity="sensor.wallbox_2_zaehler",
                              more_wallbox_energy_entities=["sensor.wallbox_3_zaehler"]))
    log(r3 is not None, "a third car with two wallboxes of its own is added", e3)
    d3s = wait_for(lambda: find("sensor", "drittauto_charge_plan"), 60)
    did = d3s["entity_id"] if d3s else None
    ok = wait_for(lambda: did and state(did)["state"] in ("planned", "infeasible") and wins(did), 180)
    log(bool(ok) and state(did)["attributes"].get("wallbox") == "sensor.wallbox_2_zaehler", "without a rising counter its first wallbox counts",
        str(state(did)["attributes"].get("wallbox") if did else None))
    # the peak target (9.5 kW, house 1.0 kW): the grid import of house and all cars (minus the sun) never above it, at no time
    worst = 0.0
    if ok:
        allw = wins(pid) + wins(zid) + wins(did)
        t = min(a for a, _, _ in allw)
        while t < max(b for _, b, _ in allw):
            worst = max(worst, max(0.0, 1.0 + sum(p for a, b, p in allw if a <= t < b) - sun_kw(t)))
            t += timedelta(minutes=15)
    log(bool(ok) and worst <= 9.5 + 0.3, "all cars together stay under the peak target (grid import)", f"highest {worst:.2f} kW")
    svc("input_number", "set_value", {"entity_id": "input_number.wb3_kwh", "value": 301.5})   # the car charges at its second wallbox
    ok = wait_for(lambda: state(did)["attributes"].get("wallbox") == "sensor.wallbox_3_zaehler", 420)
    log(bool(ok), "the wallbox whose counter rises while the car is plugged in is found", str(state(did)["attributes"].get("wallbox") if did else None))

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

    logs = subprocess.run(["docker", "logs", CONTAINER], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace").stdout
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
