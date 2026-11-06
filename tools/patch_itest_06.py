"""One-off: installation test for the potential calculator (kept for the record)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "tests" / "install"

c = ROOT / "config" / "configuration.yaml"
y = c.read_text(encoding="utf-8")
a = '''      - name: Wallbox Zaehler'''
assert y.count(a) == 1
y = y.replace(a, '''      - name: Netz Zaehler
        unique_id: netz_zaehler
        unit_of_measurement: kWh
        device_class: energy
        state_class: total_increasing
        state: "5000"
''' + a)
c.write_text(y, encoding="utf-8")

p = ROOT / "itest.py"
s = p.read_text(encoding="utf-8")


def rep(a, b):
    global s
    assert s.count(a) == 1, a[:70]
    s = s.replace(a, b)


rep('log(len(ents) == 10, "entities of the vehicle exist"', 'log(len(ents) == 11, "entities of the vehicle exist"')
rep('''    # connections: load forecast and availability as options''', '''    # ---------- potential calculator ----------
    pot = wait_for(lambda: find("sensor", "testauto_potential"), 60)
    log(bool(pot), "the potential sensor exists")
    if pot:
        ok = wait_for(lambda: state(pot["entity_id"])["state"] == "no_data", 60)
        log(bool(ok), "without a grid counter the potential says: data missing", state(pot["entity_id"])["state"] + " " + str(state(pot["entity_id"])["attributes"].get("missing")))
        s_p, d_p = api("POST", "/api/services/plugwhen/calculate_potential?return_response", {"days": 30})
        resp = (d_p or {}).get("service_response", {}).get("vehicles", {}) if isinstance(d_p, dict) else {}
        log(s_p == 200 and resp.get("Testauto", {}).get("status") == "no_data" and "grid_energy" in (resp.get("Testauto", {}).get("missing") or []),
            "the service answers and names what is missing", str(resp.get("Testauto")))

    # connections: load forecast and availability as options''')
rep('''                 {"load_entity": "sensor.test_last", "availability_entity": "sensor.test_verfuegbar"})''',
    '''                 {"load_entity": "sensor.test_last", "availability_entity": "sensor.test_verfuegbar",
                  "grid_energy_entity": "sensor.netz_zaehler", "price_low": 33.82, "price_high": 67.64, "price_threshold": 10})''')
rep('''    wk = state(week["entity_id"])''', '''    if pot:
        s_p, d_p = api("POST", "/api/services/plugwhen/calculate_potential?return_response", {"days": 30})
        resp = (d_p or {}).get("service_response", {}).get("vehicles", {}) if isinstance(d_p, dict) else {}
        log(s_p == 200 and resp.get("Testauto", {}).get("status") == "too_little_data",
            "with all entities but no history yet: too little data (no made-up numbers)", str(resp.get("Testauto")))
        ok = wait_for(lambda: state(pot["entity_id"])["state"] == "too_little_data", 30)
        log(bool(ok), "the potential sensor shows it", state(pot["entity_id"])["state"])

    wk = state(week["entity_id"])''')
p.write_text(s, encoding="utf-8")
print("ok")
