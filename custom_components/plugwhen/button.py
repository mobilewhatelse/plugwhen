"""Two buttons: 'Send feedback' sends the text with an overview of the setup (no names, entity ids or values); 'Send bug report'
sends the text (may be empty) together with the bug report (fehlerbericht.py), and the notification then shows exactly what went."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.components.persistent_notification import async_create
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import PlugwhenEntry, fehlerbericht as fb
from .entity import PlugwhenMainEntity

TEXTS = {
    "de": ("Bitte zuerst etwas in das Feld Rückmeldung schreiben.", "Danke, die Rückmeldung ist angekommen.",
           "Senden hat nicht geklappt, bitte später noch einmal."),
    "en": ("Please write something into the feedback field first.", "Thank you, the feedback was received.",
           "Sending failed, please try again later."),
}


async def async_setup_entry(hass: HomeAssistant, entry: PlugwhenEntry, add: AddConfigEntryEntitiesCallback) -> None:
    add([FeedbackButton(entry.runtime_data), ReportButton(entry.runtime_data)])


class FeedbackButton(PlugwhenMainEntity, ButtonEntity):
    """Sends the text of the field 'Feedback' with the overview of the setup."""

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


class ReportButton(PlugwhenMainEntity, ButtonEntity):
    """One press: the text (if any) and the bug report go at once; the notification shows exactly what was sent (or, if sending
    failed, what would have been sent). Independent of 'Share anonymous data'."""

    _attr_icon = "mdi:bug-outline"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, plug) -> None:
        super().__init__(plug, "feedback_report")

    async def async_press(self) -> None:
        p = self.plug
        de = str(self.hass.config.language or "").startswith("de")
        b = p.build_report(dt_util.now())
        ok = await p.send_feedback(p.feedback_text, None, True, b)
        if ok:
            p.feedback_text = ""
            async_dispatcher_send(self.hass, p.signal)
        async_create(self.hass, fb.anzeige(b, de, ok), title="Plugwhen", notification_id="plugwhen_feedback")
