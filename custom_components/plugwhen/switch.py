"""Switch per vehicle: learn the kilometres per weekday (default on, the last state is restored)."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import PlugwhenEntry
from .entity import PlugwhenEntity


async def async_setup_entry(hass: HomeAssistant, entry: PlugwhenEntry, add: AddConfigEntryEntitiesCallback) -> None:
    plug = entry.runtime_data
    for sub_id, v in plug.vehicles.items():
        add([LearnKmSwitch(plug, v)], config_subentry_id=sub_id)


class LearnKmSwitch(PlugwhenEntity, SwitchEntity, RestoreEntity):
    """Off: only the reserve counts; what was learned about the kilometres is ignored."""

    _attr_icon = "mdi:school-outline"

    def __init__(self, plug, vehicle) -> None:
        super().__init__(plug, vehicle, "learn_km")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        self.vehicle.learn_km = last is None or last.state != "off"  # default on

    @property
    def is_on(self) -> bool:
        return self.vehicle.learn_km

    async def async_turn_on(self, **kwargs) -> None:
        self.vehicle.learn_km = True
        self.async_write_ha_state()
        await self.plug.async_recompute(self.vehicle)

    async def async_turn_off(self, **kwargs) -> None:
        self.vehicle.learn_km = False
        self.async_write_ha_state()
        await self.plug.async_recompute(self.vehicle)
