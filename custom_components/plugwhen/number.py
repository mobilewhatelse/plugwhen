"""Numbers per vehicle: the reserve in kilometres (the car leaves with at least this range), the target of the weekly full charge,
and the two settings of charging for several days (also in the car's settings form: both write the same value)."""

from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode, RestoreNumber
from homeassistant.const import PERCENTAGE, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PlugwhenEntry
from . import vollladen as vl
from . import voraus
from .const import V_DAILY_CAP, V_DAYS_AHEAD
from .entity import PlugwhenEntity


async def async_setup_entry(hass: HomeAssistant, entry: PlugwhenEntry, add: AddConfigEntryEntitiesCallback) -> None:
    plug = entry.runtime_data
    for sub_id, v in plug.vehicles.items():
        add([ReserveNumber(plug, v), WeeklyTargetNumber(plug, v), DaysAheadNumber(plug, v), DailyCapNumber(plug, v)],
            config_subentry_id=sub_id)


class ReserveNumber(PlugwhenEntity, RestoreNumber):
    _attr_device_class = NumberDeviceClass.DISTANCE
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 0
    _attr_native_max_value = 600
    _attr_native_step = 5
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_icon = "mdi:shield-car"

    def __init__(self, plug, vehicle) -> None:
        super().__init__(plug, vehicle, "reserve_km")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_number_data()
        if last is not None and last.native_value is not None:
            self.vehicle.reserve_km = float(last.native_value)

    @property
    def native_value(self) -> float:
        return self.vehicle.reserve_km

    async def async_set_native_value(self, value: float) -> None:
        self.vehicle.reserve_km = float(value)
        self.async_write_ha_state()
        await self.plug.async_recompute(self.vehicle)


class WeeklyTargetNumber(PlugwhenEntity, RestoreNumber):
    """Target of the weekly full charge (default 100 %)."""

    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 50
    _attr_native_max_value = 100
    _attr_native_step = 5
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = "mdi:battery-arrow-up"

    def __init__(self, plug, vehicle) -> None:
        super().__init__(plug, vehicle, "weekly_target")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_number_data()
        self.vehicle.weekly_target = float(last.native_value) if last is not None and last.native_value is not None else vl.DEFAULT_TARGET

    @property
    def native_value(self) -> float:
        return self.vehicle.weekly_target

    async def async_set_native_value(self, value: float) -> None:
        self.vehicle.weekly_target = float(value)
        self.async_write_ha_state()
        await self.plug.async_recompute(self.vehicle)


class _CarSetting(PlugwhenEntity, NumberEntity):
    """A value of the car's settings form on the dashboard. Changing it writes the form's value (no second copy that could
    differ) and computes the plan again, without reloading the integration."""

    _cfg_key = ""
    _default = 0.0

    @property
    def native_value(self) -> float:
        return float(self.vehicle.cfg.get(self._cfg_key, self._default))

    async def async_set_native_value(self, value: float) -> None:
        value = int(value) if float(value).is_integer() else float(value)
        self.vehicle.cfg[self._cfg_key] = value
        entry = self.plug.entry
        sub = entry.subentries.get(self.vehicle.sub_id)
        if sub is not None and sub.data.get(self._cfg_key) != value:
            self.plug.quiet_updates += 1      # the update listener would reload the whole integration for one number
            if not self.hass.config_entries.async_update_subentry(entry, sub, data={**sub.data, self._cfg_key: value}):
                self.plug.quiet_updates -= 1
        self.async_write_ha_state()
        await self.plug.async_recompute(self.vehicle)


class DaysAheadNumber(_CarSetting):
    """Charge for the trips of this many days at once (1 = every day on its own)."""

    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = 1
    _attr_native_max_value = voraus.MAX_DAYS
    _attr_native_step = 1
    # no unit: "3 d" read as English on the dashboard; the name says "days"
    _attr_icon = "mdi:calendar-range"
    _cfg_key = V_DAYS_AHEAD
    _default = voraus.DEFAULT_DAYS

    def __init__(self, plug, vehicle) -> None:
        super().__init__(plug, vehicle, "days_ahead")


class DailyCapNumber(_CarSetting):
    """Charging for several days ends at this state of charge (a long trip or the weekly full charge go above it)."""

    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 50
    _attr_native_max_value = 100
    _attr_native_step = 5
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = "mdi:battery-lock"
    _cfg_key = V_DAILY_CAP
    _default = voraus.DEFAULT_CAP

    def __init__(self, plug, vehicle) -> None:
        super().__init__(plug, vehicle, "daily_cap")
