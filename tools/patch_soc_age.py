"""One-off: the state of charge has a maximum age (kept for the record)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
B = ROOT / "custom_components" / "plugwhen"


def patch(path, pairs):
    s = path.read_text(encoding="utf-8")
    for a, b in pairs:
        assert s.count(a) == 1, (str(path), a[:70], s.count(a))
        s = s.replace(a, b)
    path.write_text(s, encoding="utf-8")


patch(B / "const.py", [
    ('V_PLUGGED = "plugged_entity"', 'V_SOC_MAX_AGE = "soc_max_age_h"             # a state of charge older than this (hours) counts as unknown, 0 = no limit\nV_PLUGGED = "plugged_entity"'),
    ('DEFAULT_RESERVE_KM = 100', 'DEFAULT_SOC_MAX_AGE_H = 12.0\nDEFAULT_RESERVE_KM = 100'),
])

patch(B / "coordinator.py", [
    ("    DEFAULT_CHARGE_MAX, DEFAULT_CHARGE_MIN, DEFAULT_CONSUMPTION_100, DEFAULT_NOTIFY_HOUR, DEFAULT_RESERVE_KM, DOMAIN,",
     "    DEFAULT_CHARGE_MAX, DEFAULT_CHARGE_MIN, DEFAULT_CONSUMPTION_100, DEFAULT_NOTIFY_HOUR, DEFAULT_RESERVE_KM, DEFAULT_SOC_MAX_AGE_H, DOMAIN,"),
    ("    V_RESERVE, V_SOC, V_WALLBOX_ENERGY,\n)", "    V_RESERVE, V_SOC, V_SOC_MAX_AGE, V_WALLBOX_ENERGY,\n)"),
    ("from .history import records_from_hourly, to_km, to_kwh\n", "from .freshness import soc_is_stale\nfrom .history import records_from_hourly, to_km, to_kwh\n"),
    ("    soc: float | None = None\n    plugged: bool | None = None", "    soc: float | None = None\n    soc_age_s: float | None = None   # seconds since the state of charge was written\n    soc_stale: bool = False          # too old: counts as unknown\n    plugged: bool | None = None"),
    ('''    def _is_on(self, eid: str | None) -> bool | None:''', '''    def _age_s(self, eid: str | None, now: datetime) -> float | None:
        """Seconds since the entity's state was last written (also when the value did not change)."""
        st = self._state(eid)
        if st is None:
            return None
        stamp = max(st.last_updated, getattr(st, "last_reported", st.last_updated))
        return max(0.0, (now - stamp).total_seconds())

    def _is_on(self, eid: str | None) -> bool | None:'''),
    ('''        v.soc = self._float(v.cfg.get(V_SOC))
        v.plugged = self._is_on(v.cfg.get(V_PLUGGED))
        v.charging = self._is_on(v.cfg.get(V_CHARGING)) is True''', '''        v.plugged = self._is_on(v.cfg.get(V_PLUGGED))
        v.charging = self._is_on(v.cfg.get(V_CHARGING)) is True
        v.soc = self._float(v.cfg.get(V_SOC))
        v.soc_age_s = self._age_s(v.cfg.get(V_SOC), now) if v.soc is not None else None
        v.soc_stale = soc_is_stale(v.soc_age_s, float(v.cfg.get(V_SOC_MAX_AGE, DEFAULT_SOC_MAX_AGE_H)), v.charging)
        if v.soc_stale:  # too old to be believed: like an unknown state of charge (no plan, no warning)
            v.soc = None'''),
])

patch(B / "sensor.py", [
    ('            "soc": v.soc,\n            "plugged": v.plugged,', '            "soc": v.soc,\n            "soc_stale": v.soc_stale,\n            "soc_age_h": round(v.soc_age_s / 3600.0, 2) if v.soc_age_s is not None else None,\n            "plugged": v.plugged,'),
    ('        return {"shortfall_kwh": n.shortfall_kwh if n else 0.0, "max_possible_kwh": n.max_possible_kwh if n else None}',
     '        return {"shortfall_kwh": n.shortfall_kwh if n else 0.0, "max_possible_kwh": n.max_possible_kwh if n else None,\n                "soc_stale": self.vehicle.soc_stale}'),
])

patch(B / "config_flow.py", [
    ("DEFAULT_RESERVE_KM, DOMAIN, O_AVAIL,", "DEFAULT_RESERVE_KM, DEFAULT_SOC_MAX_AGE_H, DOMAIN, O_AVAIL,"),
    ("V_NOTIFY_HOUR, V_ODOMETER, V_PLUGGED, V_RESERVE, V_SOC, V_WALLBOX_ENERGY,\n)", "V_NOTIFY_HOUR, V_ODOMETER, V_PLUGGED, V_RESERVE, V_SOC, V_SOC_MAX_AGE, V_WALLBOX_ENERGY,\n)"),
    ('''        vol.Required(V_CAPACITY, default=d.get(V_CAPACITY, DEFAULT_CAPACITY_KWH)): _num(5, 250, 0.5, "kWh"),''',
     '''        vol.Required(V_SOC_MAX_AGE, default=d.get(V_SOC_MAX_AGE, DEFAULT_SOC_MAX_AGE_H)): _num(0, 168, 0.01, "h"),
        vol.Required(V_CAPACITY, default=d.get(V_CAPACITY, DEFAULT_CAPACITY_KWH)): _num(5, 250, 0.5, "kWh"),'''),
])

patch(ROOT / "tools" / "gen_strings.py", [
    ('f_name="Name", f_odo="Odometer", f_soc="State of charge",', 'f_name="Name", f_odo="Odometer", f_soc="State of charge", f_age="Maximum age of the state of charge",'),
    ('f_name="Name", f_odo="Kilometerstand", f_soc="Ladestand",', 'f_name="Name", f_odo="Kilometerstand", f_soc="Ladestand", f_age="Höchstalter des Ladestands",'),
    ('    d_cap="Usable battery capacity.",', '    d_age="If the state of charge was not written for longer than this, Plugwhen treats it as unknown: no plan, no warning. A parked car that sleeps is fine up to this age. While the car is charging, 90 minutes without a new value already count as stale (many cars send nothing while charging). 0 = no limit.",\n    d_cap="Usable battery capacity.",'),
    ('    d_cap="Nutzbare Batteriekapazität.",', '    d_age="Wurde der Ladestand länger als das nicht geschrieben, behandelt Plugwhen ihn als unbekannt: kein Plan, keine Warnung. Ein parkendes, schlafendes Auto ist bis zu diesem Alter in Ordnung. Während des Ladens gelten schon 90 Minuten ohne neuen Wert als veraltet (viele Autos senden beim Laden nichts). 0 = keine Grenze.",\n    d_cap="Nutzbare Batteriekapazität.",'),
    ('"odometer_entity": L["f_odo"], "soc_entity": L["f_soc"], "capacity_kwh": L["f_cap"],', '"odometer_entity": L["f_odo"], "soc_entity": L["f_soc"], "soc_max_age_h": L["f_age"], "capacity_kwh": L["f_cap"],'),
    ('"odometer_entity": L["d_odo"], "soc_entity": L["d_soc"], "capacity_kwh": L["d_cap"],', '"odometer_entity": L["d_odo"], "soc_entity": L["d_soc"], "soc_max_age_h": L["d_age"], "capacity_kwh": L["d_cap"],'),
])
print("ok")
