"""One-off: the charging habit in the Home Assistant layer (kept for the record)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "custom_components" / "plugwhen"


def edit(path, pairs):
    p = path if isinstance(path, Path) else ROOT / path
    s = p.read_text(encoding="utf-8")
    for a, b in pairs:
        assert s.count(a) == 1, f"{p.name}: {a[:90]}"
        s = s.replace(a, b)
    p.write_text(s, encoding="utf-8")


edit(PKG / "coordinator.py", [
    ("from .history import records_from_hourly, to_km, to_kwh\n", "from .habit import charging_habit\nfrom .history import records_from_hourly, to_km, to_kwh\n"),
    ("    efficiency: float | None = None          # learned share of the wallbox energy that reaches the battery (None = default)\n",
     "    efficiency: float | None = None          # learned share of the wallbox energy that reaches the battery (None = default)\n"
     "    habit: dict | None = None                # when the car is charged (per weekday: day, night, in between)\n"),
    ('                {"state", "mean", "max"},\n            )',
     '                {"state", "mean", "max", "change"},\n            )'),
    ("        odometer = series(odo_id, \"state\", \"max\", to_km)\n",
     "        if wb_id:\n"
     "            wb_unit = self._unit(wb_id)\n"
     "            hourly_wb = {dt_util.as_local(dt_util.utc_from_timestamp(r[\"start\"])): to_kwh(float(r[\"change\"]), wb_unit)\n"
     "                         for r in stats.get(wb_id, []) if r.get(\"change\") is not None}\n"
     "            v.habit = charging_habit(hourly_wb, now)\n"
     "        odometer = series(odo_id, \"state\", \"max\", to_km)\n"),
])

edit(PKG / "sensor.py", [
    ("from .charts import chart_learning, chart_plan, chart_plugs, chart_potential, chart_shadow\n",
     "from .charts import chart_habit, chart_learning, chart_plan, chart_plugs, chart_potential, chart_shadow\n"),
    ("            LearningCheckSensor(plug, v),\n", "            LearningCheckSensor(plug, v),\n            ChargingHabitSensor(plug, v),\n"),
])
s = (PKG / "sensor.py").read_text(encoding="utf-8")
s += '''

class ChargingHabitSensor(PlugwhenEntity, SensorEntity):
    """When the car is charged: the share of the energy charged at night (20 to 7 h) over the last 90 days. The attributes give the
    day and the weekend share and, per weekday, the energy during the day, at night and in between, and a chart. It works without
    a solar plant: it only needs the energy counter of the wallbox. It does not judge (with a night tariff, night charging is fine)."""

    _unrecorded_attributes = frozenset({"chart", "by_weekday"})
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = "mdi:chart-bar-stacked"

    def __init__(self, plug, vehicle) -> None:
        super().__init__(plug, vehicle, "habit")

    @property
    def native_value(self) -> int | None:
        h = self.vehicle.habit
        return h.get("night_share_pct") if h and h.get("status") == "ok" else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        h = self.vehicle.habit or {"status": "no_data"}
        keys = ("status", "days", "total_kwh", "day_share_pct", "night_share_pct", "weekend_share_pct", "weekdays_night_share_pct")
        return {**{k: h.get(k) for k in keys}, "by_weekday": h.get("weekday"), "chart": chart_habit(h, self.hass.config.language)}
'''
(PKG / "sensor.py").write_text(s, encoding="utf-8")

edit(ROOT / "tools" / "gen_strings.py", [
    ('s_lc="Does learning help?",', 's_habit="Charging habit", s_lc="Does learning help?",'),
    ('s_lc="Bringt das Lernen etwas?",', 's_habit="Ladegewohnheit", s_lc="Bringt das Lernen etwas?",'),
    ('                "learning_check": {"name": L["s_lc"],', '                "habit": {"name": L["s_habit"]},\n                "learning_check": {"name": L["s_lc"],'),
])

edit(PKG / "dashboard.py", [
    ('"mode": "select", "would_switch": "sensor", "learning_check": "sensor",', '"mode": "select", "would_switch": "sensor", "learning_check": "sensor", "habit": "sensor",'),
    ('        learn_h="Lernmodus", mode_name="Betriebsart", would="Würde schalten",',
     '        hb_h="Wann laden Sie?", hb_tile="Nachts geladen", hb_a="Nachts (20–7 Uhr) wurden", hb_b="Prozent der Energie geladen, tagsüber (9–17 Uhr)",\n'
     '        hb_c="Prozent, am Wochenende", hb_d="Prozent. Mo bis Fr nachts:", hb_few="Noch zu wenig Daten für die Ladegewohnheit (28 Tage nötig).",\n'
     '        learn_h="Lernmodus", mode_name="Betriebsart", would="Würde schalten",'),
    ('        learn_h="Learn mode", mode_name="Mode", would="Would switch",',
     '        hb_h="When do you charge?", hb_tile="Charged at night", hb_a="At night (20 to 7 h)", hb_b="percent of the energy were charged, during the day (9 to 17 h)",\n'
     '        hb_c="percent, at the weekend", hb_d="percent. Mon to Fri at night:", hb_few="Too little data for the charging habit yet (28 days needed).",\n'
     '        learn_h="Learn mode", mode_name="Mode", would="Would switch",'),
    ('    head = (lambda h: f"{name} · {h}") if multi else (lambda h: h)\n    return [',
     '''    hb_id = ids["habit"]
    habit_line = (
        "{% set a = " + _s(hb_id) + ".attributes %}"
        f"{{% if a.status == 'ok' %}}{t['hb_a']} **{{{{ a.night_share_pct }}}}** {t['hb_b']} **{{{{ a.day_share_pct }}}}**"
        f" {t['hb_c']} **{{{{ a.weekend_share_pct }}}}** {t['hb_d']} **{{{{ a.weekdays_night_share_pct }}}} %**."
        f"{{% else %}}{t['hb_few']}{{% endif %}}"
    )
    head = (lambda h: f"{name} · {h}") if multi else (lambda h: h)
    return ['''),
    ('''        {"type": "grid", "cards": [
            {"type": "heading", "heading": head(t["learn_h"]), "icon": "mdi:school-outline"},''',
     '''        {"type": "grid", "cards": [
            {"type": "heading", "heading": head(t["hb_h"]), "icon": "mdi:chart-bar-stacked"},
            {"type": "tile", "entity": hb_id, "name": t["hb_tile"]},
            {"type": "markdown", "content": _chart(hb_id)},
            {"type": "markdown", "content": habit_line},
        ]},
        {"type": "grid", "cards": [
            {"type": "heading", "heading": head(t["learn_h"]), "icon": "mdi:school-outline"},'''),
])

edit(ROOT / "tests" / "install" / "itest.py", [
    ('log(len(ents) == 14, "entities of the vehicle exist"', 'log(len(ents) == 15, "entities of the vehicle exist"'),
    ('        wa0 = state(wid)["attributes"] if would_s else {}\n',
     '        hb = find("sensor", "charging_habit")\n'
     '        hba = state(hb["entity_id"])["attributes"] if hb else {}\n'
     '        log(bool(hb) and hba.get("status") in ("too_little_data", "ok", "no_data") and str(hba.get("chart", "")).startswith("<svg"),\n'
     '            "the charging habit sensor exists and delivers a chart (valid SVG), also without any history", f"{hba.get(\'status\')} / {str(hba.get(\'chart\'))[:30]}")\n'
     '        wa0 = state(wid)["attributes"] if would_s else {}\n'),
])
print("ok")
