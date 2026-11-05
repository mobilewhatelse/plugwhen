"""One-off: installation test for the age check of the state of charge (kept for the record)."""
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "tests" / "install" / "itest.py"
s = p.read_text(encoding="utf-8")
a = '''    # connections: load forecast and availability as options'''
assert s.count(a) == 1
s = s.replace(a, '''    # a state of charge that is too old counts as unknown: a second vehicle with a very short maximum age (about 100 s)
    old_car = {"name": "Altauto", "odometer_entity": "sensor.auto_kilometerstand", "soc_entity": "sensor.auto_ladestand",
               "soc_max_age_h": 0.03, "capacity_kwh": 60, "reserve_km": 100, "consumption_kwh_100": 20,
               "departure_entity": "input_datetime.abfahrt", "charge_kw_max": 11, "charge_kw_min": 1.4}
    res_old, err_old = it_flow = flow_finish("/api/config/config_entries/subentries/flow", {"handler": [entry_id, "vehicle"]}, old_car)
    log(res_old is not None, "a vehicle with a maximum age of the state of charge is added", err_old)
    old_ready = wait_for(lambda: find("sensor", "altauto_ready_for_departure"), 60)
    log(bool(old_ready), "its readiness sensor exists")
    if old_ready:
        oid = old_ready["entity_id"]
        fresh_attr = (state(oid) or {}).get("attributes", {})
        log(fresh_attr.get("soc_stale") is False and state(oid)["state"] != "unknown", "a fresh state of charge is believed", f"{state(oid)['state']} / {fresh_attr.get('soc_stale')}")
        ok = wait_for(lambda: (state(oid) or {}).get("attributes", {}).get("soc_stale") is True, 300)
        log(bool(ok) and state(oid)["state"] == "unknown", "an old state of charge counts as unknown (no plan, no warning)", f"{state(oid)['state']}")
        log(state(rdid)["state"] != "unknown" and (state(rdid)["attributes"].get("soc_stale") is False), "the other vehicle (12 h limit) is not affected", state(rdid)["state"])
        svc("input_number", "set_value", {"entity_id": "input_number.auto_soc", "value": 26})
        ok = wait_for(lambda: (state(oid) or {}).get("attributes", {}).get("soc_stale") is False and state(oid)["state"] != "unknown", 60)
        log(bool(ok), "a new value: believed again", state(oid)["state"])
        svc("input_number", "set_value", {"entity_id": "input_number.auto_soc", "value": 25})

''' + a)
p.write_text(s, encoding="utf-8")
print("ok")
