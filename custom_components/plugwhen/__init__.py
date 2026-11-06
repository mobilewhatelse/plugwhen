"""Plugwhen: works out when to plug the car in so that it is ready when you leave."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.service import async_register_admin_service

from .const import DOMAIN, PLATFORMS, POTENTIAL_DAYS
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
    _register_services(hass)
    return True


def _register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, "calculate_potential"):
        return

    async def handle(call: ServiceCall) -> dict[str, Any]:
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries or getattr(entries[0], "runtime_data", None) is None:
            raise ServiceValidationError("Plugwhen is not set up")
        plug = entries[0].runtime_data
        out = {}
        for v in plug.vehicles.values():
            r = await plug.async_potential(v, int(call.data.get("days", POTENTIAL_DAYS)))
            out[v.name] = {k: r.get(k) for k in ("status", "verdict", "saving_spread_per_year", "saving_spread_vs_guard_per_year",
                                                 "peak_as_is_kw", "peak_spread_kw", "days", "sessions", "model_error_kw", "missing")}
        from homeassistant.helpers.dispatcher import async_dispatcher_send

        async_dispatcher_send(hass, plug.signal)
        return {"vehicles": out}

    async_register_admin_service(
        hass, DOMAIN, "calculate_potential", handle,
        schema=vol.Schema({vol.Optional("days", default=POTENTIAL_DAYS): vol.All(vol.Coerce(int), vol.Range(min=14, max=365))}),
        supports_response=SupportsResponse.OPTIONAL,
    )

    async def handle_dashboard(call: ServiceCall) -> dict[str, Any]:
        return await _create_dashboard(hass)

    async_register_admin_service(
        hass, DOMAIN, "create_dashboard", handle_dashboard, schema=vol.Schema({}), supports_response=SupportsResponse.OPTIONAL,
    )


async def _create_dashboard(hass: HomeAssistant) -> dict[str, Any]:
    """Build the dashboard with this installation's entity ids (all vehicles) and return it as YAML, also shown as a
    persistent notification, to paste into the raw configuration editor of a new dashboard. It never writes into a dashboard."""
    from homeassistant.helpers import entity_registry as er
    from homeassistant.util import yaml as ha_yaml

    from .dashboard import ENTITY_KEYS, build_views

    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        raise ServiceValidationError("Plugwhen is not set up")
    entry = entries[0]
    registry = er.async_get(hass)
    vehicles = []
    for sub in entry.subentries.values():
        ids: dict[str, str] = {}
        for key, domain in ENTITY_KEYS.items():
            entity_id = registry.async_get_entity_id(domain, DOMAIN, f"{sub.subentry_id}_{key}")
            if entity_id is None:
                raise ServiceValidationError(f"Entity '{key}' of {sub.title} not found - restart Home Assistant after the update")
            ids[key] = entity_id
        vehicles.append({"name": sub.data.get("name", sub.title), "ids": ids})
    if not vehicles:
        raise ServiceValidationError("Add a vehicle first (integration page: Add vehicle)")
    config = {"views": build_views(vehicles, hass.config.language, hass.config.currency)}
    text = ha_yaml.dump(config)
    de = (hass.config.language or "").lower().startswith("de")
    hint = ("In ein neues Dashboard einfügen (drei Punkte > Bearbeiten > Raw-Konfigurationseditor):" if de
            else "Paste this into a new dashboard (three dots > Edit > Raw configuration editor):")
    await hass.services.async_call(
        "persistent_notification", "create",
        {"title": "Plugwhen", "notification_id": f"{DOMAIN}_dashboard", "message": f"{hint}\n\n```yaml\n{text}```"},
    )
    return {"yaml": text, "config": config}


async def async_unload_entry(hass: HomeAssistant, entry: PlugwhenEntry) -> bool:
    await entry.runtime_data.async_stop()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _reload(hass: HomeAssistant, entry: PlugwhenEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
