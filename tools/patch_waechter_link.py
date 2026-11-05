"""One-off: connect to the quarter-hour peak guard by choosing it (a config entry), not entity by entity (kept for the record)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
B = ROOT / "custom_components" / "plugwhen"


def patch(path, pairs):
    s = path.read_text(encoding="utf-8")
    for a, b in pairs:
        assert s.count(a) == 1, (str(path), a[:60], s.count(a))
        s = s.replace(a, b)
    path.write_text(s, encoding="utf-8")


patch(B / "const.py", [(
    'O_LOAD = "load_entity"',
    'O_WAECHTER = "waechter_entry"             # the quarter-hour peak guard (a config entry): its load forecast is found automatically\nO_LOAD = "load_entity"')])

patch(B / "coordinator.py", [
    ("HISTORY_DAYS, HISTORY_INTERVAL, O_AVAIL, O_LOAD,", "HISTORY_DAYS, HISTORY_INTERVAL, O_AVAIL, O_LOAD, O_WAECHTER,"),
    ("from .history import records_from_hourly, to_km, to_kwh\n", "from .history import records_from_hourly, to_km, to_kwh\nfrom .links import pick\n"),
    ("        watched = {self.entry.options.get(O_LOAD), self.entry.options.get(O_AVAIL)}", "        watched = {self._load_entity(), self.entry.options.get(O_AVAIL)}"),
    ('''    def _load_inputs(self, now: datetime)''', '''    def _load_entity(self) -> str | None:
        """The load forecast sensor: an entity named in the settings, else the one of the chosen quarter-hour peak guard."""
        explicit = self.entry.options.get(O_LOAD)
        if explicit:
            return explicit
        entry_id = self.entry.options.get(O_WAECHTER)
        if not entry_id:
            return None
        from homeassistant.helpers import entity_registry as er

        return pick(((e.entity_id, e.domain, e.unique_id) for e in er.async_entries_for_config_entry(er.async_get(self.hass), entry_id)),
                    "sensor", "_forecast_peak")

    def _load_inputs(self, now: datetime)'''),
    ("        st = self._state(self.entry.options.get(O_LOAD))\n        if st is None or st.state in _BAD:\n            return None, None", "        st = self._state(self._load_entity())\n        if st is None or st.state in _BAD:\n            return None, None"),
])

patch(B / "sensor.py", [(
    '"load_forecast_used": v.load_used, "availability_used": v.availability_used,',
    '"load_forecast_used": v.load_used, "load_entity": self.plug._load_entity(), "availability_used": v.availability_used,')])

patch(B / "config_flow.py", [
    ("    EntitySelector, EntitySelectorConfig, NumberSelector,", "    ConfigEntrySelector, ConfigEntrySelectorConfig, EntitySelector, EntitySelectorConfig, NumberSelector,"),
    ("DOMAIN, O_AVAIL, O_LOAD,", "DOMAIN, O_AVAIL, O_LOAD, O_WAECHTER,"),
    ('''def find_waechter_forecast(hass: HomeAssistant) -> str | None:
    """The forecast sensor of the quarter-hour peak guard, if it is installed (found in the entity registry, nothing is imported)."""
    for entry in er.async_get(hass).entities.values():
        if entry.platform == WAECHTER_DOMAIN and entry.domain == "sensor" and str(entry.unique_id).endswith("_forecast_peak"):
            return entry.entity_id
    return None
''', '''def find_waechter_entry(hass: HomeAssistant) -> str | None:
    """The config entry of the quarter-hour peak guard if there is exactly one (offered in the settings, nothing is imported)."""
    entries = hass.config_entries.async_entries(WAECHTER_DOMAIN)
    return entries[0].entry_id if len(entries) == 1 else None
'''),
    ('''        if not current.get(O_LOAD):
            found = find_waechter_forecast(self.hass)  # offered, not forced
            if found:
                current[O_LOAD] = found
        return self.async_show_form(step_id="init", data_schema=vol.Schema({
            _opt(O_LOAD, current): _ent("sensor"),''', '''        if not current.get(O_WAECHTER) and not current.get(O_LOAD):
            found = find_waechter_entry(self.hass)  # offered, not forced
            if found:
                current[O_WAECHTER] = found
        return self.async_show_form(step_id="init", data_schema=vol.Schema({
            _opt(O_WAECHTER, current): ConfigEntrySelector(ConfigEntrySelectorConfig(integration=WAECHTER_DOMAIN)),
            _opt(O_LOAD, current): _ent("sensor"),'''),
    ("from homeassistant.helpers import entity_registry as er\n", ""),
])

patch(ROOT / "tools" / "gen_strings.py", [
    ('o_load="Load forecast", o_avail="Availability of power",', 'o_wachter="Quarter-hour peak guard", o_load="Other load forecast", o_avail="Availability of power",'),
    ('o_load="Last-Prognose", o_avail="Verfügbarkeit von Strom",', 'o_wachter="Viertelstunden-Wächter", o_load="Andere Last-Prognose", o_avail="Verfügbarkeit von Strom",'),
    ('    od_load="A sensor with the attributes hours (t, typical, high) and target_kw, for example the forecast sensor of the quarter-hour peak guard. Suggested automatically if it is installed.",',
     '    od_wachter="Choose the quarter-hour peak guard and Plugwhen finds its load forecast by itself (and keeps the charging under its peak target). Suggested automatically if exactly one is installed.",\n    od_load="Only for another source: a sensor with the attributes hours (t, typical, high) and target_kw. Not needed when you chose the peak guard.",'),
    ('    od_load="Ein Sensor mit den Attributen hours (t, typical, high) und target_kw, zum Beispiel der Prognose-Sensor des Viertelstunden-Wächters. Wird automatisch vorgeschlagen, wenn er installiert ist.",',
     '    od_wachter="Wählen Sie den Viertelstunden-Wächter, dann findet Plugwhen seine Last-Prognose selbst (und hält das Laden unter seiner Spitzengrenze). Wird automatisch vorgeschlagen, wenn genau einer installiert ist.",\n    od_load="Nur für eine andere Quelle: ein Sensor mit den Attributen hours (t, typical, high) und target_kw. Nicht nötig, wenn Sie den Wächter gewählt haben.",'),
    ('"data": {"load_entity": L["o_load"], "availability_entity": L["o_avail"]},', '"data": {"waechter_entry": L["o_wachter"], "load_entity": L["o_load"], "availability_entity": L["o_avail"]},'),
    ('"data_description": {"load_entity": L["od_load"], "availability_entity": L["od_avail"]},', '"data_description": {"waechter_entry": L["od_wachter"], "load_entity": L["od_load"], "availability_entity": L["od_avail"]},'),
])
print("ok")
