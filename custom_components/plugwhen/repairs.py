"""Questions under Settings > Repairs: share the anonymous usage statistics? (once after an update); and, for those who shared
before 0.10.1, one quiet note to confirm the short text with the list of what is sent (keep sharing, or switch it off)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers.selector import BooleanSelector

from .const import DOMAIN
from .rueckmeldung import privacy_url


def _plugs(hass: HomeAssistant):
    return [e.runtime_data for e in hass.config_entries.async_entries(DOMAIN) if getattr(e, "runtime_data", None) is not None]


def _form(flow: RepairsFlow) -> data_entry_flow.FlowResult:
    """Both questions: one switch (starts off, a consent is an active choice) and the link to the list in the user's language."""
    return flow.async_show_form(step_id="confirm", data_schema=vol.Schema(
        {vol.Required("share_usage", default=False): BooleanSelector()}),
        description_placeholders={"privacy_url": privacy_url(flow.hass.config.language)})


class ShareUsageFlow(RepairsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> data_entry_flow.FlowResult:
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input: dict[str, Any] | None = None) -> data_entry_flow.FlowResult:
        if user_input is not None:
            for plug in _plugs(self.hass):
                plug.answer_usage(bool(user_input.get("share_usage")))
            return self.async_create_entry(data={})
        return _form(self)


class ShareCheckFlow(RepairsFlow):
    """Shared before 0.10.1: keep sharing (the list of this version is then agreed) or switch sharing off."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> data_entry_flow.FlowResult:
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input: dict[str, Any] | None = None) -> data_entry_flow.FlowResult:
        if user_input is not None:
            for plug in _plugs(self.hass):
                plug.confirm_katalog(bool(user_input.get("share_usage")))
            return self.async_create_entry(data={})
        return _form(self)


async def async_create_fix_flow(hass: HomeAssistant, issue_id: str, data: dict[str, Any] | None) -> RepairsFlow:
    if issue_id == "share_usage_check":
        return ShareCheckFlow()
    return ShareUsageFlow()
