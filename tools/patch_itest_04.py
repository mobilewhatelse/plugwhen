"""One-off: adds the unknown-state-of-charge check to the installation test (kept for the record)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "tests" / "install"

c = ROOT / "config" / "configuration.yaml"
y = c.read_text(encoding="utf-8")
a = '''        state: "{{ states('input_number.auto_soc') | float(0) }}"'''
assert y.count(a) == 1
y = y.replace(a, '''        state: "{{ 'unknown' if is_state('input_boolean.soc_ausfall', 'on') else states('input_number.auto_soc') | float(0) }}"''')
y = y.replace('''input_boolean:
  auto_angesteckt:''', '''input_boolean:
  soc_ausfall:
    name: Ladestand faellt aus
    initial: false
  auto_angesteckt:''', 1)
c.write_text(y, encoding="utf-8")

p = ROOT / "itest.py"
s = p.read_text(encoding="utf-8")
a = '''    # connections: load forecast and availability as options'''
assert s.count(a) == 1
s = s.replace(a, '''    # the state of charge is not known (at the start of Home Assistant): no need, no plan, no warning
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

''' + a)
p.write_text(s, encoding="utf-8")
print("ok")
