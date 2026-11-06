"""One-off: the sensor 'would switch' (kept for the record)."""
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen" / "sensor.py"
s = p.read_text(encoding="utf-8")


def rep(a, b):
    global s
    assert s.count(a) == 1, a[:60]
    s = s.replace(a, b)


rep("from .const import PLAN_STATES, POTENTIAL_STATES, READINESS_STATES", "from .const import PLAN_STATES, POTENTIAL_STATES, READINESS_STATES, WOULD_STATES")
rep("            PotentialSensor(plug, v),\n", "            PotentialSensor(plug, v),\n            WouldSwitchSensor(plug, v),\n")
s += '''

class WouldSwitchSensor(PlugwhenEntity, SensorEntity):
    """Learn mode: what Plugwhen WOULD do right now (charge, pause, none = no decision, off = mode off). Nothing is switched.
    The attributes give the reason, when it is expected to change, the journal of the last decisions and how they compare with
    what the wallbox really did over the last days."""

    _unrecorded_attributes = frozenset({"journal"})
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = WOULD_STATES
    _attr_icon = "mdi:eye-outline"

    def __init__(self, plug, vehicle) -> None:
        super().__init__(plug, vehicle, "would_switch")

    @property
    def native_value(self) -> str:
        d = self.vehicle.decision
        return "off" if self.vehicle.mode != "learn" or d is None else d.action

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        v = self.vehicle
        d = v.decision
        iso = lambda t: t.isoformat() if t else None  # noqa: E731
        if v.mode != "learn" or d is None:
            return {"mode": v.mode}
        return {
            "mode": v.mode, "reason": d.reason, "planned_kw": d.kw, "until": iso(d.until),
            "summary": v.shadow.summary(dt_util.now()), "journal": v.shadow.journal[-12:][::-1],
        }
'''
p.write_text(s, encoding="utf-8")
print("ok")
