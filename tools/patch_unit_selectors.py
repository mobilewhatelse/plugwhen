"""One-off: odometer, state of charge and the energy counters can be any sensor with the right unit, not only sensors with a device
class (kept for the record). The same problem as issue 1 of the peak guard: template sensors without a device class were missing."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "custom_components" / "plugwhen"


def rw(path, fn):
    s = path.read_text(encoding="utf-8", newline="")
    crlf = "\r\n" in s
    s = fn(s.replace("\r\n", "\n"))
    if crlf:
        s = s.replace("\n", "\r\n")
    path.write_text(s, encoding="utf-8", newline="")


def edit(rel, pairs):
    def fn(s):
        for a, b in pairs:
            assert s.count(a) == 1, (rel, a[:80], s.count(a))
            s = s.replace(a, b)
        return s
    rw(ROOT / rel, fn)


(PKG / "units.py").write_text('''"""Checks of the sensors chosen in the dialogs (pure Python, no Home Assistant imports).

A sensor does not need a device class: a template sensor with the right unit is just as good, and many installations have exactly
that. What matters is the unit, because Plugwhen converts it. A sensor without any unit is accepted where Plugwhen assumes one
(kilometres, percent, kWh); a unit it cannot convert is refused with a clear message.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

DISTANCE_UNITS = ("km", "mi", "mile", "miles")
PERCENT_UNITS = ("%",)
ENERGY_UNITS = ("wh", "kwh", "mwh")


def unit_errors(
    get_state: Callable[[str], Any],
    values: Mapping[str, Any],
    specs: Mapping[str, tuple[tuple[str, ...], str]],
) -> dict[str, str]:
    """Field name -> error key for every chosen sensor whose unit is not one of the allowed ones.

    `specs`: field name -> (allowed units in lower case, error key). A sensor that is not loaded yet is not blocked, an empty field
    and a sensor without a unit are not either (the unit is assumed, see above)."""
    errors: dict[str, str] = {}
    for key, (units, error) in specs.items():
        entity_id = values.get(key)
        if not entity_id:
            continue
        state = get_state(entity_id)
        if state is None:
            continue
        unit = str(state.attributes.get("unit_of_measurement") or "").strip().lower()
        if unit and unit not in units:
            errors[key] = error
    return errors
''', encoding="utf-8", newline="")

edit("custom_components/plugwhen/config_flow.py", [
    ("from .const import (", "from .inputs import DISTANCE_UNITS, ENERGY_UNITS, PERCENT_UNITS, unit_errors\nfrom .const import ("),
    ('V_ODOMETER, default=d.get(V_ODOMETER, vol.UNDEFINED)): _ent("sensor", "distance"),',
     'V_ODOMETER, default=d.get(V_ODOMETER, vol.UNDEFINED)): _ent("sensor"),'),
    ('V_SOC, default=d.get(V_SOC, vol.UNDEFINED)): _ent("sensor", "battery"),',
     'V_SOC, default=d.get(V_SOC, vol.UNDEFINED)): _ent("sensor"),'),
    ('_opt(V_WALLBOX_ENERGY, d): _ent("sensor", "energy"),', '_opt(V_WALLBOX_ENERGY, d): _ent("sensor"),'),
    ('_opt(O_GRID_ENERGY, current): _ent("sensor", "energy"),', '_opt(O_GRID_ENERGY, current): _ent("sensor"),'),
    ('''        if user_input is not None:
            return self.async_create_entry(data={k: v for k, v in user_input.items() if v not in (None, "")})
        current = dict(self.config_entry.options)
''', '''        errors: dict[str, str] = {}
        if user_input is not None:
            errors = unit_errors(self.hass.states.get, user_input, OPTION_UNITS)
            if not errors:
                return self.async_create_entry(data={k: v for k, v in user_input.items() if v not in (None, "")})
        current = dict(self.config_entry.options) if user_input is None else dict(user_input)
'''),
    ('''        return self.async_show_form(step_id="init", data_schema=vol.Schema({
            _opt(O_WAECHTER, current)''', '''        return self.async_show_form(step_id="init", errors=errors, data_schema=vol.Schema({
            _opt(O_WAECHTER, current)'''),
    ('''        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input[V_ODOMETER] == user_input[V_SOC]:
                errors[V_SOC] = "same_entity"
''', '''        errors: dict[str, str] = {}
        if user_input is not None:
            errors = unit_errors(self.hass.states.get, user_input, VEHICLE_UNITS)
            if errors:
                pass
            elif user_input[V_ODOMETER] == user_input[V_SOC]:
                errors[V_SOC] = "same_entity"
'''),
    ('''class PlugwhenOptionsFlow(OptionsFlow):''', '''OPTION_UNITS = {O_GRID_ENERGY: (ENERGY_UNITS, "not_energy")}
VEHICLE_UNITS = {V_ODOMETER: (DISTANCE_UNITS, "not_distance"), V_SOC: (PERCENT_UNITS, "not_percent"),
                 V_WALLBOX_ENERGY: (ENERGY_UNITS, "not_energy")}


class PlugwhenOptionsFlow(OptionsFlow):'''),
])

edit("tools/gen_strings.py", [
    ('e_same="Odometer and state of charge must be different sensors.",',
     'e_same="Odometer and state of charge must be different sensors.", e_dist="This sensor has no distance unit (km or mi). Choose the odometer or add unit_of_measurement: km to the template sensor.",\n'
     '    e_pct="This sensor has no percent unit. Choose the state of charge in % or add unit_of_measurement: \\"%\\" to the template sensor.",\n'
     '    e_en="This sensor has no energy unit (Wh, kWh or MWh). Add unit_of_measurement: kWh to the template sensor or choose another sensor.",'),
    ('e_same="Kilometerstand und Ladestand müssen verschiedene Sensoren sein.",',
     'e_same="Kilometerstand und Ladestand müssen verschiedene Sensoren sein.", e_dist="Dieser Sensor hat keine Entfernungseinheit (km oder mi). Wählen Sie den Kilometerstand oder ergänzen Sie beim Template-Sensor unit_of_measurement: km.",\n'
     '    e_pct="Dieser Sensor hat keine Prozent-Einheit. Wählen Sie den Ladestand in % oder ergänzen Sie beim Template-Sensor unit_of_measurement: \\"%\\".",\n'
     '    e_en="Dieser Sensor hat keine Energieeinheit (Wh, kWh oder MWh). Ergänzen Sie beim Template-Sensor unit_of_measurement: kWh oder wählen Sie einen anderen Sensor.",'),
    ('"error": {"same_entity": L["e_same"], "min_above_max": L["e_minmax"], "notify_format": L["e_notify"]},',
     '"error": {"same_entity": L["e_same"], "min_above_max": L["e_minmax"], "notify_format": L["e_notify"],\n'
     '                      "not_distance": L["e_dist"], "not_percent": L["e_pct"], "not_energy": L["e_en"]},'),
    ('''        "options": {"step": {"init": {''', '''        "options": {"error": {"not_energy": L["e_en"]}, "step": {"init": {'''),
])
print("ok")
