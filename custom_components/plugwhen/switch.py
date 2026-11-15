"""Switches per vehicle (the last state is restored after a restart): learn the kilometres per weekday, warn (both default on),
once a week full (default off)."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import PlugwhenEntry
from .entity import PlugwhenEntity, PlugwhenMainEntity


async def async_setup_entry(hass: HomeAssistant, entry: PlugwhenEntry, add: AddConfigEntryEntitiesCallback) -> None:
    plug = entry.runtime_data
    for sub_id, v in plug.vehicles.items():
        add([LearnKmSwitch(plug, v), NoticeSwitch(plug, v), WeeklyFullSwitch(plug, v)], config_subentry_id=sub_id)
    add([ShareSwitch(plug)])


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



class ShareSwitch(PlugwhenMainEntity, SwitchEntity, RestoreEntity):
    """The voluntary usage statistics: as chosen in the last step of the set-up (default off), afterwards the last state."""

    _attr_icon = "mdi:chart-donut"

    def __init__(self, plug) -> None:
        super().__init__(plug, "share_usage")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None:
            self.plug.share_usage = last.state == "on"

    @property
    def is_on(self) -> bool:
        return self.plug.share_usage

    async def async_turn_on(self, **kwargs) -> None:
        self.plug.share_usage = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        self.plug.share_usage = False
        self.async_write_ha_state()


class WeeklyFullSwitch(PlugwhenEntity, SwitchEntity, RestoreEntity):
    """On: once a week the car is charged to the full target (days and target are their own settings; vollladen.py). The week in
    which it was full is kept with the state, so a restart does not charge again."""

    _attr_icon = "mdi:battery-charging-100"

    def __init__(self, plug, vehicle) -> None:
        super().__init__(plug, vehicle, "weekly_full")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        self.vehicle.weekly_full = last is not None and last.state == "on"   # default off
        if last is not None and isinstance(last.attributes.get("done_week"), str):
            self.vehicle.weekly_done = last.attributes["done_week"]

    @property
    def is_on(self) -> bool:
        return self.vehicle.weekly_full

    @property
    def extra_state_attributes(self) -> dict:
        v = self.vehicle
        from homeassistant.util import dt as dt_util

        from . import vollladen as vl

        return {"done_week": v.weekly_done, "done": v.weekly_done == vl.week_key(dt_util.now().date()),
                "day": v.weekly_day.isoformat() if v.weekly_day else None, "active": v.weekly_active}

    async def async_turn_on(self, **kwargs) -> None:
        self.vehicle.weekly_full = True
        self.async_write_ha_state()
        await self.plug.async_recompute(self.vehicle)

    async def async_turn_off(self, **kwargs) -> None:
        self.vehicle.weekly_full = False
        self.async_write_ha_state()
        await self.plug.async_recompute(self.vehicle)
