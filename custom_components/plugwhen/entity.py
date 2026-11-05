"""Common base for the entities of one vehicle."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .coordinator import Plugwhen, Vehicle


class PlugwhenEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, plug: Plugwhen, vehicle: Vehicle, key: str) -> None:
        self.plug = plug
        self.vehicle = vehicle
        self._attr_translation_key = key
        self._attr_unique_id = f"{vehicle.sub_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, vehicle.sub_id)},
            name=vehicle.name,
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Plugwhen",
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(async_dispatcher_connect(self.hass, self.plug.signal, self.async_write_ha_state))
