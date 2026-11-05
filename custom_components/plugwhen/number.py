"""Number per vehicle: the reserve in kilometres (the car leaves with at least this range)."""

from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberMode, RestoreNumber
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PlugwhenEntry
from .entity import PlugwhenEntity


async def async_setup_entry(hass: HomeAssistant, entry: PlugwhenEntry, add: AddConfigEntryEntitiesCallback) -> None:
    plug = entry.runtime_data
    for sub_id, v in plug.vehicles.items():
        add([ReserveNumber(plug, v)], config_subentry_id=sub_id)


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
