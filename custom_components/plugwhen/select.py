"""Select per vehicle: the mode (off or learn; the last choice is restored, default learn)."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import PlugwhenEntry
from .const import DEFAULT_MODE, MODES
from .entity import PlugwhenEntity


async def async_setup_entry(hass: HomeAssistant, entry: PlugwhenEntry, add: AddConfigEntryEntitiesCallback) -> None:
    plug = entry.runtime_data
    for sub_id, v in plug.vehicles.items():
        add([ModeSelect(plug, v)], config_subentry_id=sub_id)


class ModeSelect(PlugwhenEntity, SelectEntity, RestoreEntity):
    """off: Plugwhen only plans and warns. learn: it also writes down what it WOULD switch and compares that with what really
    happened. Nothing is switched in either mode; after a restart the mode is the last one chosen."""

    _attr_options = MODES
    _attr_icon = "mdi:school-outline"

    def __init__(self, plug, vehicle) -> None:
        super().__init__(plug, vehicle, "mode")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        self.vehicle.mode = last.state if last is not None and last.state in MODES else DEFAULT_MODE

    @property
    def current_option(self) -> str:
        return self.vehicle.mode

    async def async_select_option(self, option: str) -> None:
        self.vehicle.mode = option if option in MODES else DEFAULT_MODE
        self.async_write_ha_state()
        await self.plug.async_recompute(self.vehicle)
