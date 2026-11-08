"""One-off: version 0.7.3, any sensor with the right unit can be chosen (kept for the record)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "CHANGELOG.md"
s = p.read_text(encoding="utf-8", newline="")
crlf = "\r\n" in s
s = s.replace("\r\n", "\n")
a = "# Changelog\n"
assert s.count(a) == 1
s = s.replace(a, """# Changelog

## 0.7.3 (unreleased) - any sensor with the right unit

- **Odometer, state of charge, wallbox energy counter and grid energy can be any sensor**, also a template sensor without a device class.
  Before, such sensors were missing from the list (the same problem was reported for the peak guard). Instead of the device class the dialog
  now checks the **unit** when saving (kilometres or miles; percent; Wh, kWh or MWh) and says what to add if it does not fit.
  A sensor without any unit is accepted where Plugwhen assumes one (kilometres, percent, kWh).
""", 1)
if crlf:
    s = s.replace("\n", "\r\n")
p.write_text(s, encoding="utf-8", newline="")
m = ROOT / "custom_components" / "plugwhen" / "manifest.json"
d = json.loads(m.read_text(encoding="utf-8"))
d["version"] = "0.7.3"
m.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("ok")
