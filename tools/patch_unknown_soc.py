"""One-off: an unknown state of charge gives no need, no plan and no warning (kept for the record)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def patch(path, pairs):
    p = ROOT / path
    s = p.read_text(encoding="utf-8")
    for a, b in pairs:
        assert s.count(a) == 1, (path, a[:60])
        s = s.replace(a, b)
    p.write_text(s, encoding="utf-8")


patch("custom_components/plugwhen/const.py", [
    ('PLAN_STATES = ["planned", "not_needed", "infeasible", "no_departure"]', 'PLAN_STATES = ["planned", "not_needed", "infeasible", "no_departure", "unknown_soc"]'),
    ('READINESS_STATES = ["ready", "plug_in", "low", "too_late", "not_reachable"]', 'READINESS_STATES = ["ready", "plug_in", "low", "too_late", "not_reachable", "unknown"]'),
])
patch("custom_components/plugwhen/coordinator.py", [
    ('''        max_kw = float(v.cfg.get(V_CHARGE_MAX, DEFAULT_CHARGE_MAX))
        load, target_kw = self._load_inputs(now)''', '''        max_kw = float(v.cfg.get(V_CHARGE_MAX, DEFAULT_CHARGE_MAX))
        if v.soc is None:  # without the state of charge nothing can be said: no plan, no warning (the sensors say so)
            v.charge_plan = {"status": "unknown_soc", "windows": [], "needed_kwh": None, "planned_kwh": None}
            v.notice = None
            v.load_used = v.availability_used = False
            return
        load, target_kw = self._load_inputs(now)'''),
])
patch("custom_components/plugwhen/sensor.py", [
    ('''    def native_value(self) -> float | None:
        n = self.vehicle.need
        return n.charge_kwh if n is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        v, n = self.vehicle, self.vehicle.need''', '''    def native_value(self) -> float | None:
        n = self.vehicle.need
        return n.charge_kwh if n is not None and self.vehicle.soc is not None else None  # unknown state of charge: unknown

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        v, n = self.vehicle, self.vehicle.need'''),
    ('''    @property
    def native_value(self) -> str:
        n = self.vehicle.notice
        return n.kind if n is not None else "ready"''', '''    @property
    def native_value(self) -> str:
        if self.vehicle.soc is None:
            return "unknown"
        n = self.vehicle.notice
        return n.kind if n is not None else "ready"'''),
])
patch("tools/gen_strings.py", [
    ('plan_planned="Planned", plan_not_needed="Not needed", plan_infeasible="Target not reachable", plan_no_departure="No departure",',
     'plan_planned="Planned", plan_not_needed="Not needed", plan_infeasible="Target not reachable", plan_no_departure="No departure", plan_unknown="State of charge unknown",'),
    ('plan_planned="Geplant", plan_not_needed="Nicht nötig", plan_infeasible="Ziel nicht erreichbar", plan_no_departure="Keine Abfahrt",',
     'plan_planned="Geplant", plan_not_needed="Nicht nötig", plan_infeasible="Ziel nicht erreichbar", plan_no_departure="Keine Abfahrt", plan_unknown="Ladestand unbekannt",'),
    ('r_ready="Ready", r_plug="Plug in", r_low="Too low", r_late="Too late", r_unreach="Not reachable",',
     'r_ready="Ready", r_plug="Plug in", r_low="Too low", r_late="Too late", r_unreach="Not reachable", r_unknown="Unknown",'),
    ('r_ready="Bereit", r_plug="Bitte anstecken", r_low="Zu niedrig", r_late="Zu spät", r_unreach="Nicht erreichbar",',
     'r_ready="Bereit", r_plug="Bitte anstecken", r_low="Zu niedrig", r_late="Zu spät", r_unreach="Nicht erreichbar", r_unknown="Unbekannt",'),
    ('"infeasible": L["plan_infeasible"], "no_departure": L["plan_no_departure"]}},', '"infeasible": L["plan_infeasible"], "no_departure": L["plan_no_departure"],\n                                                               "unknown_soc": L["plan_unknown"]}},'),
    ('"too_late": L["r_late"], "not_reachable": L["r_unreach"]}},', '"too_late": L["r_late"], "not_reachable": L["r_unreach"], "unknown": L["r_unknown"]}},'),
])
print("ok")
