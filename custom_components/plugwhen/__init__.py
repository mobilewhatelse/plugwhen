"""Plugwhen: works out when to plug the car in so that it is ready when you leave."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
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
    _carry_over_weekly_days(hass, plug)
    # entities first: the reserve and the switch restore their last values before the first computation
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await plug.async_start()
    entry.async_on_unload(entry.add_update_listener(_reload))
    _register_services(hass)
    return True


def _carry_over_weekly_days(hass: HomeAssistant, plug: Plugwhen) -> None:
    """Builds of 0.9.2 before the day bar had a selection of days ("Saturday or Sunday" …). Its last choice is handed to the new
    day switches (they take it when they have no state of their own yet), then the selection is removed from the registry so no
    'unavailable' entity is left behind."""
    from homeassistant.helpers import entity_registry as er
    from homeassistant.helpers.restore_state import async_get as restore_data

    from . import vollladen as vl

    registry = er.async_get(hass)
    for sub_id, v in plug.vehicles.items():
        eid = registry.async_get_entity_id("select", DOMAIN, f"{sub_id}_weekly_days")
        if eid is None:
            continue
        try:
            stored = restore_data(hass).last_states.get(eid)
            v.weekly_days_old = vl.days_of(stored.state.state if stored is not None else None)
        except Exception:  # noqa: BLE001 - a missing restore cache only means the default days
            v.weekly_days_old = None
        registry.async_remove(eid)


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

    async def handle_feedback(call: ServiceCall) -> dict[str, Any]:
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries or getattr(entries[0], "runtime_data", None) is None:
            raise ServiceValidationError("Plugwhen is not set up")
        if not await entries[0].runtime_data.send_feedback(call.data["text"], call.data.get("contact"), call.data["include_setup"]):
            raise ServiceValidationError("Sending the feedback failed (no connection, or the text is empty)")
        return {"sent": True}

    hass.services.async_register(
        DOMAIN, "send_feedback", handle_feedback,
        schema=vol.Schema({vol.Required("text"): vol.All(cv.string, vol.Length(min=1, max=4000)),
                           vol.Optional("contact"): vol.All(cv.string, vol.Length(max=200)),
                           vol.Optional("include_setup", default=True): cv.boolean}),
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
        vehicles.append({"name": sub.data.get("name", sub.title), "ids": ids, "calendar": sub.data.get("trip_calendar"),
                         "evcc": bool(sub.data.get("evcc_vehicle"))})
    if not vehicles:
        raise ServiceValidationError("Add a vehicle first (integration page: Add vehicle)")
    main_ids = {k: registry.async_get_entity_id(d, DOMAIN, f"{entry.entry_id}_{k}")
                for k, d in (("feedback_text", "text"), ("feedback_send", "button"), ("share_usage", "switch"),
                             ("feedback_report", "button"))}
    config = {"views": build_views(vehicles, hass.config.language, hass.config.currency,
                                   {k: v for k, v in main_ids.items() if v},
                                   waechter=bool(hass.config_entries.async_entries("viertelstunden_waechter")))}
    text = ha_yaml.dump(config)
    de = (hass.config.language or "").lower().startswith("de")
    hint = ("In ein neues Dashboard einfügen (drei Punkte > Bearbeiten > Raw-Konfigurationseditor):" if de
            else "Paste this into a new dashboard (three dots > Edit > Raw configuration editor):")
    await hass.services.async_call(
        "persistent_notification", "create",
        {"title": "Plugwhen", "notification_id": f"{DOMAIN}_dashboard", "message": f"{hint}\n\n```yaml\n{text}```"},
    )
    # the response is the dashboard itself: copied whole from the developer tools it fits the raw configuration editor as it is
    return config


async def async_unload_entry(hass: HomeAssistant, entry: PlugwhenEntry) -> bool:
    await entry.runtime_data.async_stop()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _reload(hass: HomeAssistant, entry: PlugwhenEntry) -> None:
    plug = getattr(entry, "runtime_data", None)
    if plug is not None and plug.quiet_updates > 0:   # a number on the dashboard wrote the car's settings: already applied
        plug.quiet_updates -= 1
        return
    await hass.config_entries.async_reload(entry.entry_id)
