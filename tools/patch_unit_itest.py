"""One-off: installation test for the unit check (kept for the record)."""
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "tests" / "install" / "itest.py"
s = p.read_text(encoding="utf-8", newline="")
crlf = "\r\n" in s
s = s.replace("\r\n", "\n")
a = '''    s, d = api("POST", "/api/config/config_entries/subentries/flow", {"handler": [entry_id, "vehicle"]})
    s2, d2 = api("POST", f"/api/config/config_entries/subentries/flow/{d['flow_id']}", dict(car, soc_entity="sensor.auto_kilometerstand"))
'''
b = '''    s, d = api("POST", "/api/config/config_entries/subentries/flow", {"handler": [entry_id, "vehicle"]})
    fields = {f.get("name"): f for f in (d.get("data_schema") or [])}
    sels = {k: ((fields.get(k) or {}).get("selector") or {}).get("entity") or {} for k in ("odometer_entity", "soc_entity", "wallbox_energy_entity")}
    log(all(v and "device_class" not in str(v) for v in sels.values()), "odometer, state of charge and wallbox counter do not filter by device class", str(sels))
    s3, d3 = api("POST", f"/api/config/config_entries/subentries/flow/{d['flow_id']}", dict(car, odometer_entity="sensor.wallbox_zaehler"))
    log(s3 == 200 and (d3.get("errors") or {}).get("odometer_entity") == "not_distance", "a sensor with a wrong unit (kWh as odometer) is refused with a clear error", str(d3.get("errors")))
    s2, d2 = api("POST", f"/api/config/config_entries/subentries/flow/{d['flow_id']}", dict(car, soc_entity="sensor.auto_kilometerstand"))
'''
assert s.count(a) == 1
s = s.replace(a, b)
if crlf:
    s = s.replace("\n", "\r\n")
p.write_text(s, encoding="utf-8", newline="")
print("ok")
