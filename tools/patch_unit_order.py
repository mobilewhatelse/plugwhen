"""One-off: 'the same sensor twice' is reported before a unit problem (kept for the record)."""
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen" / "config_flow.py"
s = p.read_text(encoding="utf-8", newline="")
crlf = "\r\n" in s
s = s.replace("\r\n", "\n")
a = '''            errors = unit_errors(self.hass.states.get, user_input, VEHICLE_UNITS)
            if errors:
                pass
            elif user_input[V_ODOMETER] == user_input[V_SOC]:
                errors[V_SOC] = "same_entity"
'''
b = '''            if user_input[V_ODOMETER] == user_input[V_SOC]:
                errors[V_SOC] = "same_entity"
            else:
                errors = unit_errors(self.hass.states.get, user_input, VEHICLE_UNITS)
            if errors:
                pass
'''
assert s.count(a) == 1
s = s.replace(a, b)
if crlf:
    s = s.replace("\n", "\r\n")
p.write_text(s, encoding="utf-8", newline="")
print("ok")
