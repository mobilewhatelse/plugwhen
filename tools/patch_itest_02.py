"""One-off: extends the installation test and its configuration for version 0.2 (kept for the record)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "tests" / "install"

p = ROOT / "config" / "configuration.yaml"
s = p.read_text(encoding="utf-8")
if "notify_sink" not in s:
    s = s.replace('''input_boolean:
  auto_angesteckt:
    name: Auto angesteckt
    initial: false
''', '''input_boolean:
  auto_angesteckt:
    name: Auto angesteckt
    initial: false

input_datetime:
  abfahrt:
    name: Abfahrt
    has_date: false
    has_time: true
    initial: "07:00:00"

input_text:
  meldung:
    name: Letzte Meldung
    max: 255

counter:
  meldungen:
    name: Meldungen

# the warning goes through this script (stands in for a notify service)
script:
  notify_sink:
    alias: Notify sink
    fields:
      title: {}
      message: {}
    sequence:
      - action: counter.increment
        target:
          entity_id: counter.meldungen
      - action: input_text.set_value
        target:
          entity_id: input_text.meldung
        data:
          value: "{{ message | truncate(250) }}"
''')
    s += '''  - sensor:
      - name: Test Last
        unique_id: test_last
        state: "1"
        attributes:
          target_kw: 9.5
          hours: >
            {% set ns = namespace(l=[]) %}
            {% for i in range(0, 30) %}
              {% set t = (now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=i)).isoformat() %}
              {% set ns.l = ns.l + [{'t': t, 'typical': 0.4, 'high': 1.0}] %}
            {% endfor %}
            {{ ns.l }}
      - name: Test Verfuegbar
        unique_id: test_avail
        state: "1"
        attributes:
          schema: 1
          valid_until: "{{ (now() + timedelta(hours=6)).isoformat() }}"
          forecast: >
            {% set s = now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=2) %}
            {{ [{'start': s.isoformat(), 'end': (s + timedelta(hours=3)).isoformat(), 'kw': 5.0}] }}
'''
    p.write_text(s, encoding="utf-8")

p = ROOT / "itest.py"
s = p.read_text(encoding="utf-8")


def rep(a, b):
    global s
    assert s.count(a) == 1, a[:60]
    s = s.replace(a, b)


rep('''           "plugged_entity": "binary_sensor.auto_stecker", "wallbox_energy_entity": "sensor.wallbox_zaehler"}''',
    '''           "plugged_entity": "binary_sensor.auto_stecker", "wallbox_energy_entity": "sensor.wallbox_zaehler",
           "departure_entity": "input_datetime.abfahrt", "charge_kw_max": 11, "charge_kw_min": 1.4,
           "notify_service": "script.notify_sink", "notify_hour": 0}''')
rep('log(len(ents) == 7, "entities of the vehicle exist"', 'log(len(ents) == 10, "entities of the vehicle exist"')
rep('''    week = find("sensor", "learned_days")
    log(all([charge, rng, soc_t, reserve, learn, week]), "all kinds of entities are there")
    if not all([charge, rng, soc_t, reserve, learn, week]):
        return''', '''    week = find("sensor", "learned_days")
    plan_s = find("sensor", "charge_plan")
    ready_s = find("sensor", "ready_for_departure")
    notice_sw = find("switch", "warn_when")
    everything = [charge, rng, soc_t, reserve, learn, week, plan_s, ready_s, notice_sw]
    log(all(everything), "all kinds of entities are there")
    if not all(everything):
        return
    pid, rdid, nid = plan_s["entity_id"], ready_s["entity_id"], notice_sw["entity_id"]''')
rep('''    wk = state(week["entity_id"])''', '''    # ---------- plan and warning (0.2) ----------
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
    n0 = num("counter.meldungen") or 0
    svc("input_boolean", "turn_off", {"entity_id": "input_boolean.auto_angesteckt"})
    ok = wait_for(lambda: state(rdid)["state"] == "plug_in", 30)
    log(bool(ok), "unplugged: readiness says plug in", state(rdid)["state"])
    ok = wait_for(lambda: (num("counter.meldungen") or 0) == n0 + 1, 30)
    log(bool(ok), "the warning was sent once", f"counter {num('counter.meldungen')}")
    text = state("input_text.meldung")["state"].lower()
    log("anstecken" in text or "plug in" in text, "text of the warning", text[:90])
    svc("number", "set_value", {"entity_id": resid, "value": 150})
    time.sleep(6)
    log((num("counter.meldungen") or 0) == n0 + 1, "the same warning is not sent twice", f"counter {num('counter.meldungen')}")

    # departure in half an hour, plugged in, 26.7 kWh to charge at 11 kW: too late
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    tzv = ZoneInfo("Europe/Vienna")
    svc("input_boolean", "turn_on", {"entity_id": "input_boolean.auto_angesteckt"})
    soon = (datetime.now(tzv) + timedelta(minutes=30)).strftime("%H:%M:00")
    svc("input_datetime", "set_datetime", {"entity_id": "input_datetime.abfahrt", "time": soon})
    ok = wait_for(lambda: state(rdid)["state"] == "too_late", 30)
    log(bool(ok), "departure in 30 minutes: too late", state(rdid)["state"])
    ok = wait_for(lambda: (num("counter.meldungen") or 0) == n0 + 2, 30)
    log(bool(ok), "a worse warning is a new one", f"counter {num('counter.meldungen')}")
    svc("switch", "turn_off", {"entity_id": nid})
    later = (datetime.now(tzv) + timedelta(minutes=20)).strftime("%H:%M:00")
    svc("input_datetime", "set_datetime", {"entity_id": "input_datetime.abfahrt", "time": later})
    time.sleep(8)
    log((num("counter.meldungen") or 0) == n0 + 2 and state(rdid)["state"] == "too_late", "warning switched off: nothing sent, sensor still shows it")
    svc("switch", "turn_on", {"entity_id": nid})
    svc("input_datetime", "set_datetime", {"entity_id": "input_datetime.abfahrt", "time": "07:00:00"})

    # connections: load forecast and availability as options
    svc("input_number", "set_value", {"entity_id": "input_number.auto_soc", "value": 25})   # (33.3 - 25) % of 60 kWh / 0.9 = 5.5 kWh
    svc("number", "set_value", {"entity_id": resid, "value": 100})
    s, d = api("POST", "/api/config/config_entries/options/flow", {"handler": entry_id})
    s2, d2 = api("POST", f"/api/config/config_entries/options/flow/{d['flow_id']}",
                 {"load_entity": "sensor.test_last", "availability_entity": "sensor.test_verfuegbar"})
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

    wk = state(week["entity_id"])''')
rep('''    log(state(lid)["state"] == "off", "learning switch state is restored (off)")''', '''    log(state(lid)["state"] == "off", "learning switch state is restored (off)")
    n_before = num("counter.meldungen") or 0
    time.sleep(70)
    log((num("counter.meldungen") or 0) == n_before, "after the restart the same warning is not repeated", f"counter {num('counter.meldungen')} (before {n_before})")''')
p.write_text(s, encoding="utf-8")
print("ok")
