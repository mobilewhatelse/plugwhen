"""The text field for a feedback (sent with the button next to it)."""

from __future__ import annotations

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PlugwhenEntry
from .entity import PlugwhenMainEntity


async def async_setup_entry(hass: HomeAssistant, entry: PlugwhenEntry, add: AddConfigEntryEntitiesCallback) -> None:
    add([FeedbackText(entry.runtime_data)])


class FeedbackText(PlugwhenMainEntity, TextEntity):
    _attr_icon = "mdi:message-text-outline"
    _attr_mode = TextMode.TEXT
    _attr_native_max = 255
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, plug) -> None:
        super().__init__(plug, "feedback_text")

    @property
    def native_value(self) -> str:
        return self.plug.feedback_text

    async def async_set_value(self, value: str) -> None:
        self.plug.feedback_text = value or ""
        self.async_write_ha_state()
