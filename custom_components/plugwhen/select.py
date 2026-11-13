"""Select per vehicle: the mode (off, learn, evcc, direct; the last choice is restored after a restart, default learn)."""

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
    happened. evcc (only for a car linked to evcc): like learn, and the plan for the next needed departure is written into evcc,
    evcc charges; only plans Plugwhen wrote itself are changed. Only one of the two ever switches: you choose. After a restart the
    mode is the last one chosen."""

    _attr_icon = "mdi:school-outline"

    def __init__(self, plug, vehicle) -> None:
        super().__init__(plug, vehicle, "mode")

    @property
    def options(self) -> list[str]:
        """With evcc only evcc controls: a car linked to evcc gets 'evcc', a car without evcc gets 'direct' (once the wallbox can be
        controlled and the learn mode is through, or released early). Never both: evcc's "off" blocks charging, so Plugwhen cannot
        control a wallbox evcc controls."""
        from homeassistant.util import dt as dt_util

        v = self.vehicle
        out = ["off", "learn"]
        if v.cfg.get("evcc_vehicle"):
            out.append("evcc")
        elif v.mode == "direct" or self.plug.direct_offered(v, dt_util.now()):
            out.append("direct")
        return out

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        self.vehicle.mode = last.state if last is not None and last.state in MODES else DEFAULT_MODE
        if self.vehicle.mode == "direct" and self.vehicle.cfg.get("evcc_vehicle"):
            self.vehicle.mode = "evcc"   # linked to evcc since: evcc controls

    @property
    def current_option(self) -> str:
        return self.vehicle.mode

    async def async_select_option(self, option: str) -> None:
        self.vehicle.mode = option if option in self.options else DEFAULT_MODE
        self.async_write_ha_state()
        if self.vehicle.mode == "evcc":
            await self.plug.async_write_evcc_now(self.vehicle)
        else:
            await self.plug.async_recompute(self.vehicle)
