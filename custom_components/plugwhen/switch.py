"""Switches per vehicle (the last state is restored after a restart): learn the kilometres per weekday (default on), warn
(default on), write the plan into evcc (default off; only for a car linked to an evcc car)."""

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
        add([LearnKmSwitch(plug, v), NoticeSwitch(plug, v)], config_subentry_id=sub_id)
        if v.cfg.get("evcc_vehicle"):   # only a car linked to evcc has it
            add([EvccWriteSwitch(plug, v)], config_subentry_id=sub_id)


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


class NoticeSwitch(PlugwhenEntity, SwitchEntity, RestoreEntity):
    """Off: no warning is sent that the car will not be ready (the readiness sensor still shows it)."""

    _attr_icon = "mdi:bell-ring-outline"

    def __init__(self, plug, vehicle) -> None:
        super().__init__(plug, vehicle, "notice_enabled")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        self.vehicle.notice_enabled = last is None or last.state != "off"  # default on

    @property
    def is_on(self) -> bool:
        return self.vehicle.notice_enabled

    async def async_turn_on(self, **kwargs) -> None:
        self.vehicle.notice_enabled = True
        self.async_write_ha_state()
        await self.plug.async_recompute(self.vehicle)

    async def async_turn_off(self, **kwargs) -> None:
        self.vehicle.notice_enabled = False
        self.async_write_ha_state()
        await self.plug.async_recompute(self.vehicle)


class EvccWriteSwitch(PlugwhenEntity, SwitchEntity, RestoreEntity):
    """On: the plan for the next departure that needs charging is written into evcc and kept up to date. Only plans Plugwhen wrote
    itself are changed; a plan set in evcc by hand is never touched. Default off; the state is kept over a restart."""

    _attr_icon = "mdi:calendar-sync"

    def __init__(self, plug, vehicle) -> None:
        super().__init__(plug, vehicle, "evcc_write")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        self.vehicle.evcc_write_on = last is not None and last.state == "on"  # default off

    @property
    def is_on(self) -> bool:
        return self.vehicle.evcc_write_on

    async def async_turn_on(self, **kwargs) -> None:
        self.vehicle.evcc_write_on = True
        self.async_write_ha_state()
        await self.plug.async_write_evcc_now(self.vehicle)

    async def async_turn_off(self, **kwargs) -> None:
        self.vehicle.evcc_write_on = False
        self.async_write_ha_state()
        await self.plug.async_recompute(self.vehicle)
