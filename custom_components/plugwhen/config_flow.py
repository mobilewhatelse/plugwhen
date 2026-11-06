"""Set-up dialog (one entry), the connections to other integrations (options) and the vehicles as config subentries."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry, ConfigFlow, ConfigFlowResult, ConfigSubentryFlow, OptionsFlow, SubentryFlowResult,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    BooleanSelector, ConfigEntrySelector, ConfigEntrySelectorConfig, EntitySelector, EntitySelectorConfig, NumberSelector, NumberSelectorConfig, NumberSelectorMode, TextSelector,
)

from .const import (
    DEFAULT_CAPACITY_KWH, DEFAULT_CHARGE_MAX, DEFAULT_CHARGE_MIN, DEFAULT_CONSUMPTION_100, DEFAULT_NOTIFY_HOUR,
    DEFAULT_RESERVE_KM, DEFAULT_SOC_MAX_AGE_H, DEFAULT_SOLAR_DEDUCT, DOMAIN, O_AVAIL, O_GRID_ENERGY, O_LOAD, O_PRICE_HIGH, O_PRICE_LOW,
    O_PRICE_THRESHOLD, O_SOLAR, O_SOLAR_DEDUCT, O_WAECHTER, SUBENTRY_VEHICLE, V_CAPACITY, V_CHARGE_MAX, V_CHARGE_MIN, V_CHARGING,
    V_CONSUMPTION, V_DEPARTURE, V_NAME, V_NOTIFY, V_NOTIFY_HOUR, V_ODOMETER, V_PLUGGED, V_RESERVE, V_SOC, V_SOC_MAX_AGE, V_WALLBOX_ENERGY,
)

WAECHTER_DOMAIN = "viertelstunden_waechter"


def _num(lo: float, hi: float, step: float, unit: str) -> NumberSelector:
    return NumberSelector(NumberSelectorConfig(min=lo, max=hi, step=step, mode=NumberSelectorMode.BOX, unit_of_measurement=unit))


def _ent(domain: str | list[str], device_class: str | None = None) -> EntitySelector:
    if device_class:
        return EntitySelector(EntitySelectorConfig(domain=domain, device_class=device_class))
    return EntitySelector(EntitySelectorConfig(domain=domain))


def _opt(key: str, d: dict[str, Any]) -> vol.Optional:
    return vol.Optional(key, description={"suggested_value": d.get(key)})


def find_waechter_entry(hass: HomeAssistant) -> str | None:
    """The config entry of the quarter-hour peak guard if there is exactly one (offered in the settings, nothing is imported)."""
    entries = hass.config_entries.async_entries(WAECHTER_DOMAIN)
    return entries[0].entry_id if len(entries) == 1 else None


def _vehicle_schema(d: dict[str, Any]) -> vol.Schema:
    return vol.Schema({
        vol.Required(V_NAME, default=d.get(V_NAME, vol.UNDEFINED)): TextSelector(),
        vol.Required(V_ODOMETER, default=d.get(V_ODOMETER, vol.UNDEFINED)): _ent("sensor", "distance"),
        vol.Required(V_SOC, default=d.get(V_SOC, vol.UNDEFINED)): _ent("sensor", "battery"),
        vol.Required(V_SOC_MAX_AGE, default=d.get(V_SOC_MAX_AGE, DEFAULT_SOC_MAX_AGE_H)): _num(0, 168, 0.01, "h"),
        vol.Required(V_CAPACITY, default=d.get(V_CAPACITY, DEFAULT_CAPACITY_KWH)): _num(5, 250, 0.5, "kWh"),
        vol.Required(V_RESERVE, default=d.get(V_RESERVE, DEFAULT_RESERVE_KM)): _num(0, 600, 5, "km"),
        vol.Required(V_CONSUMPTION, default=d.get(V_CONSUMPTION, DEFAULT_CONSUMPTION_100)): _num(5, 60, 0.5, "kWh/100 km"),
        vol.Required(V_CHARGE_MAX, default=d.get(V_CHARGE_MAX, DEFAULT_CHARGE_MAX)): _num(1.4, 50, 0.1, "kW"),
        vol.Required(V_CHARGE_MIN, default=d.get(V_CHARGE_MIN, DEFAULT_CHARGE_MIN)): _num(0.5, 22, 0.1, "kW"),
        _opt(V_PLUGGED, d): _ent(["binary_sensor", "switch", "input_boolean"]),
        _opt(V_CHARGING, d): _ent(["binary_sensor", "switch", "input_boolean"]),
        _opt(V_WALLBOX_ENERGY, d): _ent("sensor", "energy"),
        _opt(V_DEPARTURE, d): _ent(["time", "datetime", "input_datetime", "sensor"]),
        _opt(V_NOTIFY, d): TextSelector(),
        vol.Required(V_NOTIFY_HOUR, default=d.get(V_NOTIFY_HOUR, DEFAULT_NOTIFY_HOUR)): _num(0, 23, 1, "h"),
    })


def vehicle_title(d: dict[str, Any]) -> str:
    return f"{d.get(V_NAME, '?')} · {d.get(V_CAPACITY, DEFAULT_CAPACITY_KWH):g} kWh · {int(d.get(V_RESERVE, DEFAULT_RESERVE_KM))} km"


class PlugwhenConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="Plugwhen", data={})
        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return PlugwhenOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, config_entry: ConfigEntry) -> dict[str, type[ConfigSubentryFlow]]:
        return {SUBENTRY_VEHICLE: VehicleFlow}


class PlugwhenOptionsFlow(OptionsFlow):
    """Connections to other integrations. Everything is optional: Plugwhen also works alone."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data={k: v for k, v in user_input.items() if v not in (None, "")})
        current = dict(self.config_entry.options)
        if not current.get(O_WAECHTER) and not current.get(O_LOAD):
            found = find_waechter_entry(self.hass)  # offered, not forced
            if found:
                current[O_WAECHTER] = found
        return self.async_show_form(step_id="init", data_schema=vol.Schema({
            _opt(O_WAECHTER, current): ConfigEntrySelector(ConfigEntrySelectorConfig(integration=WAECHTER_DOMAIN)),
            _opt(O_LOAD, current): _ent("sensor"),
            _opt(O_AVAIL, current): _ent("sensor"),
            vol.Required(O_SOLAR, default=current.get(O_SOLAR, True)): BooleanSelector(),
            vol.Required(O_SOLAR_DEDUCT, default=current.get(O_SOLAR_DEDUCT, DEFAULT_SOLAR_DEDUCT)): _num(0, 20, 0.1, "kW"),
            _opt(O_GRID_ENERGY, current): _ent("sensor", "energy"),
            _opt(O_PRICE_LOW, current): _num(0, 5000, 0.01, "/kW/a"),
            _opt(O_PRICE_HIGH, current): _num(0, 5000, 0.01, "/kW/a"),
            _opt(O_PRICE_THRESHOLD, current): _num(0, 100, 0.1, "kW"),
        }))


class VehicleFlow(ConfigSubentryFlow):
    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        return await self._form(user_input, {})

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        return await self._form(user_input, dict(self._get_reconfigure_subentry().data))

    async def _form(self, user_input: dict[str, Any] | None, current: dict[str, Any]) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input[V_ODOMETER] == user_input[V_SOC]:
                errors[V_SOC] = "same_entity"
            elif float(user_input[V_CHARGE_MIN]) > float(user_input[V_CHARGE_MAX]):
                errors[V_CHARGE_MIN] = "min_above_max"
            elif any("." not in x.strip() for x in (user_input.get(V_NOTIFY) or "").split(",") if x.strip()):
                errors[V_NOTIFY] = "notify_format"
            else:
                data = {k: (v.strip() if isinstance(v, str) else v) for k, v in user_input.items() if v not in (None, "")}
                title = vehicle_title(data)
                if self.source == "user":
                    return self.async_create_entry(title=title, data=data)
                return self.async_update_and_abort(self._get_entry(), self._get_reconfigure_subentry(), title=title, data=data)
            current = user_input
        step = "user" if self.source == "user" else "reconfigure"
        return self.async_show_form(step_id=step, data_schema=_vehicle_schema(current), errors=errors)
