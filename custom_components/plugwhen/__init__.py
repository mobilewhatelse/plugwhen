"""Plugwhen: works out when to plug the car in so that it is ready when you leave."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import Plugwhen

type PlugwhenEntry = ConfigEntry[Plugwhen]


async def async_setup_entry(hass: HomeAssistant, entry: PlugwhenEntry) -> bool:
    from .config_flow import vehicle_title  # imported here: config_flow pulls in the selector helpers

    for sub in list(entry.subentries.values()):  # keep the list titles current
        title = vehicle_title(dict(sub.data))
        if sub.title != title:
            hass.config_entries.async_update_subentry(entry, sub, title=title)
    plug = Plugwhen(hass, entry)
    entry.runtime_data = plug
    # entities first: the reserve and the switch restore their last values before the first computation
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await plug.async_start()
    entry.async_on_unload(entry.add_update_listener(_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PlugwhenEntry) -> bool:
    await entry.runtime_data.async_stop()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _reload(hass: HomeAssistant, entry: PlugwhenEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
