"""Sends what is in the feedback text field, with an overview of the setup (no names, entity ids or values)."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.components.persistent_notification import async_create
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PlugwhenEntry
from .entity import PlugwhenMainEntity

TEXTS = {
    "de": ("Bitte zuerst etwas in das Feld R\u00fcckmeldung schreiben.", "Danke, die R\u00fcckmeldung ist angekommen.",
           "Senden hat nicht geklappt, bitte sp\u00e4ter noch einmal."),
    "en": ("Please write something into the feedback field first.", "Thank you, the feedback was received.",
           "Sending failed, please try again later."),
}


async def async_setup_entry(hass: HomeAssistant, entry: PlugwhenEntry, add: AddConfigEntryEntitiesCallback) -> None:
    add([FeedbackButton(entry.runtime_data)])


class FeedbackButton(PlugwhenMainEntity, ButtonEntity):
    _attr_icon = "mdi:send"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, plug) -> None:
        super().__init__(plug, "feedback_send")

    async def async_press(self) -> None:
        p = self.plug
        empty, thanks, failed = TEXTS["de" if str(self.hass.config.language or "").startswith("de") else "en"]
        if not p.feedback_text.strip():
            msg = empty
        elif await p.send_feedback(p.feedback_text, None, True):
            p.feedback_text = ""
            async_dispatcher_send(self.hass, p.signal)
            msg = thanks
        else:
            msg = failed
        async_create(self.hass, msg, title="Plugwhen", notification_id="plugwhen_feedback")
