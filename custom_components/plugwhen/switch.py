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
        add([LearnKmSwitch(plug, v), NoticeSwitch(plug, v), WeeklyFullSwitch(plug, v)]
            + [WeeklyDaySwitch(plug, v, wd) for wd in range(7)], config_subentry_id=sub_id)
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

    @property
    def extra_state_attributes(self) -> dict:
        """The latest messages to the phone (newest first), for the dashboard: a message swiped away stays readable."""
        return {"recent": self.plug.recent_messages(self.vehicle)}

    async def async_turn_on(self, **kwargs) -> None:
        self.vehicle.notice_enabled = True
        self.async_write_ha_state()
        await self.plug.async_recompute(self.vehicle)

    async def async_turn_off(self, **kwargs) -> None:
        self.vehicle.notice_enabled = False
        self.async_write_ha_state()
        await self.plug.async_recompute(self.vehicle)


class WeeklyDaySwitch(PlugwhenEntity, SwitchEntity, RestoreEntity):
    """One weekday of the weekly full charge (Monday to Sunday, shown as a bar on the dashboard). Several ticked: the sunniest of
    them, without a forecast the first. Default Saturday and Sunday; a choice from the former selection is carried over."""

    def __init__(self, plug, vehicle, weekday: int) -> None:
        super().__init__(plug, vehicle, f"weekly_day_{weekday}")
        self.weekday = weekday

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        from . import vollladen as vl

        last = await self.async_get_last_state()
        if last is not None and last.state in ("on", "off"):
            on = last.state == "on"
        else:
            on = self.weekday in (self.vehicle.weekly_days_old or vl.DEFAULT_DAY_SET)
        self._set(on)

    def _set(self, on: bool) -> None:
        days = set(self.vehicle.weekly_days)
        (days.add if on else days.discard)(self.weekday)
        self.vehicle.weekly_days = frozenset(days)

    @property
    def is_on(self) -> bool:
        return self.weekday in self.vehicle.weekly_days

    @property
    def icon(self) -> str:
        """A ticked day shows a filled check, an unticked one an empty circle (the day bar shows which days are chosen)."""
        return "mdi:check-circle" if self.is_on else "mdi:circle-outline"

    async def async_turn_on(self, **kwargs) -> None:
        self._set(True)
        self.vehicle.weekly_done = None   # the user ticks a day: "once more this week" opens the week again
        self.async_write_ha_state()
        await self.plug.async_recompute(self.vehicle)

    async def async_turn_off(self, **kwargs) -> None:
        self._set(False)
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
        if last is not None:   # a full charge kept for a departure survives a restart in the night
            from datetime import date as _date

            from homeassistant.util import dt as dt_util

            hold, day = dt_util.parse_datetime(str(last.attributes.get("hold_until") or "")), last.attributes.get("hold_day")
            if hold is not None and isinstance(day, str):
                try:
                    self.vehicle.weekly_hold, self.vehicle.weekly_hold_day = hold, _date.fromisoformat(day)
                except ValueError:
                    pass

    @property
    def is_on(self) -> bool:
        return self.vehicle.weekly_full

    @property
    def extra_state_attributes(self) -> dict:
        v = self.vehicle
        from homeassistant.util import dt as dt_util

        from . import vollladen as vl

        return {"done_week": v.weekly_done, "done": v.weekly_done == vl.week_key(dt_util.now().date()),
                "day": v.weekly_day.isoformat() if v.weekly_day else None, "active": v.weekly_active,
                "hold_until": v.weekly_hold.isoformat() if v.weekly_hold else None,
                "hold_day": v.weekly_hold_day.isoformat() if v.weekly_hold_day else None}

    async def async_turn_on(self, **kwargs) -> None:
        self.vehicle.weekly_full = True
        self.vehicle.weekly_done = None   # switched on by the user: a done week is open again
        self.async_write_ha_state()
        await self.plug.async_recompute(self.vehicle)

    async def async_turn_off(self, **kwargs) -> None:
        self.vehicle.weekly_full = False
        self.async_write_ha_state()
        await self.plug.async_recompute(self.vehicle)
