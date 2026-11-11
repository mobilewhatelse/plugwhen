"""Set-up dialog (one entry), the connections to other integrations (options) and the vehicles as config subentries."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry, ConfigFlow, ConfigFlowResult, ConfigSubentryFlow, OptionsFlow, SubentryFlowResult,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    BooleanSelector, ConfigEntrySelector, ConfigEntrySelectorConfig, EntitySelector, EntitySelectorConfig, NumberSelector, NumberSelectorConfig, NumberSelectorMode,
    SelectOptionDict, SelectSelector, SelectSelectorConfig, SelectSelectorMode, TextSelector, TextSelectorConfig, TextSelectorType,
)

from .const import (
    DEFAULT_CAPACITY_KWH, DEFAULT_CHARGE_MAX, DEFAULT_CHARGE_MIN, DEFAULT_CONSUMPTION_100, DEFAULT_NOTIFY_HOUR,
    DEFAULT_CHARGE_PREF, DEFAULT_RESERVE_KM, DEFAULT_SOC_MAX_AGE_H, DOMAIN, O_AVAIL, O_GRID_ENERGY, O_LOAD, O_PRICE_HIGH, O_PRICE_LOW,
    O_DIRECT_EARLY, O_EVCC_PASSWORD, O_EVCC_URL, O_ROUTE_WAZE, V_CALENDAR, V_EVCC_VEHICLE, V_STOCK, O_PRICE_THRESHOLD, O_SOLAR, O_SOLAR_DEDUCT, O_WAECHTER, SUBENTRY_VEHICLE, V_CAPACITY, V_CHARGE_MAX, V_CHARGE_MIN, V_CHARGE_PREF, V_CHARGING,
    V_CONSUMPTION, V_DEPARTURE, V_NAME, V_NOTIFY, V_NOTIFY_HOUR, V_ODOMETER, V_PLUGGED, V_RESERVE, V_SOC, V_SOC_MAX_AGE, V_WALLBOX_ENERGY,
    O_OUTDOOR_TEMP, O_WEATHER,
)
from .evcc import LOCAL_URLS, PROBE_TIMEOUT_S, EvccAuthError, EvccClient, EvccError, connection, loadpoint_of, match_vehicle, parse_vehicles, vehicle_from_evcc
from .takeover import guard_wallbox, next_vehicle, pick_by_unit, sensor_by_value, vehicle_from_guard
from .units import DISTANCE_UNITS, ENERGY_UNITS, PERCENT_UNITS, unit_errors

WAECHTER_DOMAIN = "viertelstunden_waechter"


def _num(lo: float, hi: float, step: float, unit: str) -> NumberSelector:
    return NumberSelector(NumberSelectorConfig(min=lo, max=hi, step=step, mode=NumberSelectorMode.BOX, unit_of_measurement=unit))


def _ent(domain: str | list[str], device_class: str | None = None) -> EntitySelector:
    if device_class:
        return EntitySelector(EntitySelectorConfig(domain=domain, device_class=device_class))
    return EntitySelector(EntitySelectorConfig(domain=domain))


def _opt(key: str, d: dict[str, Any]) -> vol.Optional:
    return vol.Optional(key, description={"suggested_value": d.get(key)})


WAZE_HINT = {
    "de": "Kilometer von Kalender-Fahrten über Waze: dafür einmal die Integration „Waze Travel Time“ hinzufügen (ohne Konto), dann erscheint hier der Schalter.",
    "en": "Kilometres of calendar trips via Waze: add the integration \u201cWaze Travel Time\u201d once (no account), then the switch appears here.",
}


def waze_ready(hass: HomeAssistant) -> bool:
    """The Waze travel time integration is set up (its action is there)."""
    return bool(hass.config_entries.async_entries("waze_travel_time")) and hass.services.has_service("waze_travel_time", "get_travel_times")


def find_waechter_entry(hass: HomeAssistant) -> str | None:
    """The config entry of the quarter-hour peak guard if there is exactly one (offered in the settings, nothing is imported)."""
    entries = hass.config_entries.async_entries(WAECHTER_DOMAIN)
    return entries[0].entry_id if len(entries) == 1 else None


def _vehicle_schema(d: dict[str, Any], evcc_vehicles: list[dict[str, Any]] | None = None) -> vol.Schema:
    extra: dict[Any, Any] = {}
    if evcc_vehicles:   # only while evcc answers; otherwise the field is left out and a stored value is kept
        extra[_opt(V_EVCC_VEHICLE, d)] = SelectSelector(SelectSelectorConfig(
            options=[SelectOptionDict(value=x["key"], label=x["title"]) for x in evcc_vehicles], mode=SelectSelectorMode.DROPDOWN))
    return vol.Schema({**_vehicle_fields(d), **extra})


def _vehicle_fields(d: dict[str, Any]) -> dict[Any, Any]:
    return ({
        vol.Required(V_NAME, default=d.get(V_NAME, vol.UNDEFINED)): TextSelector(),
        vol.Required(V_ODOMETER, default=d.get(V_ODOMETER, vol.UNDEFINED)): _ent("sensor"),
        vol.Required(V_SOC, default=d.get(V_SOC, vol.UNDEFINED)): _ent("sensor"),
        vol.Required(V_SOC_MAX_AGE, default=d.get(V_SOC_MAX_AGE, DEFAULT_SOC_MAX_AGE_H)): _num(0, 168, 0.01, "h"),
        vol.Required(V_CAPACITY, default=d.get(V_CAPACITY, DEFAULT_CAPACITY_KWH)): _num(5, 250, 0.5, "kWh"),
        vol.Required(V_RESERVE, default=d.get(V_RESERVE, DEFAULT_RESERVE_KM)): _num(0, 600, 5, "km"),
        vol.Required(V_CONSUMPTION, default=d.get(V_CONSUMPTION, DEFAULT_CONSUMPTION_100)): _num(5, 60, 0.5, "kWh/100 km"),
        vol.Required(V_CHARGE_MAX, default=d.get(V_CHARGE_MAX, DEFAULT_CHARGE_MAX)): _num(1.4, 50, 0.1, "kW"),
        vol.Required(V_CHARGE_MIN, default=d.get(V_CHARGE_MIN, DEFAULT_CHARGE_MIN)): _num(0.5, 22, 0.1, "kW"),
        vol.Required(V_CHARGE_PREF, default=d.get(V_CHARGE_PREF, DEFAULT_CHARGE_PREF)): _num(0.5, 50, 0.1, "kW"),
        _opt(V_PLUGGED, d): _ent(["binary_sensor", "switch", "input_boolean"]),
        _opt(V_CHARGING, d): _ent(["binary_sensor", "switch", "input_boolean"]),
        _opt(V_WALLBOX_ENERGY, d): _ent("sensor"),
        _opt(V_DEPARTURE, d): _ent(["time", "datetime", "input_datetime", "sensor"]),
        _opt(V_CALENDAR, d): _ent("calendar"),
        vol.Required(V_STOCK, default=d.get(V_STOCK, 0)): _num(0, 100, 5, "%"),
        _opt(V_NOTIFY, d): TextSelector(),
        vol.Required(V_NOTIFY_HOUR, default=d.get(V_NOTIFY_HOUR, DEFAULT_NOTIFY_HOUR)): _num(0, 23, 1, "h"),
    })


async def evcc_state(hass: HomeAssistant, url: str, password: str | None) -> dict[str, Any]:
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    return await EvccClient(async_get_clientsession(hass), url, password).state()


async def find_local_evcc(hass: HomeAssistant) -> str | None:
    """The address of an evcc on the same machine (add-on), if one answers there within two seconds; offered, never forced."""
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    for url in LOCAL_URLS:
        try:
            await EvccClient(async_get_clientsession(hass), url, None, timeout=PROBE_TIMEOUT_S).state()
            return url
        except EvccAuthError:
            return url   # it is there, it only wants a password
        except EvccError:
            continue
    return None


def _guard_cfg(hass: HomeAssistant, entry: ConfigEntry | None) -> dict[str, Any]:
    wid = (entry.options if entry else {}).get(O_WAECHTER) or find_waechter_entry(hass)
    guard = hass.config_entries.async_get_entry(wid) if wid else None
    return {**guard.data, **guard.options} if guard is not None and guard.domain == WAECHTER_DOMAIN else {}


def vehicle_title(d: dict[str, Any]) -> str:
    return f"{d.get(V_NAME, '?')} · {d.get(V_CAPACITY, DEFAULT_CAPACITY_KWH):g} kWh · {int(d.get(V_RESERVE, DEFAULT_RESERVE_KM))} km"


class PlugwhenConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    # The set-up is an assistant: what was found (guard, evcc, solar forecast), then the cars - each one prefilled from the guard
    # and evcc; what is really needed per car are its odometer and its state of charge.

    def __init__(self) -> None:
        self._options: dict[str, Any] = {}
        self._cars: list[dict[str, Any]] = []
        self._car_note = ""
        self._car_taken: list[str] = []
        self._car_evcc: list[dict[str, Any]] = []
        self._car_proposal: dict[str, Any] = {}

    def _pseudo_entry(self) -> Any:
        """guard_proposal() looks at an entry (the guard it is linked to, the cars it has): the assistant has none yet."""
        subs = {str(i): SimpleNamespace(subentry_type=SUBENTRY_VEHICLE, data=c) for i, c in enumerate(self._cars)}
        return SimpleNamespace(options=self._options, subentries=subs)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Step 1: what is there. An installed guard is connected right away (its grid counter, prices, limit and load forecast are
        then read at run time); evcc is found by its own address, the guard's, or on this machine."""
        found = find_waechter_entry(self.hass)
        guard = _guard_cfg(self.hass, None)
        if user_input is not None and str(user_input.get(O_EVCC_URL) or "").strip():   # an evcc address is tried right away
            try:
                await evcc_state(self.hass, str(user_input[O_EVCC_URL]).strip(), user_input.get(O_EVCC_PASSWORD))
            except EvccAuthError:
                return self.async_show_form(step_id="user", data_schema=vol.Schema({vol.Optional(O_EVCC_URL, description={"suggested_value": user_input.get(O_EVCC_URL)}): TextSelector(),
                                            vol.Optional(O_EVCC_PASSWORD): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))}),
                                            errors={O_EVCC_PASSWORD: "evcc_auth"}, description_placeholders={"guard": "", "evcc": ""})
            except EvccError:
                return self.async_show_form(step_id="user", data_schema=vol.Schema({vol.Optional(O_EVCC_URL, description={"suggested_value": user_input.get(O_EVCC_URL)}): TextSelector(),
                                            vol.Optional(O_EVCC_PASSWORD): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))}),
                                            errors={O_EVCC_URL: "evcc_unreachable"}, description_placeholders={"guard": "", "evcc": ""})
        if user_input is not None:
            self._options = {O_WAECHTER: found} if found else {}
            for key in (O_EVCC_URL, O_EVCC_PASSWORD):
                if user_input.get(key):
                    self._options[key] = str(user_input[key]).strip()
            return await self.async_step_cars()
        local = None if guard.get("evcc_site_url") else await find_local_evcc(self.hass)
        # only symbols and addresses here: the words are in the translations (the language of the user, not of the server)
        guard_txt = "✓" if found else "–"
        evcc_txt = (f"✓ {guard['evcc_site_url']} (Wächter)" if guard.get("evcc_site_url") else f"✓ {local}" if local else "–")
        schema = vol.Schema({} if guard.get("evcc_site_url") else {
            vol.Optional(O_EVCC_URL, description={"suggested_value": local}): TextSelector(),
            vol.Optional(O_EVCC_PASSWORD): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
        })
        return self.async_show_form(step_id="user", data_schema=schema, description_placeholders={"guard": guard_txt, "evcc": evcc_txt})

    async def async_step_cars(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Step 2: the cars. Each car gets its own plan; it can also be added later on the integration page."""
        done = ", ".join(vehicle_title(c) for c in self._cars) or "–"
        return self.async_show_menu(step_id="cars", menu_options=["add_car", "finish"], description_placeholders={"cars": done})

    async def async_step_add_car(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is None:
            taken = {c.get(V_EVCC_VEHICLE) for c in self._cars if c.get(V_EVCC_VEHICLE)}
            proposal, notes, self._car_taken, _, self._car_evcc = await car_proposal(
                self.hass, self._pseudo_entry(), self._options.get(O_EVCC_URL), self._options.get(O_EVCC_PASSWORD), taken)
            self._car_note = ", ".join(notes)
            current = proposal
        else:
            errors = vehicle_errors(self.hass, user_input)
            if not errors:
                data = {k: (v.strip() if isinstance(v, str) else v) for k, v in user_input.items() if v not in (None, "")}
                if self._car_taken:
                    data["taken_from"] = list(self._car_taken)
                self._cars.append(data)
                return await self.async_step_cars()
            current = user_input
        return self.async_show_form(step_id="add_car", data_schema=_vehicle_schema(current, self._car_evcc), errors=errors,
                                    description_placeholders={"taken_over": self._car_note or "–"})

    async def async_step_finish(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Last step: the voluntary, anonymous usage statistics (off unless ticked), then the entry is created."""
        if user_input is None:
            return self.async_show_form(step_id="finish", data_schema=vol.Schema(
                {vol.Required("share_usage", default=False): BooleanSelector()}))
        self._options["share_usage"] = bool(user_input.get("share_usage"))
        subentries = [{"subentry_type": SUBENTRY_VEHICLE, "title": vehicle_title(c), "data": c, "unique_id": None} for c in self._cars]
        return self.async_create_entry(title="Plugwhen", data={}, options=self._options, subentries=subentries)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return PlugwhenOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, config_entry: ConfigEntry) -> dict[str, type[ConfigSubentryFlow]]:
        return {SUBENTRY_VEHICLE: VehicleFlow}


OPTION_UNITS = {O_GRID_ENERGY: (ENERGY_UNITS, "not_energy")}
VEHICLE_UNITS = {V_ODOMETER: (DISTANCE_UNITS, "not_distance"), V_SOC: (PERCENT_UNITS, "not_percent"),
                 V_WALLBOX_ENERGY: (ENERGY_UNITS, "not_energy")}


class PlugwhenOptionsFlow(OptionsFlow):
    """Connections to other integrations. Everything is optional: Plugwhen also works alone."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = unit_errors(self.hass.states.get, user_input, OPTION_UNITS)
            if not errors and str(user_input.get(O_EVCC_URL) or "").strip():   # an own evcc address is tried right away
                try:
                    await evcc_state(self.hass, user_input[O_EVCC_URL], user_input.get(O_EVCC_PASSWORD))
                except EvccAuthError:
                    errors[O_EVCC_PASSWORD] = "evcc_auth"
                except EvccError:
                    errors[O_EVCC_URL] = "evcc_unreachable"
            if not errors:
                return self.async_create_entry(data={k: v for k, v in user_input.items() if v not in (None, "")})
        current = dict(self.config_entry.options) if user_input is None else dict(user_input)
        if not current.get(O_WAECHTER) and not current.get(O_LOAD):
            found = find_waechter_entry(self.hass)  # offered, not forced
            if found:
                current[O_WAECHTER] = found
        if user_input is None and not current.get(O_EVCC_URL) and not _guard_cfg(self.hass, self.config_entry).get("evcc_site_url"):
            local = await find_local_evcc(self.hass)   # offered, not forced: saved only if the form is saved with it
            if local:
                current[O_EVCC_URL] = local
        return self.async_show_form(step_id="init", errors=errors, data_schema=vol.Schema({
            _opt(O_WAECHTER, current): ConfigEntrySelector(ConfigEntrySelectorConfig(integration=WAECHTER_DOMAIN)),
            _opt(O_LOAD, current): _ent("sensor"),
            _opt(O_AVAIL, current): _ent("sensor"),
            _opt(O_OUTDOOR_TEMP, current): _ent("sensor"),
            _opt(O_WEATHER, current): _ent("weather"),
            vol.Required(O_SOLAR, default=current.get(O_SOLAR, True)): BooleanSelector(),
            _opt(O_SOLAR_DEDUCT, current): _num(0, 20, 0.1, "kW"),
            _opt(O_GRID_ENERGY, current): _ent("sensor"),
            _opt(O_PRICE_LOW, current): _num(0, 5000, 0.01, "/kW/a"),
            _opt(O_PRICE_HIGH, current): _num(0, 5000, 0.01, "/kW/a"),
            _opt(O_PRICE_THRESHOLD, current): _num(0, 100, 0.1, "kW"),
            _opt(O_EVCC_URL, current): TextSelector(),
            _opt(O_EVCC_PASSWORD, current): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
            vol.Required(O_DIRECT_EARLY, default=bool(current.get(O_DIRECT_EARLY, False))): BooleanSelector(),
            **({vol.Required(O_ROUTE_WAZE, default=bool(current.get(O_ROUTE_WAZE, False))): BooleanSelector()}
               if waze_ready(self.hass) else {}),
        }), description_placeholders={"waze": "" if waze_ready(self.hass) else WAZE_HINT.get(self.hass.config.language[:2], WAZE_HINT["en"])})




def guard_proposal(hass: HomeAssistant, entry: ConfigEntry) -> tuple[dict[str, Any], str | None]:
    """What the guard already knows about the next car Plugwhen does not have yet: (prefilled values, name) or ({}, None).
    The odometer and the wallbox energy counter are looked up on the same devices as the state of charge and the wallbox
    power. Copied once; nothing here is needed later."""
    wid = entry.options.get(O_WAECHTER) or find_waechter_entry(hass)
    guard = hass.config_entries.async_get_entry(wid) if wid else None
    if guard is None or guard.domain != WAECHTER_DOMAIN:
        return {}, None
    devices = [{**sub.data, "kind": sub.subentry_type, "name": sub.data.get("name") or sub.title} for sub in guard.subentries.values()]
    taken = {sub.data.get(V_SOC) for sub in entry.subentries.values() if sub.subentry_type == SUBENTRY_VEHICLE}
    car = next_vehicle(devices, {t for t in taken if t})
    if car is None:
        return {}, None
    out = vehicle_from_guard(car, devices, {**guard.data, **guard.options}.get("notify_services"))
    odo = _beside(hass, out.get(V_SOC), DISTANCE_UNITS)
    if odo:
        out[V_ODOMETER] = odo
    wb = guard_wallbox(devices) or {}
    counter = _beside(hass, wb.get("power_entity"), ENERGY_UNITS)
    if counter:
        out[V_WALLBOX_ENERGY] = counter
    return out, str(car.get("name") or guard.title)


def _beside(hass: HomeAssistant, entity_id: str | None, units: tuple[str, ...]) -> str | None:
    """A counter sensor with one of `units` on the same device as `entity_id`, or None."""
    if not entity_id:
        return None
    from homeassistant.helpers import entity_registry as er

    reg = er.async_get(hass)
    ent = reg.async_get(entity_id)
    if ent is None or not ent.device_id:
        return None
    cands = []
    for e in er.async_entries_for_device(reg, ent.device_id):
        if e.domain != "sensor" or e.entity_id == entity_id:
            continue
        st = hass.states.get(e.entity_id)
        attrs = st.attributes if st else {}
        cands.append((e.entity_id, attrs.get("unit_of_measurement") or e.unit_of_measurement, attrs.get("state_class")))
    return pick_by_unit(cands, units)




def vehicle_errors(hass: HomeAssistant, u: dict[str, Any]) -> dict[str, str]:
    """The checks of the car form: odometer and state of charge are two different sensors with the right units, minimum below
    maximum, notify services written as notify.xxx."""
    if u[V_ODOMETER] == u[V_SOC]:
        return {V_SOC: "same_entity"}
    errors = unit_errors(hass.states.get, u, VEHICLE_UNITS)
    if errors:
        return errors
    if float(u[V_CHARGE_MIN]) > float(u[V_CHARGE_MAX]):
        return {V_CHARGE_MIN: "min_above_max"}
    if any("." not in x.strip() for x in (u.get(V_NOTIFY) or "").split(",") if x.strip()):
        return {V_NOTIFY: "notify_format"}
    return {}


def _sensors_from_evcc_values(hass: HomeAssistant, state: dict[str, Any] | None, key: str, proposal: dict[str, Any]) -> bool:
    """Fill the odometer and the state-of-charge sensor of the car by their values: evcc reports both for the car at its loadpoint,
    the sensors of the car's integration in Home Assistant show the same numbers. Only empty fields, only an unambiguous hit."""
    from homeassistant.helpers import entity_registry as er

    lp = loadpoint_of(state, key)
    if not lp:
        return False
    reg = er.async_get(hass)

    def cands(units: tuple[str, ...], device: str | None = None) -> list[tuple[str, float, bool]]:
        out = []
        for st in hass.states.async_all("sensor"):
            unit = str(st.attributes.get("unit_of_measurement") or "")
            if unit not in units:
                continue
            try:
                val = float(st.state)
            except (TypeError, ValueError):
                continue
            ent = reg.async_get(st.entity_id)
            if device is not None and (ent is None or ent.device_id != device):
                continue
            if unit in ("mi", "mile", "miles"):
                val *= 1.609344
            out.append((st.entity_id, val, "evcc" not in str(getattr(ent, "platform", "") or "")))
        return out

    def num(x: Any) -> float | None:
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    found = False
    odo = num(lp.get("vehicleOdometer"))
    if not proposal.get(V_ODOMETER) and odo and odo > 0:
        eid = sensor_by_value(cands(DISTANCE_UNITS), odo, 2.0)
        if eid:
            proposal[V_ODOMETER] = eid
            found = True
    soc = num(lp.get("vehicleSoc"))
    if not proposal.get(V_SOC) and soc is not None and proposal.get(V_ODOMETER):
        ent = reg.async_get(proposal[V_ODOMETER])   # the state of charge only from the same device as the odometer: "62 %" alone is not unique
        if ent is not None and ent.device_id:
            eid = sensor_by_value(cands(PERCENT_UNITS, ent.device_id), soc, 2.5)
            if eid:
                proposal[V_SOC] = eid
                found = True
    return found


async def car_proposal(hass: HomeAssistant, entry: Any, own_url: str | None, own_password: str | None,
                       taken_evcc: set[str]) -> tuple[dict[str, Any], list[str], list[str], dict[str, Any] | None, list[dict[str, Any]]]:
    """What the guard and evcc already know about the next car: (values, notes, sources, evcc state, evcc vehicles)."""
    proposal, name = guard_proposal(hass, entry)
    notes = [f"Viertelstunden-Wächter ({name})"] if name else []   # names only: the words are in the translations
    taken = ["guard"] if name else []
    conn = connection(own_url, own_password, _guard_cfg(hass, entry))
    state, vehicles = None, []
    if conn is not None:
        try:
            state = await evcc_state(hass, conn[0], conn[1])
            vehicles = parse_vehicles(state)
        except EvccError:
            state, vehicles = None, []
    if vehicles:
        key = match_vehicle(state, proposal.get(V_NAME), taken_evcc)
        if key:
            found = vehicle_from_evcc(state, key)
            for k, val in found.items():   # the guard's values (sensors of Home Assistant) win
                proposal.setdefault(k, val)
            notes.append(f"evcc ({found.get(V_NAME, key)})")
            if _sensors_from_evcc_values(hass, state, key, proposal):
                notes.append("evcc → Home Assistant (km, %)")
            taken.append("evcc")
    return proposal, notes, taken, state, vehicles


class VehicleFlow(ConfigSubentryFlow):
    _evcc: list[dict[str, Any]] | None = None
    _taken: list[str] | None = None   # "guard", "evcc": where the form was filled in from (shown on the dashboard)

    async def _evcc_vehicles(self) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        """evcc's state and vehicles if an address is known (Plugwhen's own or the guard's) and evcc answers; else (None, [])."""
        entry = self._get_entry()
        conn = connection(entry.options.get(O_EVCC_URL), entry.options.get(O_EVCC_PASSWORD), _guard_cfg(self.hass, entry))
        if conn is None:
            return None, []
        try:
            state = await evcc_state(self.hass, conn[0], conn[1])
        except EvccError:
            return None, []
        return state, parse_vehicles(state)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        if user_input is None:
            entry = self._get_entry()
            taken = {sub.data.get(V_EVCC_VEHICLE) for sub in entry.subentries.values() if sub.subentry_type == SUBENTRY_VEHICLE}
            proposal, notes, self._taken, _, self._evcc = await car_proposal(
                self.hass, entry, entry.options.get(O_EVCC_URL), entry.options.get(O_EVCC_PASSWORD), {t for t in taken if t})
            return await self._form(None, proposal, ", ".join(notes))
        return await self._form(user_input, {})

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        if user_input is None:
            _, self._evcc = await self._evcc_vehicles()
        return await self._form(user_input, dict(self._get_reconfigure_subentry().data))

    async def _form(self, user_input: dict[str, Any] | None, current: dict[str, Any], note: str = "") -> SubentryFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = vehicle_errors(self.hass, user_input)
            if not errors:
                data = {k: (v.strip() if isinstance(v, str) else v) for k, v in user_input.items() if v not in (None, "")}
                if self.source == "user" and self._taken:
                    data["taken_from"] = list(self._taken)
                elif self.source != "user" and self._get_reconfigure_subentry().data.get("taken_from"):
                    data["taken_from"] = self._get_reconfigure_subentry().data["taken_from"]
                if self.source != "user" and not self._evcc and V_EVCC_VEHICLE not in user_input:   # evcc not reachable: keep the car
                    old = self._get_reconfigure_subentry().data.get(V_EVCC_VEHICLE)
                    if old:
                        data[V_EVCC_VEHICLE] = old
                title = vehicle_title(data)
                if self.source == "user":
                    return self.async_create_entry(title=title, data=data)
                return self.async_update_and_abort(self._get_entry(), self._get_reconfigure_subentry(), title=title, data=data)
            current = user_input
        step = "user" if self.source == "user" else "reconfigure"
        return self.async_show_form(step_id=step, data_schema=_vehicle_schema(current, self._evcc), errors=errors,
                                    description_placeholders={"taken_over": note or "–"})
