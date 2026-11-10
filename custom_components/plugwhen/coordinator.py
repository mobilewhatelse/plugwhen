"""Connects the learning, the need, the plan and the warning with Home Assistant."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later, async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    DEFAULT_CHARGE_MAX, DEFAULT_CHARGE_MIN, DEFAULT_MODE, DEFAULT_CONSUMPTION_100, DEFAULT_NOTIFY_HOUR, DEFAULT_RESERVE_KM, DEFAULT_SOC_MAX_AGE_H, DOMAIN,
    HISTORY_DAYS, HISTORY_INTERVAL, O_AVAIL, O_GRID_ENERGY, O_LOAD, O_PRICE_HIGH, O_PRICE_LOW, O_PRICE_THRESHOLD,
    O_EVCC_PASSWORD, O_EVCC_URL, O_EVCC_WRITE, O_ROUTE_WAZE, V_CALENDAR, V_EVCC_VEHICLE, V_STOCK, O_SOLAR, O_SOLAR_DEDUCT, DEFAULT_SOLAR_DEDUCT, SOLAR_REFRESH, O_WAECHTER, POTENTIAL_DAYS, POTENTIAL_FIXED_KW, POTENTIAL_INTERVAL, POTENTIAL_QUARTER_ADD_KW, SUBENTRY_VEHICLE, UPDATE_INTERVAL, V_CAPACITY, V_CHARGE_MAX,
    V_CHARGE_MIN, V_CHARGING, V_CONSUMPTION, V_DEPARTURE, V_NAME, V_NOTIFY, V_NOTIFY_HOUR, V_ODOMETER, V_PLUGGED,
    V_RESERVE, V_SOC, V_SOC_MAX_AGE, V_WALLBOX_ENERGY, V_CHARGE_PREF, DEFAULT_CHARGE_PREF, CALIBRATE_INTERVAL,
)
from dataclasses import replace

from .evcc import EvccClient, EvccError, connection as evcc_connection, live_vehicle
from .evcc_plan import decide_write, evcc_plan
from .trips import range_for_trip, trip_km, trips_from_events, waze_region
from .freshness import soc_is_stale
from .calibrate import QuarterAddModel, SolarAccuracy, base_load_from_hourly, efficiency_from_records, quarter_add_samples
from .habit import charging_habit
from .history import records_from_hourly, to_km, to_kwh
from .insight import learning_check
from .links import pick
from .inputs import availability_from_attributes, departure_from_state, load_from_hours, merge_available, surplus_from_solar
from .plugs import PlugLog
from .learning import MobilityModel, WeekdayPlan
from .horizon import Trip, horizon_plan
from .messages import ahead_text, notice_text
from .need import DEFAULT_EFFICIENCY, MIN_SAMPLES, Need, compute_need
from .notice import Notice, ahead_key, check_ahead, check_ready, dedupe_key, should_check
from .plan import make_plan
from .shadow import Decision, ShadowLog, decide
from .potential import Prices, calculate as calculate_potential, clean_grid

_LOGGER = logging.getLogger(__name__)
_BAD = (None, "", STATE_UNKNOWN, STATE_UNAVAILABLE)
LOOKAHEAD_DAYS = 7
HORIZON_DAYS = 14             # days looked at for the look-ahead (as far as possible: with normal behaviour, when is charging needed?)
HORIZON_TRIPS = 10            # departures in the look-ahead
TRIPS_REFRESH = timedelta(minutes=15)   # the calendar is read this often
MIN_DRIVE_SHARE = 0.5        # a weekday counts as a day of departure if the car is used on at least half of its days
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
    departure: datetime | None = None
    departure_source: str | None = None                    # "entity" or "learned"
    soc: float | None = None
    soc_age_s: float | None = None   # seconds since the state of charge was written
    soc_stale: bool = False          # too old: counts as unknown
    plugged: bool | None = None
    charging: bool = False
    history_days: int = 0
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


class Plugwhen:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.signal = f"{DOMAIN}_{entry.entry_id}_update"
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
        self._calib: dict[str, Any] = {"quarter_add_kw": None, "base_load_kw": None, "at": None}
        self._calib_at: datetime | None = None
        self._solar_acc = SolarAccuracy()
        self._add_model = QuarterAddModel()
        self._solar: dict[datetime, float] | None = None
        self._solar_at: datetime | None = None
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
        for v in self.vehicles.values():
            self._compute(v, now)
        async_dispatcher_send(self.hass, self.signal)
        for v in self.vehicles.values():
            await self._maybe_send(v, now)
            await self._write_evcc(v, now)

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
        if self._calib_at is None or now - self._calib_at >= CALIBRATE_INTERVAL:
            self._calib_at = now
            self.entry.async_create_background_task(self.hass, self._calibrate(now), f"{DOMAIN} calibrate")
        await self._refresh_evcc(now)
        for v in self.vehicles.values():
            if v.cfg.get(V_CALENDAR) and (v.trips_at is None or now - v.trips_at >= TRIPS_REFRESH):
                await self._refresh_trips(v, now)
        for v in self.vehicles.values():
            if v.history_at is None or now - v.history_at >= HISTORY_INTERVAL:
                await self._load_history(v, now)
            self._compute(v, now)
            if v.potential_at is None or now - v.potential_at >= POTENTIAL_INTERVAL:
                v.potential_at = now
                self.entry.async_create_background_task(self.hass, self._potential_and_tell(v), f"{DOMAIN} potential")
        async_dispatcher_send(self.hass, self.signal)
        for v in self.vehicles.values():
            await self._maybe_send(v, now)

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

    async def _route_km(self, location: str | None, now: datetime) -> float | None:
        """One-way kilometres from home to `location` (Waze travel time, only if switched on and installed); cached for a week."""
        if not location or not self.entry.options.get(O_ROUTE_WAZE):
            return None
        hit = self._routes.get(location)
        if hit and hit.get("at") and now - datetime.fromisoformat(hit["at"]) < timedelta(days=7):
            return hit.get("km")
        if not self.hass.services.has_service("waze_travel_time", "get_travel_times"):
            return None
        try:
            resp = await self.hass.services.async_call("waze_travel_time", "get_travel_times", {
                "origin": "zone.home", "destination": location, "region": waze_region(self.hass.config.country)},
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

    def _evcc_data(self) -> dict[str, Any]:
        return {"written": self._written, "routes": self._routes}

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

    def _min_soc(self, v: Vehicle) -> float:
        """Never plan below this: the stock for unplanned trips (setting), at least 20 %."""
        return max(20.0, float(v.cfg.get(V_STOCK) or 0.0))

    def evcc_plan_for(self, v: Vehicle, now: datetime) -> dict[str, Any] | None:
        if not v.cfg.get(V_EVCC_VEHICLE):
            return None
        ahead, week, reason, lasts = self.evcc_plan_inputs(v, now)
        key = v.cfg[V_EVCC_VEHICLE]
        return evcc_plan(self.evcc_state, key, ahead, week, now, reason, lasts, last_written=self._written.get(key),
                         write_enabled=bool(self.entry.options.get(O_EVCC_WRITE)))

    async def _write_evcc(self, v: Vehicle, now: datetime) -> None:
        """Write the plan for the next needed departure into evcc (only when switched on, only plans Plugwhen wrote itself)."""
        key = v.cfg.get(V_EVCC_VEHICLE)
        conn = self.evcc_connection()
        if not key or not self.entry.options.get(O_EVCC_WRITE) or conn is None or self.evcc_state is None:
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
        odo_id, soc_id, wb_id = v.cfg.get(V_ODOMETER), v.cfg.get(V_SOC), v.cfg.get(V_WALLBOX_ENERGY)
        ids = {e for e in (odo_id, soc_id, wb_id) if e}
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

        if wb_id:
            wb_unit = self._unit(wb_id)
            hourly_wb = {dt_util.as_local(dt_util.utc_from_timestamp(r["start"])): to_kwh(float(r["change"]), wb_unit)
                         for r in stats.get(wb_id, []) if r.get("change") is not None}
            v.habit = charging_habit(hourly_wb, now)
        odometer = series(odo_id, "state", "max", to_km)
        if not odometer:
            v.history_error = "no statistics for the odometer (the sensor needs a state class)"
            return
        records = records_from_hourly(
            odometer,
            series(soc_id, "mean", "state", lambda x, _u: x),
            series(wb_id, "state", "max", to_kwh) or None,
            float(v.cfg.get(V_CAPACITY) or 0) or None,
        )
        v.records = records
        v.efficiency = efficiency_from_records(records)
        model = MobilityModel()
        for r in records:
            model.add_day(r)
        v.model, v.history_days, v.history_error = model, len(records), None
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
        wb_id, odo_id = v.cfg.get(V_WALLBOX_ENERGY), v.cfg.get(V_ODOMETER)
        missing = [k for k, e in (("grid_energy", grid_id), ("wallbox_energy", wb_id), ("odometer", odo_id)) if not e]
        if missing:
            v.potential = {"status": "no_data", "missing": missing, "computed_at": now.isoformat()}
            return v.potential
        try:
            from homeassistant.components.recorder import get_instance
            from homeassistant.components.recorder.statistics import statistics_during_period

            stats = await get_instance(self.hass).async_add_executor_job(
                statistics_during_period, self.hass, now - timedelta(days=days), now, {grid_id, wb_id, odo_id}, "hour", None,
                {"change", "state"},
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
        car = {t: max(0.0, x) for t, x in hourly(wb_id, "change", to_kwh).items()}
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
            "sources": {"grid_energy": grid_id, "wallbox_energy": wb_id, "odometer": odo_id,
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
        quarters = load_from_hours(st.attributes.get("hours"), now.tzinfo)
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

    def _save_calib(self) -> None:
        self._calib_store.async_delay_save(lambda: {"calib": self._calib, "solar": self._solar_acc.to_dict(), "add": self._add_model.to_dict()}, 30)

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
                wb_ids = {x.cfg.get(V_WALLBOX_ENERGY) for x in self.vehicles.values()} - {None, ""}
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
            solar_ids = await self._solar_production_ids()
            if solar_ids and self._solar_acc.pending:
                stats = await rec.async_add_executor_job(
                    statistics_during_period, self.hass, now - timedelta(days=4), now, set(solar_ids), "day", {"energy": "kWh"}, {"change"})
                per_day: dict = {}
                for sid in solar_ids:
                    for r in stats.get(sid, []):
                        if r.get("change") is not None:
                            d = dt_util.as_local(dt_util.utc_from_timestamp(r["start"])).date()
                            per_day[d] = per_day.get(d, 0.0) + float(r["change"])
                for d, kwh in per_day.items():
                    if d < now.date() and self._solar_acc.measured(d, kwh):
                        changed = True
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

    def _compute(self, v: Vehicle, now: datetime) -> None:
        self._compute_plan(v, now)
        self._shadow_step(v, now)

    def insight(self, v: Vehicle) -> dict[str, Any]:
        """Does the learning bring anything for this car (walks through the history; cached until the reserve or the history changes)."""
        key = (v.reserve_km, len(v.records), v.history_at)
        if v.insight_cache is None or v.insight_cache[0] != key:
            v.insight_cache = (key, learning_check(v.records, v.reserve_km))
        return v.insight_cache[1]

    def _shadow_step(self, v: Vehicle, now: datetime) -> None:
        """Learn mode: the decision Plugwhen would take now, written down and compared with the real wallbox. Nothing is switched."""
        if v.mode != "learn":
            v.decision = None
            return
        v.decision = decide(v.charge_plan, now, v.plugged, v.soc is not None)
        charging = (self._is_on(v.cfg.get(V_CHARGING)) if v.cfg.get(V_CHARGING)
                    else (v.evcc_live["charging"] if v.evcc_live else None))
        energy = None
        wb = v.cfg.get(V_WALLBOX_ENERGY)
        if wb:
            energy = to_kwh(self._float(wb), self._unit(wb))
        if v.shadow.update(now, v.decision, charging, energy):
            self._shadow_store.async_delay_save(
                lambda: {"vehicles": {x.sub_id: x.shadow.to_dict() for x in self.vehicles.values()}}, 30)

    def _compute_plan(self, v: Vehicle, now: datetime) -> None:
        v.evcc_live = live_vehicle(self.evcc_state, v.cfg[V_EVCC_VEHICLE]) if v.cfg.get(V_EVCC_VEHICLE) else None
        # a sensor wins; evcc only fills in what no sensor says (and only while evcc has the car at a loadpoint)
        v.plugged = self._is_on(v.cfg.get(V_PLUGGED)) if v.cfg.get(V_PLUGGED) else (v.evcc_live["plugged"] if v.evcc_live else None)
        self._track_plug(v, now)
        v.charging = (self._is_on(v.cfg.get(V_CHARGING)) is True) if v.cfg.get(V_CHARGING) else bool(v.evcc_live and v.evcc_live["charging"])
        v.soc = self._float(v.cfg.get(V_SOC))
        v.soc_age_s = self._age_s(v.cfg.get(V_SOC), now) if v.soc is not None else None
        v.soc_stale = soc_is_stale(v.soc_age_s, float(v.cfg.get(V_SOC_MAX_AGE, DEFAULT_SOC_MAX_AGE_H)), v.charging)
        if v.soc_stale:  # too old to be believed: like an unknown state of charge (no plan, no warning)
            v.soc = None
        v.departure, v.departure_source = self._departure(v, now)
        weekday = (v.departure or (now + timedelta(days=1))).weekday()  # without a departure: tomorrow
        v.plan = self._plan_for(v, v.departure, weekday)
        v.consumption = (v.model.consumption_kwh_per_km() if v.model.consumption_known
                         else float(v.cfg.get(V_CONSUMPTION, DEFAULT_CONSUMPTION_100)) / 100.0)
        v.need = compute_need(
            v.plan, v.reserve_km, v.soc, float(v.cfg.get(V_CAPACITY) or 60.0), v.consumption,
            learn_km=v.learn_km or v.departure_source == "calendar", efficiency=v.efficiency or DEFAULT_EFFICIENCY, min_soc=self._min_soc(v))

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
            pref_kw=float(v.cfg.get(V_CHARGE_PREF, DEFAULT_CHARGE_PREF)),
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
        for t in v.trips:   # trips from the calendar replace the learned departure of their day
            d = dt_util.parse_datetime(t["departure"])
            if d is None or d <= now:
                continue
            out = [x for x in out if x.departure.date() != d.date()]
            if t.get("km"):
                out.append(Trip(d, float(t["km"]), float(t["range_km"])))
            else:
                out.append(trip_for(d, d.weekday()))
        out.sort(key=lambda t: t.departure)
        return out[:HORIZON_TRIPS]

    def _horizon(self, v: Vehicle, now: datetime, avail: dict[datetime, float] | None, max_kw: float) -> dict[str, Any] | None:
        """Where the energy for the next departures comes from and whether charging with the sun in advance saves grid energy. Works without
        a solar plant (then nothing is pre-charged). It recommends only."""
        if v.soc is None:
            return None
        capacity = float(v.cfg.get(V_CAPACITY) or 60.0)
        try:
            return horizon_plan(
                now, v.soc / 100.0 * capacity, capacity, v.consumption, self._trips(v, now, capacity), avail, max_kw,
                efficiency=v.efficiency or DEFAULT_EFFICIENCY, pref_kw=float(v.cfg.get(V_CHARGE_PREF, DEFAULT_CHARGE_PREF)))
        except Exception as err:  # noqa: BLE001 - a look-ahead that fails must never disturb the plan
            _LOGGER.debug("Plugwhen: look-ahead of %s failed: %s", v.name, err)
            return None

    # ---------- the warning ----------

    async def _maybe_send(self, v: Vehicle, now: datetime) -> None:
        await self._send_ready(v, now)
        await self._send_ahead(v, now)

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
        sent.append(key)
        del sent[:-SENT_KEEP]
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
