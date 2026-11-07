"""One-off: the two charts in the Home Assistant layer (kept for the record)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "custom_components" / "plugwhen"


def edit(path, pairs):
    p = path if isinstance(path, Path) else ROOT / path
    s = p.read_text(encoding="utf-8")
    for a, b in pairs:
        assert s.count(a) == 1, f"{p.name}: {a[:80]}"
        s = s.replace(a, b)
    p.write_text(s, encoding="utf-8")


edit(PKG / "const.py", [
    ('WOULD_STATES = ["charge", "pause", "none", "off"]', 'WOULD_STATES = ["charge", "pause", "none", "off"]\nLEARNING_STATES = ["learning_helps", "reserve_enough", "little", "too_little_data"]'),
])

edit(PKG / "coordinator.py", [
    ("from .history import records_from_hourly, to_km, to_kwh\n", "from .history import records_from_hourly, to_km, to_kwh\nfrom .insight import learning_check\n"),
    ("    plug_seeding: bool = False               # the recorder history is being read: do not write meanwhile\n",
     "    plug_seeding: bool = False               # the recorder history is being read: do not write meanwhile\n"
     "    records: list = field(default_factory=list)   # daily records of the history (for the check of the learning)\n"
     "    insight_cache: tuple | None = None       # ((reserve, number of records, loaded at), result)\n"),
    ("        model = MobilityModel()\n        for r in records:\n", "        v.records = records\n        model = MobilityModel()\n        for r in records:\n"),
    ("    def _shadow_step(self, v: Vehicle, now: datetime) -> None:\n",
     "    def insight(self, v: Vehicle) -> dict[str, Any]:\n"
     '        """Does the learning bring anything for this car (walks through the history; cached until the reserve or the history changes)."""\n'
     "        key = (v.reserve_km, len(v.records), v.history_at)\n"
     "        if v.insight_cache is None or v.insight_cache[0] != key:\n"
     "            v.insight_cache = (key, learning_check(v.records, v.reserve_km))\n"
     "        return v.insight_cache[1]\n\n"
     "    def _shadow_step(self, v: Vehicle, now: datetime) -> None:\n"),
])

edit(PKG / "sensor.py", [
    ("from .const import PLAN_STATES, POTENTIAL_STATES, READINESS_STATES, WOULD_STATES",
     "from .charts import chart_learning, chart_shadow\nfrom .const import LEARNING_STATES, PLAN_STATES, POTENTIAL_STATES, READINESS_STATES, WOULD_STATES"),
    ("            WouldSwitchSensor(plug, v),\n", "            WouldSwitchSensor(plug, v),\n            LearningCheckSensor(plug, v),\n"),
    ('    _unrecorded_attributes = frozenset({"journal"})', '    _unrecorded_attributes = frozenset({"journal", "chart"})'),
    ('            "summary": v.shadow.summary(dt_util.now()), "journal": v.shadow.journal[-12:][::-1],\n        }',
     '            "summary": v.shadow.summary(dt_util.now()), "journal": v.shadow.journal[-12:][::-1],\n'
     '            "chart": chart_shadow(v.shadow.days, dt_util.now().date(), self.hass.config.language),\n        }'),
])
s = (PKG / "sensor.py").read_text(encoding="utf-8")
s += '''

class LearningCheckSensor(PlugwhenEntity, SensorEntity):
    """Does the learning bring anything for this car? Walks through its history day by day (the model only knows the days before
    each day) and compares the range with the fixed reserve alone against the reserve lifted by what was learned, and how often
    the departure hour was guessed right. State: learning_helps, reserve_enough, little, too_little_data."""

    _unrecorded_attributes = frozenset({"chart", "departure_by_weekday"})
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = LEARNING_STATES
    _attr_icon = "mdi:school-outline"

    def __init__(self, plug, vehicle) -> None:
        super().__init__(plug, vehicle, "learning_check")

    @property
    def native_value(self) -> str:
        return self.plug.insight(self.vehicle)["verdict"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        r = self.plug.insight(self.vehicle)
        keys = ("days", "reserve_km", "coverage_reserve_pct", "coverage_learned_pct", "gain_points", "departure_right_pct",
                "departure_days", "departure_by_weekday")
        return {**{k: r[k] for k in keys}, "chart": chart_learning(r, self.hass.config.language)}
'''
(PKG / "sensor.py").write_text(s, encoding="utf-8")

edit(ROOT / "tools" / "gen_strings.py", [
    ('m_mode="Mode", m_off="Off",', 's_lc="Does learning help?", lc_helps="Learning helps", lc_enough="Reserve is enough", lc_little="Little difference", lc_few="Too little data",\n    m_mode="Mode", m_off="Off",'),
    ('m_mode="Betriebsart", m_off="Aus",', 's_lc="Bringt das Lernen etwas?", lc_helps="Lernen hilft", lc_enough="Reserve reicht", lc_little="Kaum Unterschied", lc_few="Zu wenig Daten",\n    m_mode="Betriebsart", m_off="Aus",'),
    ('                "would_switch": {"name": L["s_would"],',
     '                "learning_check": {"name": L["s_lc"], "state": {"learning_helps": L["lc_helps"], "reserve_enough": L["lc_enough"], "little": L["lc_little"], "too_little_data": L["lc_few"]}},\n'
     '                "would_switch": {"name": L["s_would"],'),
])
print("ok")
