"""One-off: the notify setting may name several services, separated by commas (kept for the record)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def patch(path, pairs):
    p = ROOT / path
    s = p.read_text(encoding="utf-8")
    for a, b in pairs:
        assert s.count(a) == 1, (path, a[:60])
        s = s.replace(a, b)
    p.write_text(s, encoding="utf-8")


patch("custom_components/plugwhen/coordinator.py", [
    ('''        service = str(v.cfg.get(V_NOTIFY) or "").strip()
        if n is None or not v.notice_enabled or v.departure is None or "." not in service:
            return''', '''        services = [x.strip() for x in str(v.cfg.get(V_NOTIFY) or "").split(",") if "." in x]
        if n is None or not v.notice_enabled or v.departure is None or not services:
            return'''),
    ('''        domain, name = service.split(".", 1)
        try:
            await self.hass.services.async_call(domain, name, {"title": title, "message": message}, blocking=False)
        except Exception as err:  # noqa: BLE001 - a wrong service name must not stop the planner
            _LOGGER.warning("Plugwhen: the warning for %s could not be sent through %s: %s", v.name, service, err)
            return
        sent.append(key)''', '''        delivered = 0
        for service in services:
            domain, name = service.split(".", 1)
            try:
                await self.hass.services.async_call(domain, name, {"title": title, "message": message}, blocking=False)
                delivered += 1
            except Exception as err:  # noqa: BLE001 - a wrong service name must not stop the planner or the other phones
                _LOGGER.warning("Plugwhen: the warning for %s could not be sent through %s: %s", v.name, service, err)
        if not delivered:
            return
        sent.append(key)'''),
])
patch("custom_components/plugwhen/config_flow.py", [
    ('''            elif (user_input.get(V_NOTIFY) or "").strip() and "." not in user_input[V_NOTIFY].strip():
                errors[V_NOTIFY] = "notify_format"''', '''            elif any("." not in x.strip() for x in (user_input.get(V_NOTIFY) or "").split(",") if x.strip()):
                errors[V_NOTIFY] = "notify_format"'''),
])
patch("tools/gen_strings.py", [
    ('d_notify="For example notify.mobile_app_phone. Used for the warning that the car will not be ready. Leave empty for none.",',
     'd_notify="One or more notify services, separated by commas, for example notify.mobile_app_phone, notify.mobile_app_tablet. Used for the warning that the car will not be ready. Leave empty for none.",'),
    ('d_notify="Zum Beispiel notify.mobile_app_handy. Für die Warnung, dass das Auto nicht bereit sein wird. Leer lassen für keine.",',
     'd_notify="Ein oder mehrere Benachrichtigungsdienste, durch Komma getrennt, zum Beispiel notify.mobile_app_handy, notify.mobile_app_tablet. Für die Warnung, dass das Auto nicht bereit sein wird. Leer lassen für keine.",'),
    ('e_notify="Enter the service as domain.name, for example notify.mobile_app_phone."',
     'e_notify="Enter each service as domain.name, separated by commas, for example notify.mobile_app_phone."'),
    ('e_notify="Den Dienst als domain.name angeben, zum Beispiel notify.mobile_app_handy."',
     'e_notify="Jeden Dienst als domain.name angeben, durch Komma getrennt, zum Beispiel notify.mobile_app_handy."'),
])
print("ok")
