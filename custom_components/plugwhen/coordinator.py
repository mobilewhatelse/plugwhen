"""Connects the learning, the need, the plan and the warning with Home Assistant."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later, async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    DEFAULT_CHARGE_MAX, DEFAULT_CHARGE_MIN, DEFAULT_MODE, LEARNING_MODES, DEFAULT_CONSUMPTION_100, DEFAULT_NOTIFY_HOUR, DEFAULT_RESERVE_KM, DEFAULT_SOC_MAX_AGE_H, DOMAIN,
    HISTORY_DAYS, HISTORY_INTERVAL, O_AVAIL, O_GRID_ENERGY, O_LOAD, O_PRICE_HIGH, O_PRICE_LOW, O_PRICE_THRESHOLD,
    O_DIRECT_EARLY, O_EVCC_PASSWORD, O_EVCC_URL, O_ROUTE_WAZE, V_CALENDAR, V_EVCC_VEHICLE, V_STOCK, O_SOLAR, O_SOLAR_DEDUCT, DEFAULT_SOLAR_DEDUCT, SOLAR_REFRESH, O_WAECHTER, POTENTIAL_DAYS, POTENTIAL_FIXED_KW, POTENTIAL_INTERVAL, POTENTIAL_QUARTER_ADD_KW, SUBENTRY_VEHICLE, UPDATE_INTERVAL, V_CAPACITY, V_CHARGE_MAX,
    V_CHARGE_MIN, V_CHARGING, V_CONSUMPTION, V_DEPARTURE, V_NAME, V_NOTIFY, V_NOTIFY_HOUR, V_ODOMETER, V_PLUGGED,
    V_RESERVE, V_SOC, V_SOC_MAX_AGE, V_WALLBOX_ENERGY, V_WALLBOX_MORE, V_CHARGE_PREF, DEFAULT_CHARGE_PREF, CALIBRATE_INTERVAL,
    O_OUTDOOR_TEMP, O_WEATHER, WEATHER_REFRESH,
)
from dataclasses import replace

from . import direct_stats, flotte
from . import rueckmeldung as rm

from .evcc import EvccClient, EvccError, connection as evcc_connection, live_vehicle, loadpoint_index
from .evcc_plan import decide_write, evcc_plan
from .readiness import switch_readiness
from .direct import detect as detect_wallbox, in_grid_window, next_action, trip_settings
from .trips import (GEO_MISS, address_variants, coordinates, event_days, parse_geocode, range_for_trip, trip_km, trips_from_events,
                    waze_region)
from .freshness import soc_is_stale
from .calibrate import QuarterAddModel, SolarAccuracy, base_load_from_hourly, efficiency_from_records, quarter_add_samples
from .habit import charging_habit
from .history import records_from_hourly, to_km, to_kwh
from .insight import learning_check
from .links import pick
from .inputs import availability_from_attributes, departure_from_state, load_from_hours, merge_available, surplus_from_solar
from .plugs import PlugLog
from .learning import MobilityModel, WeekdayPlan
from .horizon import Trip, horizon_plan, with_calendar
from .messages import ahead_text, notice_text
from .need import MIN_SAMPLES, Need, compute_need
from .startwerte import charge_efficiency
from .notice import Notice, ahead_key, check_ahead, check_ready, dedupe_key, remember_sent, should_check
from .plan import make_plan
from .shadow import Decision, ShadowLog, decide
from .potential import Prices, calculate as calculate_potential, clean_grid
from .wallboxes import active_wallbox, car_hourly, cumulative, plan_order, shared, soc_rise_hours, taken_by_others, wallbox_ids

_LOGGER = logging.getLogger(__name__)
_BAD = (None, "", STATE_UNKNOWN, STATE_UNAVAILABLE)


def _to_celsius(value: Any, unit: str | None) -> float | None:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return round((x - 32.0) / 1.8, 2) if (unit or "").strip().upper() in ("°F", "F", "DEGF") else x
LOOKAHEAD_DAYS = 7
HORIZON_DAYS = 14             # days looked at for the look-ahead (as far as possible: with normal behaviour, when is charging needed?)
HORIZON_TRIPS = 10            # departures in the look-ahead
SOLAR_CHECK_DAYS = 7                    # past days the solar check looks at
TRIPS_REFRESH = timedelta(minutes=15)   # the calendar is read this often
MIN_DRIVE_SHARE = 0.5        # a weekday counts as a day of departure if the car is used on at least half of its days
SHARED_COMPACT = 0.75        # at a shared wallbox a plan charges with at least this share of the wallbox power
SENT_KEEP = 8                # warnings remembered per vehicle (so that a restart does not repeat them)


@dataclass
class Vehicle:
    sub_id: str
    name: str
    cfg: dict[str, Any]
    reserve_km: float = DEFAULT_RESERVE_KM
    learn_km: bool = True
    notice_enabled: bool = True
    model: MobilityModel = field(default_factory=MobilityModel)
    plan: WeekdayPlan | None = None
    need: Need | None = None
    charge_plan: dict[str, Any] | None = None
    notice: Notice | None = None
    consumption: float = DEFAULT_CONSUMPTION_100 / 100.0   # kWh per km used for the need
    consumption_source: str = "config"                     # learned, config, curve, rule, rule_config (learning.consumption_at)
    departure_temp_c: float | None = None                  # outdoor temperature expected at the departure (None = not known)
    departure: datetime | None = None
    departure_source: str | None = None                    # "entity" or "learned"
    soc: float | None = None
    soc_age_s: float | None = None   # seconds since the state of charge was written
    soc_stale: bool = False          # too old: counts as unknown
    plugged: bool | None = None
    charging: bool = False
    history_days: int = 0
    trip_days_skipped: int = 0   # days of the trip calendar left out of the learning (special trips)
    history_at: datetime | None = None
    history_error: str | None = None
    availability_used: bool = False
    load_used: bool = False
    potential: dict[str, Any] | None = None
    potential_at: datetime | None = None
    plug_log: PlugLog = field(default_factory=PlugLog)
    availability_source: str | None = None   # "entity", "solar", "entity+solar" or None
    plug_seeding: bool = False               # the recorder history is being read: do not write meanwhile
    records: list = field(default_factory=list)   # daily records of the history (for the check of the learning)
    insight_cache: tuple | None = None       # ((reserve, number of records, loaded at), result)
    efficiency: float | None = None          # learned share of the wallbox energy that reaches the battery (None = default)
    habit: dict | None = None                # when the car is charged (per weekday: day, night, in between)
    horizon: dict | None = None              # look-ahead over the next departures (deficits, pre-charging with the sun)
    mode: str = DEFAULT_MODE                 # "off" or "learn" (nothing is switched in either)
    decision: Decision | None = None         # what would be switched now (learn mode)
    shadow: ShadowLog = field(default_factory=ShadowLog)
    evcc_live: dict | None = None            # plugged in / charging of this car at its evcc loadpoint (None = not known)
    trips: list = field(default_factory=list)   # trips from the car's calendar: departure, title, location, km, km_source, range_km
    trips_at: datetime | None = None
    trips_error: str | None = None
    evcc_write: dict | None = None           # last write into evcc: {at, action, reason, error}
    direct_last: dict | None = None          # last action of the mode 'direct' on the wallbox
    wallbox_active: str | None = None        # energy counter of the wallbox the car is at (several wallboxes, see wallboxes.py)
    wallbox_seen: dict = field(default_factory=dict)   # last counter values, to see which one rises
    others_kw: dict | None = None            # what the cars planned before this one (per quarter hour), for the attributes
    fleet_model: str | None = None           # car model for the fleet values (maker and model of the state of charge's device)
    fleet_cars: int | None = None            # how many cars the fleet value in use comes from


class Plugwhen:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.signal = f"{DOMAIN}_{entry.entry_id}_update"
        self.share_usage = bool(entry.options.get("share_usage"))   # voluntary anonymous usage statistics (default off, rueckmeldung.py)
        self.feedback_text = ""
        self._usage: dict[str, Any] = {}
        self._usage_busy = False
        self._usage_shared_seen = self.share_usage
        # fleet values (flotte.py): {"autos": {sub_id: {"bis", "gemeldet"}}, "schluessel", "gueltig_bis", "modelle", "at"}
        self._fleet: dict[str, Any] = {}
        self._fleet_busy = False
        self.vehicles: dict[str, Vehicle] = {}
        self._unsub = None
        self._unsub_states = None
        self._pending = None
        self._store: Store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.sent")
        self._sent: dict[str, list[str]] = {}
        self._plug_store: Store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.plugs")
        self._shadow_store: Store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.shadow")
        self._calib_store: Store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.calib")
        self._evcc_store: Store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.evcc")   # the plans Plugwhen wrote into evcc
        self._written: dict[str, dict] = {}
        self._routes: dict[str, dict] = {}   # destination -> {"km", "at"} from the route service (one way)
        self._direct: dict[str, dict] = {}   # per car: entity -> {"set", "orig"} what the mode 'direct' set on the wallbox
        self._geo: dict[str, str] = {}       # location text -> "lat,lon" (OpenStreetMap search, kept)
        self._calib: dict[str, Any] = {"quarter_add_kw": None, "base_load_kw": None, "at": None}
        self._calib_at: datetime | None = None
        self._solar_acc = SolarAccuracy()
        self._add_model = QuarterAddModel()
        self._solar: dict[datetime, float] | None = None
        self._solar_at: datetime | None = None
        self._wx: dict[datetime, float] = {}       # hourly outdoor temperature forecast (local hour start -> deg C)
        self._wx_at: datetime | None = None
        self.solar_check: dict[str, Any] = {}   # forecasts remembered and days measured (shown at the charge plan)
        self.evcc_state: dict[str, Any] | None = None   # last state read from evcc (only while a vehicle names its evcc car)
        self.evcc_info: dict[str, Any] = {}             # where evcc is, whether it answered (for the sensors)
        for sub in entry.subentries.values():
            if sub.subentry_type == SUBENTRY_VEHICLE:
                d = dict(sub.data)
                self.vehicles[sub.subentry_id] = Vehicle(
                    sub.subentry_id, d.get(V_NAME, "?"), d, reserve_km=float(d.get(V_RESERVE, DEFAULT_RESERVE_KM)))

    # ---------- life cycle ----------

    async def async_start(self) -> None:
        self._sent = (await self._store.async_load() or {}).get("sent", {})
        ev = await self._evcc_store.async_load() or {}
        self._written = ev.get("written", {}) if isinstance(ev.get("written"), dict) else {}
        self._routes = ev.get("routes", {}) if isinstance(ev.get("routes"), dict) else {}
        self._direct = ev.get("direct", {}) if isinstance(ev.get("direct"), dict) else {}
        self._geo = ev.get("geo", {}) if isinstance(ev.get("geo"), dict) else {}
        self._usage = ev.get("usage", {}) if isinstance(ev.get("usage"), dict) else {}
        self._fleet = ev.get("flotte", {}) if isinstance(ev.get("flotte"), dict) else {}
        if not self._usage.get("seit"):   # only for the rough class "running since"; stays here, never sent as a date
            created = getattr(self.entry, "created_at", None)
            self._usage["seit"] = (created if isinstance(created, datetime) else dt_util.now()).isoformat()
        if int(self.entry.options.get("zustimmung") or 0) > int(self._usage.get("zustimmung") or 0):
            self._usage["zustimmung"] = int(self.entry.options["zustimmung"])   # agreed in the set-up to the current text
        self.ask_usage_once()
        plugs = (await self._plug_store.async_load() or {}).get("vehicles", {})
        shadows = (await self._shadow_store.async_load() or {}).get("vehicles", {})
        calib = await self._calib_store.async_load() or {}
        if isinstance(calib.get("calib"), dict):
            self._calib.update({k: calib["calib"].get(k) for k in ("quarter_add_kw", "base_load_kw", "at")})
        self._solar_acc = SolarAccuracy(calib.get("solar"))
        self._add_model = QuarterAddModel(calib.get("add"))
        for v in self.vehicles.values():
            v.shadow = ShadowLog(shadows.get(v.sub_id))
        for v in self.vehicles.values():
            v.plug_log = PlugLog(plugs.get(v.sub_id))
            if not v.plug_log.items and v.cfg.get(V_PLUGGED):   # first start: what the recorder still has (a few days)
                v.plug_seeding = True
                self.entry.async_create_background_task(self.hass, self._seed_plugs(v), f"{DOMAIN} plug history")
        self._unsub = async_track_time_interval(self.hass, self._tick, UPDATE_INTERVAL)
        watched = {self._load_entity(), self.entry.options.get(O_AVAIL)}
        for v in self.vehicles.values():
            watched |= {v.cfg.get(k) for k in (V_SOC, V_PLUGGED, V_CHARGING, V_DEPARTURE)}
        watched.discard(None)
        if watched:  # react when the car is plugged in, starts charging or a departure is set, not only every five minutes
            self._unsub_states = async_track_state_change_event(self.hass, list(watched), self._state_changed)
        self.entry.async_create_background_task(self.hass, self._tick(), f"{DOMAIN} first run")

    async def async_stop(self) -> None:
        for unsub in (self._unsub, self._unsub_states, self._pending):
            if unsub:
                unsub()
        self._unsub = self._unsub_states = self._pending = None

    def _state_changed(self, _event) -> None:
        """Compute again shortly after a watched entity changed (several changes at once count as one)."""
        if self._pending is None:
            self._pending = async_call_later(self.hass, 2, self._after_change)

    async def _after_change(self, _now: datetime) -> None:
        self._pending = None
        now = dt_util.now()
        self._compute(None, now)
        async_dispatcher_send(self.hass, self.signal)
        await self._send_and_act(now)

    async def _send_and_act(self, now: datetime) -> None:
        """Warnings, the plan for evcc and the wallbox (mode 'direct'). Also in the regular run: a window of the plan begins at a time,
        not when a sensor changes (a sleeping car at night does not report its state of charge for hours)."""
        acted = False
        for v in self.vehicles.values():
            await self._maybe_send(v, now)
            before = (v.evcc_write, v.direct_last)
            await self._write_evcc(v, now)
            await self._direct_step(v, now)
            acted = acted or before != (v.evcc_write, v.direct_last)
        if acted:   # show at once what was written into evcc or set on the wallbox, not only at the next run
            async_dispatcher_send(self.hass, self.signal)

    async def async_write_evcc_now(self, vehicle: Vehicle) -> None:
        """The mode 'evcc' was chosen: read evcc, write at once (not only at the next run) and show it."""
        now = dt_util.now()
        await self._refresh_evcc(now)
        self._compute(vehicle, now)
        await self._write_evcc(vehicle, now)
        async_dispatcher_send(self.hass, self.signal)

    async def async_recompute(self, vehicle: Vehicle) -> None:
        """A setting of the vehicle changed (reserve, switch): compute again and tell the entities."""
        now = dt_util.now()
        self._compute(vehicle, now)
        async_dispatcher_send(self.hass, self.signal)
        await self._maybe_send(vehicle, now)

    async def _tick(self, _now: datetime | None = None) -> None:
        now = dt_util.now()
        if self.entry.options.get(O_SOLAR, True) and (self._solar_at is None or now - self._solar_at >= SOLAR_REFRESH):
            self._solar_at = now
            self._solar = await self._solar_kw()
            self._note_solar_prediction(now)
            await self._check_solar(now)
        if self._calib_at is None or now - self._calib_at >= CALIBRATE_INTERVAL:
            self._calib_at = now
            self.entry.async_create_background_task(self.hass, self._calibrate(now), f"{DOMAIN} calibrate")
        if self._wx_at is None or now - self._wx_at >= WEATHER_REFRESH:
            self._wx_at = now
            await self._refresh_weather()
        await self._refresh_evcc(now)
        self._usage_step(now)
        self._fleet_step(now)
        for v in self.vehicles.values():
            if v.cfg.get(V_CALENDAR) and (v.trips_at is None or now - v.trips_at >= TRIPS_REFRESH):
                await self._refresh_trips(v, now)
        for v in self.vehicles.values():
            if v.history_at is None or now - v.history_at >= HISTORY_INTERVAL:
                await self._load_history(v, now)
        self._compute(None, now)
        for v in self.vehicles.values():
            if v.potential_at is None or now - v.potential_at >= POTENTIAL_INTERVAL:
                v.potential_at = now
                self.entry.async_create_background_task(self.hass, self._potential_and_tell(v), f"{DOMAIN} potential")
        async_dispatcher_send(self.hass, self.signal)
        await self._send_and_act(now)

    # ---------- evcc (optional, read only) ----------

    def evcc_connection(self) -> tuple[str, str | None, str] | None:
        """(url, password, source) of evcc: Plugwhen's own setting, else the guard's, else None."""
        return evcc_connection(self.entry.options.get(O_EVCC_URL), self.entry.options.get(O_EVCC_PASSWORD), self._waechter_cfg())

    # ---------- trips from a calendar (optional) ----------

    async def _refresh_trips(self, v: Vehicle, now: datetime) -> None:
        """Read the car's calendar for the next 14 days. Kilometres: written in the event, else (if switched on) the route to the location
        from the Waze travel time integration, cached per destination. A failure keeps the last trips."""
        v.trips_at = now
        cal = v.cfg.get(V_CALENDAR)
        try:
            resp = await self.hass.services.async_call("calendar", "get_events", {"entity_id": cal, "start_date_time": now,
                                                       "end_date_time": now + timedelta(days=14)}, blocking=True, return_response=True)
            events = ((resp or {}).get(cal) or {}).get("events", [])
        except Exception as err:  # noqa: BLE001 - optional: without the calendar Plugwhen plans as before
            v.trips_error = str(err)[:120]
            _LOGGER.debug("Plugwhen: calendar %s not readable: %s", cal, err)
            return
        v.trips_error = None
        out = []
        for t in trips_from_events(events, now):
            route = await self._route_km(t.get("location"), now) if not t.get("km_given") else None
            km, src = trip_km(t, route)
            out.append({**t, "departure": t["departure"].isoformat(), "km": km, "km_source": src,
                        "range_km": range_for_trip(km, v.reserve_km) if km else None})
        v.trips = out

    async def _calendar_days(self, v: Vehicle, now: datetime) -> set:
        """The dates of the past events in the car's trip calendar (the learning period); empty without a calendar or on a failure."""
        cal = v.cfg.get(V_CALENDAR)
        if not cal:
            return set()
        try:
            resp = await self.hass.services.async_call("calendar", "get_events", {"entity_id": cal, "start_date_time": now - timedelta(days=HISTORY_DAYS),
                                                       "end_date_time": now}, blocking=True, return_response=True)
        except Exception as err:  # noqa: BLE001 - then nothing is left out, as before
            _LOGGER.debug("Plugwhen: calendar %s not readable for the learning: %s", cal, err)
            return set()
        return event_days(((resp or {}).get(cal) or {}).get("events", []), now.tzinfo, )

    async def _route_km(self, location: str | None, now: datetime) -> float | None:
        """One-way kilometres from home to `location` (Waze travel time, only if switched on and installed); cached for a week."""
        if not location or not self.entry.options.get(O_ROUTE_WAZE):
            return None
        hit = self._routes.get(location)
        if hit and hit.get("at") and now - datetime.fromisoformat(hit["at"]) < timedelta(days=7):
            return hit.get("km")
        if not self.hass.services.has_service("waze_travel_time", "get_travel_times"):
            return None
        dest = coordinates(location) or await self._geocode(location)   # Waze's own address search fails: coordinates work
        if dest is None:
            return None
        try:
            resp = await self.hass.services.async_call("waze_travel_time", "get_travel_times", {
                "origin": "zone.home", "destination": dest, "region": waze_region(self.hass.config.country)},
                blocking=True, return_response=True)
            routes = (resp or {}).get("routes") or []
            km = round(min(float(r["distance"]) for r in routes if r.get("distance")), 1) if routes else None
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Plugwhen: route to %s not found: %s", location, err)
            return None
        if km:
            self._routes[location] = {"km": km, "at": now.isoformat()}
            self._evcc_store.async_delay_save(self._evcc_data, 10)
        return km

    async def _geocode(self, location: str) -> str | None:
        """Coordinates of a location text from OpenStreetMap (Nominatim), kept for good. Only the location goes there, not home.
        An address with door, staircase or floor ("Stiege 2") is not found as written: then the street alone, then postcode and
        town. A location found nowhere is not asked again for a week."""
        known = self._geo.get(location)
        if known and not known.startswith(GEO_MISS):
            return known
        if known and dt_util.utcnow() - datetime.fromisoformat(known[len(GEO_MISS):]) < timedelta(days=7):
            return None
        from homeassistant.helpers.aiohttp_client import async_get_clientsession

        hit = None
        for i, query in enumerate(address_variants(location)):
            if i:
                await asyncio.sleep(1.1)   # OpenStreetMap asks for at most one request per second
            try:
                async with asyncio.timeout(10):
                    async with async_get_clientsession(self.hass).get(
                            "https://nominatim.openstreetmap.org/search", params={"q": query, "format": "json", "limit": "1"},
                            headers={"User-Agent": "Plugwhen (Home Assistant integration; github.com/mobilewhatelse/plugwhen)",
                                     "Accept-Language": self.hass.config.language or "en"}) as resp:
                        data = await resp.json(content_type=None) if resp.status == 200 else None
            except Exception as err:  # noqa: BLE001 - offline or slow: try again next time, nothing is remembered
                _LOGGER.debug("Plugwhen: location %s not found: %s", query, err)
                return None
            hit = parse_geocode(data)
            if hit:
                break
        self._geo[location] = hit or GEO_MISS + dt_util.utcnow().isoformat()
        self._evcc_store.async_delay_save(self._evcc_data, 10)
        return hit

    # ---------- voluntary usage statistics and feedback (rueckmeldung.py) ----------

    def setup_overview(self) -> dict[str, Any]:
        """What is set up, without names, entity ids or values: number of cars, modes, the integrations the entities come from."""
        from homeassistant.helpers import entity_registry as er

        reg = er.async_get(self.hass)
        ids: list[str] = []
        modes: dict[str, int] = {}
        control: dict[str, int] = {}
        for v in self.vehicles.values():
            ids += [x for k, x in v.cfg.items() if str(k).endswith("_entity") and isinstance(x, str)]
            modes[v.mode] = modes.get(v.mode, 0) + 1
            var = str(self.wallbox_control(v).get("variant") or "keine")
            control[var] = control.get(var, 0) + 1

        def platform(eid: str) -> str | None:
            ent = reg.async_get(eid)
            return ent.platform if ent else None

        o = self.entry.options
        return {
            "autos": len(self.vehicles), "betriebsarten": modes, "wallbox_steuerung": control,
            "herkunft": rm.herkunft(ids, platform),
            "evcc": any(v.cfg.get(V_EVCC_VEHICLE) for v in self.vehicles.values()) or bool(o.get(O_EVCC_URL)),
            "waechter": bool(o.get(O_WAECHTER)), "solarprognose": bool(o.get(O_SOLAR, True)), "waze": bool(o.get(O_ROUTE_WAZE)),
            "kalender": sum(1 for v in self.vehicles.values() if v.cfg.get(V_CALENDAR)),
            "vorrat": sum(1 for v in self.vehicles.values() if float(v.cfg.get(V_STOCK) or 0) > 0),
        }

    def _version(self) -> tuple[str, str]:
        from homeassistant.const import __version__ as ha_version
        from homeassistant.loader import async_get_loaded_integration

        try:
            ver = str(async_get_loaded_integration(self.hass, DOMAIN).version or "?")
        except Exception:  # noqa: BLE001
            ver = "?"
        return ver, ha_version

    def ask_usage_once(self) -> None:
        """An installation from before the question (set up without the last step of the assistant): ask once, in Settings >
        Repairs. Not again after an answer or after "ignore"."""
        from homeassistant.helpers import issue_registry as ir

        self.ask_reconfirm()
        if "share_usage" in self.entry.options:
            self._usage["gefragt"] = True   # answered in the set-up; a later change of the settings must not ask again
            return
        if self._usage.get("gefragt") or self.share_usage:
            return
        ir.async_create_issue(self.hass, DOMAIN, "share_usage_question", is_fixable=True, is_persistent=False,
                              severity=ir.IssueSeverity.WARNING, translation_key="share_usage_question")

    @property
    def consent_current(self) -> bool:
        """Agreed to the current text (monthly id, extra values, all purposes)? Only then the extra values go out."""
        return int(self._usage.get("zustimmung") or 0) >= rm.ZUSTIMMUNG

    def ask_reconfirm(self) -> None:
        """Shares under an older text: ask once to confirm the current one (Settings > Repairs). Until then only what the older
        text named goes out; without a tick sharing is switched off and the data deleted."""
        from homeassistant.helpers import issue_registry as ir

        if self.share_usage and not self.consent_current:
            ir.async_create_issue(self.hass, DOMAIN, "share_usage_reconfirm", is_fixable=True, is_persistent=False,
                                  severity=ir.IssueSeverity.WARNING, translation_key="share_usage_reconfirm")
        else:
            ir.async_delete_issue(self.hass, DOMAIN, "share_usage_reconfirm")

    def answer_usage(self, share: bool) -> None:
        self.share_usage = bool(share)
        self._usage["gefragt"] = True
        if share:
            self._usage["zustimmung"] = rm.ZUSTIMMUNG
        self.ask_reconfirm()
        self._evcc_store.async_delay_save(self._evcc_data, 1)
        from homeassistant.helpers.dispatcher import async_dispatcher_send

        async_dispatcher_send(self.hass, self.signal)

    def _usage_step(self, now: datetime) -> None:
        """Weekly while the switch is on; once 'delete' after it was switched off. Runs in the background, never blocks."""
        if self._usage_busy:
            return
        if self.share_usage != self._usage_shared_seen:   # the switch was moved: ask again or remove the question
            self._usage_shared_seen = self.share_usage
            self.ask_reconfirm()
        if not (self.share_usage and self.consent_current):
            self._usage.pop("wallbox", None)   # nothing kept that would not be sent
        old = rm.zu_loeschen(self._usage, self.share_usage)
        if old:   # the fixed id of older versions (once), or every monthly id after switching off
            daten = rm.loeschen(DOMAIN, old)
        elif self.share_usage and rm.faellig(self._usage.get("gesendet"), now):
            ver, ha = self._version()
            daten = rm.statistik(DOMAIN, ver, ha, rm.kennung_fuer(self._usage, now), self.hass.config.country,
                                 self.hass.config.language, self.setup_overview(), rm.laeuft_seit(self._usage.get("seit"), now),
                                 self.usage_extras(now) if self.consent_current else None)
            _LOGGER.debug("Plugwhen: usage statistics to send: %s", daten)
        else:
            return
        self._usage_busy = True
        self.entry.async_create_background_task(self.hass, self._usage_send(daten, now), f"{DOMAIN} usage")

    async def _usage_send(self, daten: dict[str, Any], now: datetime) -> None:
        from homeassistant.helpers.aiohttp_client import async_get_clientsession

        try:
            ok = await rm.senden(async_get_clientsession(self.hass), rm.ZIEL_STATISTIK, daten)
            if daten.get("loeschen"):
                if ok:
                    rm.geloescht(self._usage, daten["kennung"])
            else:
                self._usage["gesendet"] = now.isoformat()   # sent or not: next try in a week
                if ok:
                    self._usage.pop("wallbox", None)        # counted afresh for the next week
            self._evcc_store.async_delay_save(self._evcc_data, 5)
        finally:
            self._usage_busy = False

    async def send_feedback(self, text: str, kontakt: str | None, mit_einrichtung: bool) -> bool:
        from homeassistant.helpers.aiohttp_client import async_get_clientsession

        if not str(text or "").strip():
            return False
        ver, ha = self._version()
        daten = rm.rueckmeldung(DOMAIN, ver, ha, text, kontakt, self.setup_overview() if mit_einrichtung else None)
        return await rm.senden(async_get_clientsession(self.hass), rm.ZIEL_RUECKMELDUNG, daten)

    def _evcc_data(self) -> dict[str, Any]:
        return {"written": self._written, "routes": self._routes, "direct": self._direct, "geo": self._geo, "usage": self._usage,
                "flotte": self._fleet}

    # ---------- fleet values (flotte.py): trip days out, models in; only with sharing, never disturbs ----------

    def _car_model(self, v: Vehicle) -> str | None:
        """Maker and model of the device the state of charge belongs to (e.g. "mercedes-benz eqa 250+")."""
        from homeassistant.helpers import device_registry as dr, entity_registry as er

        ent = er.async_get(self.hass).async_get(v.cfg.get(V_SOC) or "")
        dev = dr.async_get(self.hass).async_get(ent.device_id) if ent and ent.device_id else None
        return flotte.model_name(dev.manufacturer, dev.model) if dev else None

    def _fleet_step(self, now: datetime) -> None:
        if not self.share_usage:
            if self._fleet.get("schluessel") or self._fleet.get("modelle"):   # switched off: forget key and models
                self._fleet = {"autos": self._fleet.get("autos", {})}
                self._evcc_store.async_delay_save(self._evcc_data, 5)
            return
        if self._fleet_busy or not flotte.due(self._fleet.get("at"), now):
            return
        if not any(v.records for v in self.vehicles.values()):
            return   # the history is not read yet: next run
        self._fleet_busy = True
        self.entry.async_create_background_task(self.hass, self._fleet_run(now), f"{DOMAIN} fleet")

    async def _fleet_run(self, now: datetime) -> None:
        from homeassistant.helpers.aiohttp_client import async_get_clientsession

        session = async_get_clientsession(self.hass)
        ver, _ha = self._version()
        headers = {"User-Agent": f"{DOMAIN}/{ver}"}
        try:
            cars = self._fleet.setdefault("autos", {})
            for v in self.vehicles.values():
                if not v.fleet_model or not v.records:
                    continue
                car = cars.setdefault(v.sub_id, {})
                after = None
                try:
                    after = datetime.fromisoformat(car["bis"]).date() if car.get("bis") else None
                except ValueError:
                    pass
                days, last = flotte.trip_days(v.records, v.fleet_model, float(v.cfg.get(V_CAPACITY) or 0) or 60.0, after, now.date())
                charges = flotte.charge_days(v.records, v.fleet_model, float(v.cfg.get(V_CAPACITY) or 0), after, now.date())
                parked = (flotte.parked_days(v.records, v.fleet_model, float(v.cfg.get(V_CAPACITY) or 0) or 60.0, after, now.date())
                          if self.consent_current else None)
                if days:
                    async with asyncio.timeout(15):
                        async with session.post(flotte.ZIEL_SENDEN, json=flotte.payload(days, not car.get("gemeldet"), charges, parked),
                                                headers=headers) as r:
                            if r.status != 200:
                                _LOGGER.debug("Plugwhen: fleet send answered %s", r.status)
                                continue   # service off or full: the same days again tomorrow
                            ans = await r.json(content_type=None)
                    if isinstance(ans, dict) and ans.get("schluessel"):
                        self._fleet["schluessel"], self._fleet["gueltig_bis"] = str(ans["schluessel"]), ans.get("gueltig_bis")
                    if isinstance(ans, dict) and isinstance(ans.get("modell"), dict):   # which model of its list the service took
                        self._fleet.setdefault("gruppe", {}).update({str(k): str(x) for k, x in ans["modell"].items() if x})
                    car["gemeldet"] = True
                if last is not None:
                    car["bis"] = last.isoformat()
            if self._fleet.get("schluessel"):
                async with asyncio.timeout(15):
                    async with session.get(flotte.ZIEL_MODELLE, headers=headers | {"X-Schluessel": self._fleet["schluessel"]}) as r:
                        if r.status == 200:
                            m = await r.json(content_type=None)
                            if isinstance(m, dict) and m.get("schema") == 1:
                                self._fleet["modelle"] = m
                        elif r.status in (401, 403):
                            self._fleet.pop("schluessel", None)   # expired: a new one comes with the next days sent
        except Exception as err:  # noqa: BLE001 - the fleet values must never disturb Plugwhen
            _LOGGER.debug("Plugwhen: fleet values: %s", err)
        finally:
            self._fleet["at"] = now.isoformat()   # sent or not: next try tomorrow
            self._fleet_busy = False
            self._evcc_store.async_delay_save(self._evcc_data, 5)

    def usage_extras(self, now: datetime) -> dict[str, Any] | None:
        """The extra values of the weekly statistics (only with the current consent): condensed, rounded, as classes."""
        extra: dict[str, Any] = {}
        devices = direct_stats.summary(self._usage.get("wallbox") or {})
        if devices:
            extra["geraete"] = devices
        return extra or None

    def fleet_info(self, v: Vehicle) -> dict[str, Any]:
        """For the sensor and the dashboard: is sharing on, which model, whether fleet values are in use."""
        models = self._fleet.get("modelle") if self.share_usage else None
        return {"sharing": self.share_usage, "model": v.fleet_model,
                "in_use": v.consumption_source in ("fleet_model", "fleet_all"), "cars": v.fleet_cars,
                "fetched": (models or {}).get("erzeugt")}

    def _trip_at(self, v: Vehicle, dep: datetime | None) -> dict[str, Any] | None:
        """The calendar trip departing at `dep` (same minute), if any."""
        if dep is None:
            return None
        for t in v.trips:
            d = dt_util.parse_datetime(t["departure"])
            if d is not None and abs((d - dep).total_seconds()) < 60:
                return t
        return None

    def _next_trip(self, v: Vehicle, now: datetime) -> dict[str, Any] | None:
        for t in v.trips:
            d = dt_util.parse_datetime(t["departure"])
            if d is not None and d > now:
                return t
        return None

    def _plan_for(self, v: Vehicle, dep: datetime | None, weekday: int) -> WeekdayPlan:
        """The weekday's learned plan; for a calendar trip with kilometres the trip decides the range."""
        p = v.model.plan(weekday)
        t = self._trip_at(v, dep)
        if t and t.get("range_km"):
            p = replace(p, km_typical=t["km"], km_high=t["range_km"], samples=max(p.samples, MIN_SAMPLES), home_charge_share=None)
        return p

    # ---------- mode 'direct': Plugwhen controls the wallbox ----------

    def wallboxes(self, v: Vehicle) -> list[str]:
        """The energy counters of the car's wallboxes (its own field first, then the further ones)."""
        return wallbox_ids(v.cfg.get(V_WALLBOX_ENERGY), v.cfg.get(V_WALLBOX_MORE))

    def shared_wallboxes(self) -> set[str]:
        """Counters of wallboxes more than one car uses."""
        return shared({x.sub_id: self.wallboxes(x) for x in self.vehicles.values()})

    def wallbox_now(self, v: Vehicle) -> str | None:
        """The counter of the wallbox the car is at (the last one found rising), else its first one."""
        ids = self.wallboxes(v)
        return v.wallbox_active if v.wallbox_active in ids else (ids[0] if ids else None)

    def _car_energy(self, v: Vehicle, stats: dict[str, Any], soc: list[tuple[datetime, float | None]]) -> dict[datetime, float] | None:
        """Energy per hour into this car from its wallboxes (a shared wallbox counts only while the car's state of charge rose)."""
        ids = self.wallboxes(v)
        if not ids:
            return None
        changes = {}
        for wid in ids:
            unit = self._unit(wid)
            changes[wid] = {dt_util.as_local(dt_util.utc_from_timestamp(r["start"])): to_kwh(float(r["change"]), unit)
                            for r in stats.get(wid, []) if r.get("change") is not None}
        return car_hourly(changes, self.shared_wallboxes(), soc_rise_hours(soc))

    def wallbox_control(self, v: Vehicle) -> dict[str, Any]:
        """What the car's wallbox offers, found on its device (the device of the wallbox it is at, the plug or charging sensor)."""
        from homeassistant.helpers import entity_registry as er

        reg = er.async_get(self.hass)
        device = None
        for eid in (self.wallbox_now(v), v.cfg.get(V_CHARGING), v.cfg.get(V_PLUGGED)):
            ent = reg.async_get(eid or "")
            if ent is not None and ent.device_id:
                device = ent.device_id
                break
        if device is None:
            return {"variant": None}
        cands = []
        for e in er.async_entries_for_device(reg, device):
            st = self.hass.states.get(e.entity_id)
            attrs = st.attributes if st else {}
            cands.append({"entity_id": e.entity_id, "domain": e.domain, "options": attrs.get("options"), "unit": attrs.get("unit_of_measurement")})
        return detect_wallbox(sorted(cands, key=lambda c: c["entity_id"]))

    def direct_offered(self, v: Vehicle, now: datetime) -> bool:
        """The mode 'direct' is offered once the wallbox can be controlled and the learn mode is through."""
        if not self.wallbox_control(v).get("variant"):
            return False
        return bool(self.entry.options.get(O_DIRECT_EARLY)) or self.switch_ready(v, now)["ready"]

    async def _set_entity(self, entity_id: str, value: Any) -> None:
        """Set a wallbox entity; with the current consent also count how the wallbox follows (direct_stats.py)."""
        try:
            await self._call_entity(entity_id, value)
        except Exception:
            self._wallbox_reply(entity_id, False)
            raise
        if value is not None and entity_id.split(".", 1)[0] in ("select", "time", "number"):
            self._watch_reply(entity_id, value)

    def _wallbox_key(self, entity_id: str) -> str | None:
        """Integration, model and firmware of the wallbox (never a name or serial), or None without the current consent."""
        if not (self.share_usage and self.consent_current):
            return None
        from homeassistant.helpers import device_registry as dr, entity_registry as er

        ent = er.async_get(self.hass).async_get(entity_id)
        dev = dr.async_get(self.hass).async_get(ent.device_id) if ent and ent.device_id else None
        return direct_stats.key(ent.platform if ent else None, dev.model if dev else None, dev.sw_version if dev else None)

    def _wallbox_reply(self, entity_id: str, ok: bool, seconds: float | None = None, k: str | None = None) -> None:
        k = k or self._wallbox_key(entity_id)
        if k:
            direct_stats.record(self._usage.setdefault("wallbox", {}), k, ok, seconds)
            self._evcc_store.async_delay_save(self._evcc_data, 30)

    def _watch_reply(self, entity_id: str, value: Any) -> None:
        """Wait (without blocking) until the entity shows `value`: the time counts; nothing within REPLY_S counts as not taken."""
        k = self._wallbox_key(entity_id)
        if not k:
            return
        start = dt_util.utcnow()
        unsubs: list = []

        def same(state: Any) -> bool:
            if str(state) in (str(value), f"{value}.0", f"{value}:00"):
                return True
            try:
                return abs(float(state) - float(value)) < 1e-6
            except (TypeError, ValueError):
                return False

        def finish(ok: bool) -> None:
            if not unsubs:
                return
            for u in unsubs:
                u()
            unsubs.clear()
            self._wallbox_reply(entity_id, ok, (dt_util.utcnow() - start).total_seconds() if ok else None, k)

        @callback
        def changed(event) -> None:
            new = event.data.get("new_state")
            if new is not None and same(new.state):
                finish(True)

        st = self.hass.states.get(entity_id)
        if st is not None and same(st.state):   # already there when the call returned
            self._wallbox_reply(entity_id, True, (dt_util.utcnow() - start).total_seconds(), k)
            return
        unsubs.append(async_track_state_change_event(self.hass, [entity_id], changed))
        unsubs.append(async_call_later(self.hass, direct_stats.REPLY_S, lambda _now: finish(False)))

    async def _call_entity(self, entity_id: str, value: Any) -> None:
        domain = entity_id.split(".", 1)[0]
        if domain == "select":
            await self.hass.services.async_call("select", "select_option", {"entity_id": entity_id, "option": value}, blocking=True)
        elif domain == "time":
            await self.hass.services.async_call("time", "set_value", {"entity_id": entity_id, "time": value}, blocking=True)
        elif domain == "number":
            await self.hass.services.async_call("number", "set_value", {"entity_id": entity_id, "value": value}, blocking=True)
        elif domain == "button":
            await self.hass.services.async_call("button", "press", {"entity_id": entity_id}, blocking=True)

    async def _own(self, v: Vehicle, entity_id: str, wanted: Any) -> str | None:
        """Set `entity_id` to `wanted` (None = give back) - only what Plugwhen set itself is changed back."""
        mine = self._direct.setdefault(v.sub_id, {})
        st = self.hass.states.get(entity_id)
        current = st.state if st is not None else None
        rec = mine.get(entity_id, {})
        action, value = next_action(current, wanted, rec.get("set"), rec.get("orig"))
        if action is None:
            if value == "user_changed" or (wanted is None and rec):
                mine.pop(entity_id, None)   # the user took over, or nothing left to give back
            return None
        await self._set_entity(entity_id, value)
        if action == "set":
            mine[entity_id] = {"set": value, "orig": rec.get("orig", current)}
        else:
            mine.pop(entity_id, None)
        return f"{entity_id}={value}"

    async def _evcc_loadpoint_mode(self, v: Vehicle, wanted: str | None) -> str | None:
        """Set evcc's mode of the car's loadpoint (mode 'direct': off, so evcc does not regulate the same wallbox); give it back
        afterwards - only what Plugwhen set itself."""
        key, conn = v.cfg.get(V_EVCC_VEHICLE), self.evcc_connection()
        lp = loadpoint_index(self.evcc_state, key) if key and self.evcc_state is not None else None
        mine = self._direct.setdefault(v.sub_id, {})
        rec = mine.get("evcc_loadpoint", {})
        if lp is None or conn is None:
            return None
        action, value = next_action(lp[1], wanted, rec.get("set"), rec.get("orig"))
        if action is None:
            if value == "user_changed" or (wanted is None and rec):
                mine.pop("evcc_loadpoint", None)
            return None
        from homeassistant.helpers.aiohttp_client import async_get_clientsession

        await EvccClient(async_get_clientsession(self.hass), conn[0], conn[1]).set_loadpoint_mode(lp[0], value)
        if action == "set":
            mine["evcc_loadpoint"] = {"set": value, "orig": rec.get("orig", lp[1])}
        else:
            mine.pop("evcc_loadpoint", None)
        return f"evcc loadpoint {lp[0]}={value}"

    async def _direct_step(self, v: Vehicle, now: datetime) -> None:
        """The mode decides who controls, and Plugwhen sets what belongs to it (only what it set itself is given back):
        direct - the wallbox's base mode is its sun mode (e.g. Eco), before a departure the next-trip mode or the grid mode (evcc must
        only read this wallbox: evcc's "off" blocks charging, it is not touched); evcc - the wallbox's grid mode (e.g. Default), evcc
        regulates; off/learn - everything Plugwhen set is given back."""
        caps = self.wallbox_control(v)
        variant = caps.get("variant")
        done: list[str] = []
        try:
            if v.mode == "direct" and variant:
                if variant == "trip":
                    ts = trip_settings(v.need.charge_kwh if v.need else None, v.departure, now, caps.get("trip_energy_unit"))
                    if ts:
                        for eid, val in ((caps["trip_time"], ts["time"]), (caps["trip_energy"], ts["energy"])):
                            st = self.hass.states.get(eid)
                            if st is None or str(st.state) not in (str(val), f"{val}.0"):
                                await self._set_entity(eid, val)
                                done.append(f"{eid}={val}")
                    r = await self._own(v, caps["mode"], caps["mode_trip"] if ts else caps.get("mode_sun"))
                    done += [r] if r else []
                elif variant == "mode":
                    windows = (v.charge_plan or {}).get("windows")
                    r = await self._own(v, caps["mode"], caps["mode_grid"] if in_grid_window(windows, now) else caps.get("mode_sun"))
                    done += [r] if r else []
                elif variant == "buttons":
                    mine = self._direct.setdefault(v.sub_id, {})
                    active = in_grid_window((v.charge_plan or {}).get("windows"), now)
                    if active and not mine.get("started"):
                        await self._set_entity(caps["start"], None)
                        mine["started"] = now.isoformat()
                        done.append(caps["start"])
                    elif not active and mine.get("started"):
                        await self._set_entity(caps["stop"], None)
                        mine.pop("started", None)
                        done.append(caps["stop"])
                # evcc's loadpoint is left alone: "off" in evcc means charging blocked, not "evcc keeps out". For 'direct' evcc must
                # only read the wallbox (or not be there); a mode Plugwhen set earlier is given back.
                r = await self._evcc_loadpoint_mode(v, None)
                done += [r] if r else []
            elif v.mode == "evcc":
                if caps.get("mode") and caps.get("mode_grid"):   # evcc regulates: the wallbox charges when evcc lets it
                    r = await self._own(v, caps["mode"], caps["mode_grid"])
                    done += [r] if r else []
                r = await self._evcc_loadpoint_mode(v, None)
                done += [r] if r else []
            else:   # off / learn: give back everything Plugwhen set
                for eid in [e for e in self._direct.get(v.sub_id, {}) if "." in e]:
                    r = await self._own(v, eid, None)
                    done += [r] if r else []
                mine = self._direct.get(v.sub_id, {})
                if mine.get("started"):   # Plugwhen pressed start: press stop, or the wallbox keeps charging from the grid
                    if variant == "buttons" and caps.get("stop"):
                        await self._set_entity(caps["stop"], None)
                        done.append(caps["stop"])
                    mine.pop("started", None)
                r = await self._evcc_loadpoint_mode(v, None)
                done += [r] if r else []
        except Exception as err:  # noqa: BLE001 - a wallbox or evcc that does not answer must not stop the planner
            v.direct_last = {"at": now.isoformat(), "mode": v.mode, "variant": variant, "error": str(err)[:120]}
            _LOGGER.warning("Plugwhen: wallbox of %s not controlled: %s", v.name, err)
            return
        if done:
            v.direct_last = {"at": now.isoformat(), "mode": v.mode, "variant": variant, "done": done, "error": None}
            self._evcc_store.async_delay_save(self._evcc_data, 5)

    def _min_soc(self, v: Vehicle) -> float:
        """Never plan below this: the stock for unplanned trips (setting), at least 20 %."""
        return max(20.0, float(v.cfg.get(V_STOCK) or 0.0))

    def evcc_plan_for(self, v: Vehicle, now: datetime) -> dict[str, Any] | None:
        if not v.cfg.get(V_EVCC_VEHICLE):
            return None
        ahead, week, reason, lasts = self.evcc_plan_inputs(v, now)
        key = v.cfg[V_EVCC_VEHICLE]
        return evcc_plan(self.evcc_state, key, ahead, week, now, reason, lasts, last_written=self._written.get(key),
                         write_enabled=v.mode == "evcc")

    async def _write_evcc(self, v: Vehicle, now: datetime) -> None:
        """Write the plan for the next needed departure into evcc (only when switched on, only plans Plugwhen wrote itself)."""
        key = v.cfg.get(V_EVCC_VEHICLE)
        conn = self.evcc_connection()
        if not key or v.mode != "evcc" or conn is None or self.evcc_state is None:
            return
        plan = self.evcc_plan_for(v, now) or {}
        action, why = decide_write(plan.get("would_write"), plan.get("current"), self._written.get(key))
        if action is None:
            return
        from homeassistant.helpers.aiohttp_client import async_get_clientsession

        client = EvccClient(async_get_clientsession(self.hass), conn[0], conn[1])
        try:
            if action == "set":
                w = plan["would_write"]
                await client.set_plan(key, int(w["soc"]), dt_util.parse_datetime(w["time"]))
                self._written[key] = dict(w)
            else:
                await client.delete_plan(key)
                self._written.pop(key, None)
            v.evcc_write = {"at": now.isoformat(), "action": action, "reason": why, "error": None}
            self.evcc_state = await client.state()   # show what evcc has now
        except EvccError as err:
            v.evcc_write = {"at": now.isoformat(), "action": action, "reason": why, "error": str(err)[:120]}
            _LOGGER.warning("Plugwhen: plan of %s not written into evcc: %s", v.name, err)
        self._evcc_store.async_delay_save(self._evcc_data, 5)

    def evcc_plan_inputs(self, v: Vehicle, now: datetime) -> tuple[dict[str, Any] | None, list[dict[str, Any]], str, str | None]:
        """For the card "Plan for evcc": (first needed departure with its target, learned week, reason, lasts until).
        The target of a departure is the one Plugwhen plans for that weekday (reserve or learned kilometres)."""
        capacity = float(v.cfg.get(V_CAPACITY) or 60.0)

        def target(weekday: int, dep: datetime | None = None) -> float:
            cal = self._trip_at(v, dep) is not None
            return compute_need(self._plan_for(v, dep, weekday), v.reserve_km, None, capacity, v.consumption,
                                learn_km=v.learn_km or cal, min_soc=self._min_soc(v)).target_soc

        week = []
        for wd in range(7):
            p = v.model.plan(wd)
            hour = p.departure_early if p.departure_early is not None else p.departure_hour
            if hour is None or p.samples < MIN_SAMPLES or (p.drive_share or 0.0) < MIN_DRIVE_SHARE:
                continue
            week.append({"weekday": wd, "hour": hour, "target_soc": target(wd)})
        h = v.horizon or {}
        if v.soc is None:
            return None, week, "unknown_soc", None
        if h.get("status") != "ok":
            return None, week, "no_departure", None
        fn = h.get("first_need")
        if not fn:
            return None, week, "covered", h.get("lasts_until")
        dep = dt_util.parse_datetime(str(fn.get("departure") or ""))
        if dep is None:
            return None, week, "no_departure", None
        return {"departure": dep, "target_soc": target(dt_util.as_local(dep).weekday(), dep)}, week, "planned", None

    async def _refresh_evcc(self, now: datetime) -> None:
        """Read evcc's state once per run, only if a vehicle names its evcc car. A failure leaves the cars as without evcc."""
        conn = self.evcc_connection()
        if conn is None or not any(v.cfg.get(V_EVCC_VEHICLE) for v in self.vehicles.values()):
            self.evcc_state, self.evcc_info = None, ({"source": conn[2], "used": False} if conn else {})
            return
        from homeassistant.helpers.aiohttp_client import async_get_clientsession

        try:
            self.evcc_state = await EvccClient(async_get_clientsession(self.hass), conn[0], conn[1]).state()
            self.evcc_info = {"source": conn[2], "used": True, "ok": True, "at": now.isoformat()}
        except EvccError as err:
            self.evcc_state = None
            self.evcc_info = {"source": conn[2], "used": True, "ok": False, "error": str(err)[:120]}
            _LOGGER.debug("Plugwhen: evcc not readable: %s", err)

    # ---------- reading ----------

    def _state(self, eid: str | None):
        return self.hass.states.get(eid) if eid else None

    def _float(self, eid: str | None) -> float | None:
        st = self._state(eid)
        if st is None or st.state in _BAD:
            return None
        try:
            return float(st.state)
        except ValueError:
            return None

    def _age_s(self, eid: str | None, now: datetime) -> float | None:
        """Seconds since the entity's state was last written (also when the value did not change)."""
        st = self._state(eid)
        if st is None:
            return None
        stamp = max(st.last_updated, getattr(st, "last_reported", st.last_updated))
        return max(0.0, (now - stamp).total_seconds())

    def _is_on(self, eid: str | None) -> bool | None:
        st = self._state(eid)
        if st is None or st.state in _BAD:
            return None
        return st.state == "on"

    def _unit(self, eid: str | None) -> str | None:
        st = self._state(eid)
        return st.attributes.get("unit_of_measurement") if st else None

    # ---------- learning from the long-term statistics ----------

    async def _load_history(self, v: Vehicle, now: datetime) -> None:
        v.history_at = now  # also after a failure: try again in an hour
        odo_id, soc_id, wbs = v.cfg.get(V_ODOMETER), v.cfg.get(V_SOC), self.wallboxes(v)
        temp_id = self._outdoor_entity()
        ids = {e for e in (odo_id, soc_id, temp_id, *wbs) if e}
        try:
            from homeassistant.components.recorder import get_instance
            from homeassistant.components.recorder.statistics import statistics_during_period

            stats = await get_instance(self.hass).async_add_executor_job(
                statistics_during_period, self.hass, now - timedelta(days=HISTORY_DAYS), now, ids, "hour", None,
                {"state", "mean", "max", "change"},
            )
        except Exception as err:  # noqa: BLE001 - the planner must not break because the history is missing
            v.history_error = str(err)
            _LOGGER.warning("Plugwhen: history of %s could not be read: %s", v.name, err)
            return

        def series(eid: str | None, first: str, second: str, convert) -> list[tuple[datetime, float | None]]:
            if not eid:
                return []
            unit = self._unit(eid)
            out = []
            for row in stats.get(eid, []):
                val = row.get(first)
                if val is None:
                    val = row.get(second)
                out.append((dt_util.as_local(dt_util.utc_from_timestamp(row["start"])), convert(val, unit)))
            return out

        soc_series = series(soc_id, "mean", "state", lambda x, _u: x)
        hourly_wb = self._car_energy(v, stats, soc_series)
        if hourly_wb is not None:
            v.habit = charging_habit(hourly_wb, now)
        odometer = series(odo_id, "state", "max", to_km)
        if not odometer:
            v.history_error = "no statistics for the odometer (the sensor needs a state class)"
            return
        records = records_from_hourly(
            odometer,
            soc_series,
            cumulative(hourly_wb) if hourly_wb else None,
            float(v.cfg.get(V_CAPACITY) or 0) or None,
            temp_c=series(temp_id, "mean", "state", _to_celsius) or None,
        )
        v.records = records
        v.efficiency = efficiency_from_records(records)
        skip = await self._calendar_days(v, now)   # special trips from the calendar are exceptions, not the usual week
        model = MobilityModel()
        for r in records:
            if r.day not in skip:
                model.add_day(r)
        v.trip_days_skipped = sum(1 for r in records if r.day in skip)
        v.model, v.history_days, v.history_error = model, len(records), None
        try:
            v.fleet_model = self._car_model(v)
        except Exception:  # noqa: BLE001 - only for the fleet values
            v.fleet_model = None
        _LOGGER.debug("Plugwhen: %s learned from %s days", v.name, len(records))

    # ---------- departure, need, plan, warning ----------

    def _learned_departure(self, v: Vehicle, now: datetime) -> datetime | None:
        for d in range(LOOKAHEAD_DAYS + 1):
            day = (now + timedelta(days=d)).date()
            p = v.model.plan(day.weekday())
            target = p.departure_early if p.departure_early is not None else p.departure_hour   # the early departure: ready in time
            if target is None or p.samples < MIN_SAMPLES or (p.drive_share or 0.0) < MIN_DRIVE_SHARE:
                continue
            hour = int(target)
            dep = datetime.combine(day, time(hour, int(round((target - hour) * 60)) % 60), tzinfo=now.tzinfo)
            if dep > now:
                return dep
        return None

    def _departure(self, v: Vehicle, now: datetime) -> tuple[datetime | None, str | None]:
        """The departure an entity names wins over the learned one."""
        eid = v.cfg.get(V_DEPARTURE)
        if eid:
            st = self._state(eid)
            dep = departure_from_state(st.state, now) if st is not None else None
            trip = self._next_trip(v, now)
            tdep = dt_util.parse_datetime(trip["departure"]) if trip else None
            if dep is not None and (tdep is None or dep <= tdep):
                return dep, "entity"
            if tdep is not None:
                return tdep, "calendar"
        dep = self._learned_departure(v, now)
        trip = self._next_trip(v, now)
        if trip is not None:   # a trip in the calendar before the learned departure comes first
            tdep = dt_util.parse_datetime(trip["departure"])
            if tdep is not None and (dep is None or tdep <= dep + timedelta(minutes=1) or tdep.date() == dep.date()):
                return tdep, "calendar"
        return dep, ("learned" if dep is not None else None)

    # ---------- potential calculator ----------

    def _waechter_values(self) -> dict[str, Any]:
        """Settings and measured peaks of the chosen quarter-hour peak guard, read from its entities (nothing is imported)."""
        wid = self.entry.options.get(O_WAECHTER)
        entry = self.hass.config_entries.async_get_entry(wid) if wid else None
        if entry is None:
            return {}
        from homeassistant.helpers import entity_registry as er

        ents = {str(e.unique_id): e.entity_id for e in er.async_entries_for_config_entry(er.async_get(self.hass), wid)}
        num = lambda key: self._float(ents.get(f"{wid}_{key}"))  # noqa: E731
        out: dict[str, Any] = {"grid_energy": {**entry.data, **entry.options}.get("grid_energy") or None}
        for key in ("limit", "margin", "price_low", "price_high", "price_threshold"):
            out[key] = num(key)
        mp = self._state(ents.get(f"{wid}_month_peak"))
        measured = {}
        for m in (mp.attributes.get("months") if mp else None) or []:
            try:
                if abs(float(m["peak_kw"]) - float(m["peak_without_kw"])) < 0.01:   # only months the guard did not change
                    measured[str(m["month"])] = float(m["peak_without_kw"])
            except (KeyError, TypeError, ValueError):
                continue
        out["measured"] = measured
        return out

    async def _potential_and_tell(self, v: Vehicle) -> None:
        await self.async_potential(v)
        async_dispatcher_send(self.hass, self.signal)

    async def async_potential(self, v: Vehicle, days: int = POTENTIAL_DAYS) -> dict[str, Any]:
        """Replay the last `days` with other ways of charging (see potential.py). Read-only; the result goes to the sensor."""
        now = dt_util.now()
        v.potential_at = now
        w = self._waechter_values()
        grid_id = self.entry.options.get(O_GRID_ENERGY) or w.get("grid_energy")
        wbs, odo_id, soc_id = self.wallboxes(v), v.cfg.get(V_ODOMETER), v.cfg.get(V_SOC)
        wb_id = wbs[0] if wbs else None
        missing = [k for k, e in (("grid_energy", grid_id), ("wallbox_energy", wb_id), ("odometer", odo_id)) if not e]
        if missing:
            v.potential = {"status": "no_data", "missing": missing, "computed_at": now.isoformat()}
            return v.potential
        try:
            from homeassistant.components.recorder import get_instance
            from homeassistant.components.recorder.statistics import statistics_during_period

            stats = await get_instance(self.hass).async_add_executor_job(
                statistics_during_period, self.hass, now - timedelta(days=days), now, {grid_id, odo_id, *wbs, *([soc_id] if soc_id else [])},
                "hour", None, {"change", "state", "mean"},
            )
        except Exception as err:  # noqa: BLE001 - a calculation that cannot run must not disturb the planner
            v.potential = {"status": "no_data", "error": str(err), "computed_at": now.isoformat()}
            return v.potential

        def hourly(eid: str, field: str, convert) -> dict[datetime, float]:
            unit = self._unit(eid)
            out = {}
            for row in stats.get(eid, []):
                val = convert(row.get(field), unit)
                if val is not None:
                    out[dt_util.as_local(dt_util.utc_from_timestamp(row["start"]))] = val
            return out

        grid = clean_grid(hourly(grid_id, "change", to_kwh))
        soc_rows = [(dt_util.as_local(dt_util.utc_from_timestamp(r["start"])), r.get("mean") if r.get("mean") is not None else r.get("state"))
                    for r in stats.get(soc_id, [])] if soc_id else []
        car = {t: max(0.0, x) for t, x in (self._car_energy(v, stats, soc_rows) or {}).items()}
        odo = hourly(odo_id, "state", to_km)
        ks = sorted(odo)
        trips = [b for a, b in zip(ks, ks[1:]) if 0.5 < odo[b] - odo[a] < 400]
        low = self.entry.options.get(O_PRICE_LOW) or w.get("price_low")
        prices = None
        if low:
            high = self.entry.options.get(O_PRICE_HIGH) or w.get("price_high") or low
            threshold = self.entry.options.get(O_PRICE_THRESHOLD)
            if threshold is None:
                threshold = w.get("price_threshold") or 0.0
            prices = Prices(float(low), float(high), float(threshold))
        guard_kw = (w["limit"] - (w.get("margin") or 0.0)) if w.get("limit") else None
        full = float(v.cfg.get(V_CHARGE_MAX, DEFAULT_CHARGE_MAX))
        result = calculate_potential(
            grid, car, trips, full_kw=full, min_kw=float(v.cfg.get(V_CHARGE_MIN, DEFAULT_CHARGE_MIN)),
            fixed_kw=min(full, POTENTIAL_FIXED_KW), guard_kw=guard_kw, quarter_add_kw=self.quarter_add_fn(),
            prices=prices, measured_peaks=w.get("measured") or None, plugged=v.plug_log.intervals() or None,
        )
        result.update({
            "computed_at": now.isoformat(), "history_days": days,
            "sources": {"grid_energy": grid_id, "wallbox_energy": wbs if len(wbs) > 1 else wb_id, "odometer": odo_id,
                        "prices": "settings" if self.entry.options.get(O_PRICE_LOW) else ("guard" if w.get("price_low") else None),
                        "guard_kw": guard_kw, "quarter_add": self._add_model.summary(), "quarter_add_default_kw": POTENTIAL_QUARTER_ADD_KW},
        })
        v.potential = result
        return result

    def _load_entity(self) -> str | None:
        """The load forecast sensor: an entity named in the settings, else the one of the chosen quarter-hour peak guard."""
        explicit = self.entry.options.get(O_LOAD)
        if explicit:
            return explicit
        entry_id = self.entry.options.get(O_WAECHTER)
        if not entry_id:
            return None
        from homeassistant.helpers import entity_registry as er

        return pick(((e.entity_id, e.domain, e.unique_id) for e in er.async_entries_for_config_entry(er.async_get(self.hass), entry_id)),
                    "sensor", "_forecast_peak")

    def _load_inputs(self, now: datetime) -> tuple[list[dict[str, Any]] | None, float | None]:
        st = self._state(self._load_entity())
        if st is None or st.state in _BAD:
            return None, None
        # the house alone if the guard offers it (from 0.14.1): its own `hours` contain the expected charging of the car, and the
        # car Plugwhen plans must not count as load against itself (otherwise there is "no room" every night)
        quarters = load_from_hours(st.attributes.get("hours_house") or st.attributes.get("hours"), now.tzinfo)
        try:
            target = float(st.attributes.get("target_kw")) if st.attributes.get("target_kw") is not None else None
        except (TypeError, ValueError):
            target = None
        return (quarters or None), target

    async def _solar_kw(self) -> dict[datetime, float] | None:
        """PV forecast per quarter hour from whatever solar forecast the Energy dashboard uses (Forecast.Solar, Solcast,
        Open-Meteo ...). None without one: the plan then simply spreads (households without solar)."""
        try:
            from homeassistant.components.energy.data import async_get_manager
            from homeassistant.components.energy.websocket_api import async_get_energy_platforms

            manager = await async_get_manager(self.hass)
            entries: list[str] = []
            for source in (manager.data or {}).get("energy_sources", []):
                if source.get("type") == "solar":
                    entries += source.get("config_entry_solar_forecast") or []
            if not entries:
                return None
            platforms = await async_get_energy_platforms(self.hass)
            hourly: dict[datetime, float] = {}
            for entry_id in entries:
                ce = self.hass.config_entries.async_get_entry(entry_id)
                if ce is None or ce.domain not in platforms:
                    continue
                forecast = await platforms[ce.domain](self.hass, entry_id)
                for iso, wh in ((forecast or {}).get("wh_hours") or {}).items():
                    t = dt_util.parse_datetime(iso)
                    if t is not None:
                        t = dt_util.as_local(t)
                        hourly[t] = hourly.get(t, 0.0) + float(wh) / 1000.0
            return {t.replace(minute=m): kw for t, kw in hourly.items() for m in (0, 15, 30, 45)} or None
        except Exception as err:  # noqa: BLE001 - the sun is optional
            _LOGGER.debug("Plugwhen: no solar forecast: %s", err)
            return None

    def _availability(self, now: datetime) -> tuple[dict[datetime, float] | None, str | None]:
        """Available power: the availability entity (if chosen) and the solar forecast (if on), the larger per quarter hour."""
        from_entity = None
        st = self._state(self.entry.options.get(O_AVAIL))
        if st is not None and st.state not in _BAD:
            from_entity = availability_from_attributes(dict(st.attributes), now)
        from_sun = None
        if self.entry.options.get(O_SOLAR, True):
            from_sun = surplus_from_solar(self._solar_scaled(), self.solar_deduct_kw(), now)
        source = "+".join(n for n, s in (("entity", from_entity), ("solar", from_sun)) if s) or None
        return merge_available(from_entity, from_sun), source

    # ---------- learned house-specific numbers ----------

    def quarter_add_fn(self):
        """How far a quarter hour lies above its hour's mean, as a function of the house load: learned for the house alone (hours without
        wallbox charging) by load level; the default applies for a level that has too few hours."""
        model = self._add_model

        def add(house_kw: float) -> float:
            v = model.value(house_kw)
            return POTENTIAL_QUARTER_ADD_KW if v is None else v

        return add

    def solar_deduct_kw(self) -> float:
        """What the house takes off the solar forecast first: the setting if given, else the learned night-time base load, else the default."""
        explicit = self.entry.options.get(O_SOLAR_DEDUCT)
        if explicit not in (None, ""):
            return float(explicit)
        return float(self._calib.get("base_load_kw") or DEFAULT_SOLAR_DEDUCT)

    def solar_deduct_source(self) -> str:
        if self.entry.options.get(O_SOLAR_DEDUCT) not in (None, ""):
            return "setting"
        return "learned" if self._calib.get("base_load_kw") else "default"

    def solar_factor(self) -> float | None:
        return self._solar_acc.factor()

    def _solar_scaled(self) -> dict[datetime, float] | None:
        f = self._solar_acc.factor()
        if not self._solar or f is None or abs(f - 1.0) < 0.005:
            return self._solar
        return {t: kw * f for t, kw in self._solar.items()}

    def _note_solar_prediction(self, now: datetime) -> None:
        """Remember what the forecast says for the coming days (the last value before midnight counts)."""
        if not self._solar:
            return
        per_day: dict = {}
        for t, kw in self._solar.items():
            if t.date() > now.date():
                per_day[t.date()] = per_day.get(t.date(), 0.0) + kw / 4.0     # four quarter hours of one hourly kW
        for d, kwh in per_day.items():
            self._solar_acc.predict(d, kwh)
        if per_day:
            self._save_calib()

    async def _check_solar(self, now: datetime) -> None:
        """Pair the remembered forecasts of past days with what the solar plant really produced (Energy dashboard, daily statistics).
        Its own step, every 15 minutes: before, it ran once a day inside the calibration and was skipped whenever an earlier part failed
        (e.g. the recorder not ready right after a restart), so the solar check stayed at 0 days."""
        info = self.solar_check = {"at": now.isoformat(), "pending": len(self._solar_acc.pending), "days": len(self._solar_acc.days),
                                   "sources": [], "error": None}
        try:
            solar_ids = await self._solar_production_ids()
            info["sources"] = solar_ids
            if not solar_ids or not any(k < now.date().isoformat() for k in self._solar_acc.pending):
                return
            from homeassistant.components.recorder import get_instance
            from homeassistant.components.recorder.statistics import statistics_during_period

            stats = await get_instance(self.hass).async_add_executor_job(
                statistics_during_period, self.hass, now - timedelta(days=SOLAR_CHECK_DAYS), now, set(solar_ids), "day", {"energy": "kWh"}, {"change"})
            per_day: dict = {}
            for sid in solar_ids:
                for r in stats.get(sid, []):
                    if r.get("change") is not None:
                        d = dt_util.as_local(dt_util.utc_from_timestamp(r["start"])).date()
                        per_day[d] = per_day.get(d, 0.0) + float(r["change"])
            added = sum(1 for d, kwh in per_day.items() if d < now.date() and self._solar_acc.measured(d, kwh))
            for k in [k for k in self._solar_acc.pending if k < (now.date() - timedelta(days=SOLAR_CHECK_DAYS)).isoformat()]:
                del self._solar_acc.pending[k]   # too old to be measured any more
            if added:
                self._save_calib()
            info.update(pending=len(self._solar_acc.pending), days=len(self._solar_acc.days), added=added)
        except Exception as err:  # noqa: BLE001 - optional; tried again in 15 minutes
            info["error"] = str(err)[:120]
            _LOGGER.debug("Plugwhen: solar check skipped: %s", err)

    def _save_calib(self) -> None:
        self._calib_store.async_delay_save(lambda: {"calib": self._calib, "solar": self._solar_acc.to_dict(), "add": self._add_model.to_dict()}, 30)

    # ---------- outdoor temperature (optional: consumption per km by temperature) ----------

    def _outdoor_entity(self) -> str | None:
        return self.entry.options.get(O_OUTDOOR_TEMP) or self._waechter_cfg().get("outdoor_temp_entity") or None

    def _weather_entity(self) -> str | None:
        return self.entry.options.get(O_WEATHER) or self._waechter_cfg().get("weather_entity") or None

    async def _refresh_weather(self) -> None:
        """Hourly temperature forecast of the weather entity (none: the outdoor sensor's value is used near the departure)."""
        eid = self._weather_entity()
        if not eid:
            self._wx = {}
            return
        try:
            resp = await self.hass.services.async_call(
                "weather", "get_forecasts", {"entity_id": eid, "type": "hourly"}, blocking=True, return_response=True)
            unit = (self._state(eid).attributes.get("temperature_unit") if self._state(eid) else None)
            out: dict[datetime, float] = {}
            for row in ((resp or {}).get(eid) or {}).get("forecast") or []:
                t = dt_util.parse_datetime(str(row.get("datetime") or ""))
                c = _to_celsius(row.get("temperature"), unit)
                if t is not None and c is not None:
                    out[dt_util.as_local(t).replace(minute=0, second=0, microsecond=0)] = c
            self._wx = out
        except Exception as err:  # noqa: BLE001 - the temperature is optional
            _LOGGER.debug("Plugwhen: no weather forecast from %s: %s", eid, err)
            self._wx = {}

    def _temp_at(self, when: datetime, now: datetime) -> float | None:
        """Outdoor temperature at `when`: the forecast hour, else the sensor's current value if `when` is within a day."""
        hour = when.replace(minute=0, second=0, microsecond=0)
        if hour in self._wx:
            return self._wx[hour]
        eid = self._outdoor_entity()
        if eid and when - now <= timedelta(hours=24):
            return _to_celsius(self._float(eid), self._unit(eid))
        return None

    def _waechter_cfg(self) -> dict[str, Any]:
        wid = self.entry.options.get(O_WAECHTER)
        entry = self.hass.config_entries.async_get_entry(wid) if wid else None
        return {**entry.data, **entry.options} if entry else {}

    async def _solar_production_ids(self) -> list[str]:
        try:
            from homeassistant.components.energy.data import async_get_manager

            manager = await async_get_manager(self.hass)
            out = []
            for source in (manager.data or {}).get("energy_sources", []):
                if source.get("type") == "solar" and source.get("stat_energy_from"):
                    out.append(source["stat_energy_from"])
            return out
        except Exception:  # noqa: BLE001 - optional
            return []

    async def _calibrate(self, now: datetime) -> None:
        """Learn the house-specific numbers from the recorder, once a day in the background. Every number keeps its default
        until there is enough data; nothing here can break the plan."""
        try:
            from homeassistant.components.recorder import get_instance
            from homeassistant.components.recorder.statistics import statistics_during_period
        except Exception:  # noqa: BLE001
            return
        wcfg = self._waechter_cfg()
        grid_power = wcfg.get("grid_power")
        grid_energy = self.entry.options.get(O_GRID_ENERGY) or wcfg.get("grid_energy")
        changed = False
        rec = get_instance(self.hass)
        try:
            if grid_power:
                stats = await rec.async_add_executor_job(
                    statistics_during_period, self.hass, now - timedelta(days=10), now, {grid_power}, "5minute", None, {"mean"})
                unit = (self._unit(grid_power) or "W").strip().lower()
                scale = 0.001 if unit == "w" else 1.0
                series = [(dt_util.as_local(dt_util.utc_from_timestamp(r["start"])), (float(r["mean"]) * scale) if r.get("mean") is not None else None)
                          for r in stats.get(grid_power, [])]
                wb_ids = {w for x in self.vehicles.values() for w in self.wallboxes(x)}
                wb_hourly = None
                if wb_ids:   # hours without wallbox energy are the house alone
                    wstats = await rec.async_add_executor_job(
                        statistics_during_period, self.hass, now - timedelta(days=10), now, wb_ids, "hour", None, {"change"})
                    wb_hourly = {}
                    for wid in wb_ids:
                        wunit = self._unit(wid)
                        for r in wstats.get(wid, []):
                            if r.get("change") is not None:
                                k = dt_util.as_local(dt_util.utc_from_timestamp(r["start"]))
                                wb_hourly[k] = wb_hourly.get(k, 0.0) + (to_kwh(float(r["change"]), wunit) or 0.0)
                samples = quarter_add_samples(series, wb_hourly)
                if samples:
                    self._add_model.merge(samples, house_only=wb_hourly is not None)
                    changed = True
            if grid_energy:
                stats = await rec.async_add_executor_job(
                    statistics_during_period, self.hass, now - timedelta(days=14), now, {grid_energy}, "hour", None, {"change"})
                unit = self._unit(grid_energy)
                hourly = {dt_util.as_local(dt_util.utc_from_timestamp(r["start"])): to_kwh(float(r["change"]), unit)
                          for r in stats.get(grid_energy, []) if r.get("change") is not None}
                b = base_load_from_hourly(hourly)
                if b is not None:
                    self._calib["base_load_kw"], changed = b, True
        except Exception as err:  # noqa: BLE001 - the recorder may be busy or a sensor without statistics
            _LOGGER.debug("Plugwhen: calibration skipped: %s", err)
        if changed:
            self._calib["at"] = now.isoformat()
            self._save_calib()
            for v in self.vehicles.values():
                v.potential_at = None            # the potential uses the learned quarter add: compute again soon

    # ---------- plug-in times ----------

    async def _seed_plugs(self, v: Vehicle) -> None:
        eid = v.cfg.get(V_PLUGGED)
        now = dt_util.now()
        try:
            from homeassistant.components.recorder import get_instance, history

            states = await get_instance(self.hass).async_add_executor_job(
                lambda: history.get_significant_states(self.hass, now - timedelta(days=30), now, [eid],
                                                       significant_changes_only=False, no_attributes=True))
            seq = [(dt_util.as_local(s.last_changed), None if s.state in _BAD else s.state == "on") for s in states.get(eid, [])]
            if v.plug_log.seed(seq):
                self._save_plugs()
                _LOGGER.debug("Plugwhen: %s plug-in times of %s taken from the recorder", len(v.plug_log.items), v.name)
        except Exception as err:  # noqa: BLE001 - without the history the log simply starts now
            _LOGGER.debug("Plugwhen: plug history of %s not readable: %s", v.name, err)
        finally:
            v.plug_seeding = False
        self._compute(v, dt_util.now())   # catch up with the current state

    def _track_plug(self, v: Vehicle, now: datetime) -> None:
        st = self._state(v.cfg.get(V_PLUGGED))
        if v.plug_seeding or v.plugged is None or v.plugged == v.plug_log.open:
            return
        if st is not None:
            when = dt_util.as_local(st.last_changed) if st.last_changed <= now else now
        elif v.evcc_live is not None:   # from evcc: known to the minute of the run
            when = now
        else:
            return
        if v.plug_log.change(v.plugged, when):
            v.plug_log.trim(now)
            self._save_plugs()

    def _save_plugs(self) -> None:
        self._plug_store.async_delay_save(lambda: {"vehicles": {v.sub_id: v.plug_log.items for v in self.vehicles.values()}}, 10)

    def _compute(self, v: Vehicle | None, now: datetime) -> None:
        """Compute the plans of all cars (one car's change can move the others: the same house, the same peak, maybe the same
        wallbox). One after the other: plugged in first, then by departure; a later car sees what the earlier ones planned."""
        order = plan_order([{"id": x.sub_id, "plugged": x.plugged, "departure": x.departure, "name": x.name} for x in self.vehicles.values()])
        done: list[tuple[set[str], dict]] = []
        for sid in order:
            x = self.vehicles[sid]
            mine = set(self.wallboxes(x))
            others, blocked = taken_by_others(done, mine)
            self._compute_plan(x, now, others or None, blocked or None)
            self._shadow_step(x, now)
            cp = x.charge_plan or {}
            if cp.get("status") in ("planned", "infeasible") and cp.get("quarters"):
                done.append((mine, cp["quarters"]))

    def insight(self, v: Vehicle) -> dict[str, Any]:
        """Does the learning bring anything for this car (walks through the history; cached until the reserve or the history changes)."""
        key = (v.reserve_km, len(v.records), v.history_at)
        if v.insight_cache is None or v.insight_cache[0] != key:
            v.insight_cache = (key, learning_check(v.records, v.reserve_km))
        return v.insight_cache[1]

    def _shadow_step(self, v: Vehicle, now: datetime) -> None:
        """Learn mode: the decision Plugwhen would take now, written down and compared with the real wallbox. Nothing is switched."""
        if v.mode not in LEARNING_MODES:
            v.decision = None
            return
        v.decision = decide(v.charge_plan, now, v.plugged, v.soc is not None)
        charging = (self._is_on(v.cfg.get(V_CHARGING)) if v.cfg.get(V_CHARGING)
                    else (v.evcc_live["charging"] if v.evcc_live else None))
        energy = None
        wb = self.wallbox_now(v)
        if wb:
            energy = to_kwh(self._float(wb), self._unit(wb))
        if v.shadow.update(now, v.decision, charging, energy):
            self._shadow_store.async_delay_save(
                lambda: {"vehicles": {x.sub_id: x.shadow.to_dict() for x in self.vehicles.values()}}, 30)

    def _compute_plan(self, v: Vehicle, now: datetime, others: dict[datetime, float] | None = None,
                      blocked: set[datetime] | None = None) -> None:
        v.others_kw = others
        v.evcc_live = live_vehicle(self.evcc_state, v.cfg[V_EVCC_VEHICLE]) if v.cfg.get(V_EVCC_VEHICLE) else None
        # a sensor wins; evcc only fills in what no sensor says (and only while evcc has the car at a loadpoint)
        v.plugged = self._is_on(v.cfg.get(V_PLUGGED)) if v.cfg.get(V_PLUGGED) else (v.evcc_live["plugged"] if v.evcc_live else None)
        self._track_plug(v, now)
        v.charging = (self._is_on(v.cfg.get(V_CHARGING)) is True) if v.cfg.get(V_CHARGING) else bool(v.evcc_live and v.evcc_live["charging"])
        seen = {w: to_kwh(self._float(w), self._unit(w)) for w in self.wallboxes(v)}
        if seen:   # which wallbox the car is at: the one whose counter rises while it charges (or is plugged in)
            v.wallbox_active = active_wallbox(v.wallbox_seen, seen, v.charging or v.plugged is True, v.wallbox_active)
            v.wallbox_seen = seen
        v.soc = self._float(v.cfg.get(V_SOC))
        v.soc_age_s = self._age_s(v.cfg.get(V_SOC), now) if v.soc is not None else None
        v.soc_stale = soc_is_stale(v.soc_age_s, float(v.cfg.get(V_SOC_MAX_AGE, DEFAULT_SOC_MAX_AGE_H)), v.charging)
        if v.soc_stale:  # too old to be believed: like an unknown state of charge (no plan, no warning)
            v.soc = None
        v.departure, v.departure_source = self._departure(v, now)
        weekday = (v.departure or (now + timedelta(days=1))).weekday()  # without a departure: tomorrow
        v.plan = self._plan_for(v, v.departure, weekday)
        v.departure_temp_c = self._temp_at(v.departure or now + timedelta(hours=12), now)
        v.consumption, v.consumption_source = v.model.consumption_at(
            v.departure_temp_c, float(v.cfg.get(V_CONSUMPTION, DEFAULT_CONSUMPTION_100)) / 100.0)
        v.fleet_cars = None
        if v.consumption_source in ("config", "rule_config") and self.share_usage:   # no own values yet: the fleet's, if any
            models = self._fleet.get("modelle")
            entry, src = flotte.entry_for(models, flotte.group_of(models, v.fleet_model, self._fleet.get("gruppe")))
            c = flotte.consumption(entry, v.departure_temp_c) if entry else None
            if c is not None:
                v.consumption, v.consumption_source = c, src
                v.fleet_cars = entry.get("autos") if src == "fleet_model" else (self._fleet.get("modelle") or {}).get("autos")
        v.need = compute_need(
            v.plan, v.reserve_km, v.soc, float(v.cfg.get(V_CAPACITY) or 60.0), v.consumption,
            learn_km=v.learn_km or v.departure_source == "calendar", efficiency=self.efficiency_of(v), min_soc=self._min_soc(v))

        max_kw = float(v.cfg.get(V_CHARGE_MAX, DEFAULT_CHARGE_MAX))
        if v.soc is None:  # without the state of charge nothing can be said: no plan, no warning (the sensors say so)
            v.charge_plan = {"status": "unknown_soc", "windows": [], "needed_kwh": None, "planned_kwh": None}
            v.notice = None
            v.horizon = None
            v.load_used = v.availability_used = False
            return
        load, target_kw = self._load_inputs(now)
        avail, v.availability_source = self._availability(now)
        v.load_used, v.availability_used = load is not None, avail is not None
        v.charge_plan = make_plan(
            now, v.departure or now, v.need.charge_kwh, max_kw, float(v.cfg.get(V_CHARGE_MIN, DEFAULT_CHARGE_MIN)),
            load=load, target_kw=target_kw if load is not None else None, available_kw=avail,
            # a wallbox shared with another car: charge compactly (at least three quarters of the wallbox power), so that the other
            # car still fits into the night
            pref_kw=(max(SHARED_COMPACT * max_kw, float(v.cfg.get(V_CHARGE_PREF, DEFAULT_CHARGE_PREF)))
                     if set(self.wallboxes(v)) & self.shared_wallboxes() else float(v.cfg.get(V_CHARGE_PREF, DEFAULT_CHARGE_PREF))),
            others_kw=others, blocked=blocked,
        )
        v.horizon = self._horizon(v, now, avail, max_kw)
        hours = (v.departure - now).total_seconds() / 3600.0 if v.departure else None
        planned = v.charge_plan["planned_kwh"] if v.charge_plan["status"] == "planned" else None
        v.notice = check_ready(
            v.need, v.soc, plugged=v.plugged, charging=v.charging, hours_to_departure=hours, charge_kw_max=max_kw,
            planned_kwh=planned,
        )

    # ---------- the look-ahead ----------

    def _trips(self, v: Vehicle, now: datetime, capacity: float) -> list[Trip]:
        """The coming departures (learned, the early hour; an entity departure wins for its day) with the expected and the planned range."""
        def trip_for(departure: datetime, weekday: int) -> Trip:
            p = v.model.plan(weekday)
            need = compute_need(p, v.reserve_km, None, capacity, v.consumption, learn_km=v.learn_km)
            return Trip(departure, float(p.km_typical or 0.0), need.km)

        out: list[Trip] = []
        for d in range(HORIZON_DAYS + 1):
            day = (now + timedelta(days=d)).date()
            p = v.model.plan(day.weekday())
            target = p.departure_early if p.departure_early is not None else p.departure_hour
            if target is None or p.samples < MIN_SAMPLES or (p.drive_share or 0.0) < MIN_DRIVE_SHARE:
                continue
            hour = int(target)
            dep = datetime.combine(day, time(hour, int(round((target - hour) * 60)) % 60), tzinfo=now.tzinfo)
            if dep > now:
                out.append(trip_for(dep, day.weekday()))
        if v.departure is not None and v.departure_source == "entity":
            out = [t for t in out if t.departure.date() != v.departure.date()]
            out.append(trip_for(v.departure, v.departure.weekday()))
        cal: list[Trip] = []
        for t in v.trips:
            d = dt_util.parse_datetime(t["departure"])
            if d is None or d <= now:
                continue
            cal.append(Trip(d, float(t["km"]), float(t["range_km"])) if t.get("km") else trip_for(d, d.weekday()))
        # a calendar trip replaces the learned departure only when it is the same trip (within two hours); calendar trips never replace each other
        return with_calendar(out, cal)[:HORIZON_TRIPS]

    def efficiency_of(self, v: Vehicle) -> float:
        """Share of the wallbox energy that reaches the battery: learned from the own history, else the start value at the power
        the car usually charges with (the preferred power, within min..max): about 89 % at 4 kW, 76 % at 1.4 kW, 93 % at 11 kW."""
        if v.efficiency:
            return v.efficiency
        lo = float(v.cfg.get(V_CHARGE_MIN, DEFAULT_CHARGE_MIN))
        hi = float(v.cfg.get(V_CHARGE_MAX, DEFAULT_CHARGE_MAX))
        return charge_efficiency(max(lo, min(hi, float(v.cfg.get(V_CHARGE_PREF, DEFAULT_CHARGE_PREF)))))

    def _horizon(self, v: Vehicle, now: datetime, avail: dict[datetime, float] | None, max_kw: float) -> dict[str, Any] | None:
        """Where the energy for the next departures comes from and whether charging with the sun in advance saves grid energy. Works without
        a solar plant (then nothing is pre-charged). It recommends only."""
        if v.soc is None:
            return None
        capacity = float(v.cfg.get(V_CAPACITY) or 60.0)
        try:
            return horizon_plan(
                now, v.soc / 100.0 * capacity, capacity, v.consumption, self._trips(v, now, capacity), avail, max_kw,
                efficiency=self.efficiency_of(v), pref_kw=float(v.cfg.get(V_CHARGE_PREF, DEFAULT_CHARGE_PREF)))
        except Exception as err:  # noqa: BLE001 - a look-ahead that fails must never disturb the plan
            _LOGGER.debug("Plugwhen: look-ahead of %s failed: %s", v.name, err)
            return None

    # ---------- the warning ----------

    async def _maybe_send(self, v: Vehicle, now: datetime) -> None:
        await self._send_ready(v, now)
        await self._send_ahead(v, now)
        await self._send_switch_ready(v, now)

    def switch_ready(self, v: Vehicle, now: datetime) -> dict[str, Any]:
        """Checklist: may Plugwhen switch the wallbox itself (mode 'direct', later)? Learned trips, days with a comparison in learn
        mode, agreement, and with a solar plant the checked solar forecast."""
        weekdays = []
        for wd in range(7):
            p = v.model.plan(wd)
            weekdays.append({"weekday": wd, "samples": p.samples, "used": (p.drive_share or 0.0) >= MIN_DRIVE_SHARE})
        summ = v.shadow.summary(now, days=30)
        solar_days = len(self._solar_acc.days) if (self.entry.options.get(O_SOLAR, True) and self._solar) else None
        return switch_readiness(weekdays, int(summ.get("days") or 0), summ.get("agree_pct"), solar_days, now)

    async def _send_switch_ready(self, v: Vehicle, now: datetime) -> None:
        """Once per car: tell that the learn mode is through (the notify services of the car; nothing without them)."""
        key = "switch_ready"
        services = [x.strip() for x in str(v.cfg.get(V_NOTIFY) or "").split(",") if "." in x]
        if not services or key in self._sent.get(v.sub_id, []) or not self.switch_ready(v, now)["ready"]:
            return
        de = (self.hass.config.language or "").lower().startswith("de")
        title = f"Plugwhen · {v.name}"
        msg = ("Der Lernmodus ist durch: Plugwhen hat oft genug gleich entschieden wie die Wirklichkeit. Ohne evcc kann jetzt die Betriebsart „Direkt“ gewählt werden."
               if de else "The learn mode is through: Plugwhen decided like reality often enough. Without evcc the mode “direct” can be chosen now.")
        await self._deliver(v, services, title, msg, key)

    async def _deliver(self, v: Vehicle, services: list[str], title: str, message: str, key: str) -> bool:
        sent = self._sent.setdefault(v.sub_id, [])
        delivered = 0
        for service in services:
            domain, name = service.split(".", 1)
            try:
                await self.hass.services.async_call(domain, name, {"title": title, "message": message}, blocking=False)
                delivered += 1
            except Exception as err:  # noqa: BLE001 - a wrong service name must not stop the planner or the other phones
                _LOGGER.warning("Plugwhen: the warning for %s could not be sent through %s: %s", v.name, service, err)
        if not delivered:
            return False
        remember_sent(sent, key, SENT_KEEP)
        self._store.async_delay_save(lambda: {"sent": self._sent}, 10)
        return True

    async def _send_ahead(self, v: Vehicle, now: datetime) -> None:
        """The heads-up of the evening before the day on which charging has to happen (or pays with the sun)."""
        services = [x.strip() for x in str(v.cfg.get(V_NOTIFY) or "").split(",") if "." in x]
        if not services or not v.notice_enabled or v.horizon is None:
            return
        a = check_ahead(v.horizon, now, float(v.cfg.get(V_NOTIFY_HOUR, DEFAULT_NOTIFY_HOUR)))
        if a is None:
            return
        key = ahead_key(a)
        if key in self._sent.setdefault(v.sub_id, []):
            return
        title, message = ahead_text(self.hass.config.language, a, v.name, float(v.cfg.get(V_CHARGE_PREF, DEFAULT_CHARGE_PREF)))
        if await self._deliver(v, services, title, message, key):
            _LOGGER.info("Plugwhen: heads-up '%s' for tomorrow sent for %s", a.kind, v.name)

    async def _send_ready(self, v: Vehicle, now: datetime) -> None:
        n = v.notice
        services = [x.strip() for x in str(v.cfg.get(V_NOTIFY) or "").split(",") if "." in x]
        if n is None or not v.notice_enabled or v.departure is None or not services:
            return
        hours = (v.departure - now).total_seconds() / 3600.0
        if not should_check(now.hour + now.minute / 60.0, float(v.cfg.get(V_NOTIFY_HOUR, DEFAULT_NOTIFY_HOUR)), hours):
            return
        key = dedupe_key(n, v.departure.date())
        sent = self._sent.setdefault(v.sub_id, [])
        if key in sent:
            return
        title, message = notice_text(self.hass.config.language, n, v.name, v.departure)
        if await self._deliver(v, services, title, message, key):
            _LOGGER.info("Plugwhen: warning '%s' sent for %s", n.kind, v.name)
