"""One-off: the three new charts as sensor attributes (kept for the record)."""
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"


def edit(name, pairs):
    p = PKG / name
    s = p.read_text(encoding="utf-8")
    for a, b in pairs:
        assert s.count(a) == 1, f"{name}: {a[:80]}"
        s = s.replace(a, b)
    p.write_text(s, encoding="utf-8")


edit("charts.py", [
    ('''        label = f"{t['wd'][tt.weekday()]} 0" if tt.hour == 0 else f"{tt.hour}"''',
     '''        label = t["wd"][tt.weekday()] if tt.hour == 0 else f"{tt.hour}"'''),
])
edit("sensor.py", [
    ("from .charts import chart_learning, chart_shadow\n", "from .charts import chart_learning, chart_plan, chart_plugs, chart_potential, chart_shadow\n"),
    ('    _unrecorded_attributes = frozenset({"windows"})', '    _unrecorded_attributes = frozenset({"windows", "chart"})'),
    ('            "availability_source": v.availability_source,\n',
     '            "availability_source": v.availability_source,\n'
     '            "chart": chart_plan(p, dt_util.now(), float(v.cfg.get("charge_kw_max") or 11.0), self.hass.config.language),\n'),
    ('            out["plugging"] = v.plug_log.summary(dt_util.now())\n',
     '            out["plugging"] = v.plug_log.summary(dt_util.now())\n'
     '            out["plug_chart"] = chart_plugs(v.plug_log.intervals(), dt_util.now(), self.hass.config.language)\n'),
    ('    _unrecorded_attributes = frozenset({"strategies"})', '    _unrecorded_attributes = frozenset({"strategies", "chart"})'),
    ("        return {k: p.get(k) for k in keys if k in p}\n",
     "        out = {k: p.get(k) for k in keys if k in p}\n"
     "        cur = {\"EUR\": \"€\", \"USD\": \"$\", \"GBP\": \"£\"}.get(self.hass.config.currency or \"EUR\", self.hass.config.currency or \"€\")\n"
     "        out[\"chart\"] = chart_potential(p, self.hass.config.language, cur)\n"
     "        return out\n"),
])
# the readiness sensor gets a recorder exclusion for its chart
p = PKG / "sensor.py"
s = p.read_text(encoding="utf-8")
anchor = 'class ReadinessSensor(PlugwhenEntity, SensorEntity):\n'
i = s.index(anchor)
j = s.index("    _attr_device_class", i)
assert "_unrecorded_attributes" not in s[i:j]
s = s[:j] + '    _unrecorded_attributes = frozenset({"plug_chart"})\n' + s[j:]
p.write_text(s, encoding="utf-8")
print("ok")
