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
    DEFAULT_CHARGE_MAX, DEFAULT_CHARGE_MIN, DEFAULT_CONSUMPTION_100, DEFAULT_NOTIFY_HOUR, DEFAULT_RESERVE_KM, DEFAULT_SOC_MAX_AGE_H, DOMAIN,
    HISTORY_DAYS, HISTORY_INTERVAL, O_AVAIL, O_LOAD, O_WAECHTER, SUBENTRY_VEHICLE, UPDATE_INTERVAL, V_CAPACITY, V_CHARGE_MAX,
    V_CHARGE_MIN, V_CHARGING, V_CONSUMPTION, V_DEPARTURE, V_NAME, V_NOTIFY, V_NOTIFY_HOUR, V_ODOMETER, V_PLUGGED,
    V_RESERVE, V_SOC, V_SOC_MAX_AGE, V_WALLBOX_ENERGY,
)
from .freshness import soc_is_stale
from .history import records_from_hourly, to_km, to_kwh
from .links import pick
from .inputs import availability_from_attributes, departure_from_state, load_from_hours
from .learning import MobilityModel, WeekdayPlan
from .messages import notice_text
from .need import MIN_SAMPLES, Need, compute_need
from .notice import Notice, check_ready, dedupe_key, should_check
from .plan import make_plan

_LOGGER = logging.getLogger(__name__)
_BAD = (None, "", STATE_UNKNOWN, STATE_UNAVAILABLE)
LOOKAHEAD_DAYS = 7
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
        for sub in entry.subentries.values():
            if sub.subentry_type == SUBENTRY_VEHICLE:
                d = dict(sub.data)
                self.vehicles[sub.subentry_id] = Vehicle(
                    sub.subentry_id, d.get(V_NAME, "?"), d, reserve_km=float(d.get(V_RESERVE, DEFAULT_RESERVE_KM)))

    # ---------- life cycle ----------

    async def async_start(self) -> None:
        self._sent = (await self._store.async_load() or {}).get("sent", {})
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

    async def async_recompute(self, vehicle: Vehicle) -> None:
        """A setting of the vehicle changed (reserve, switch): compute again and tell the entities."""
        now = dt_util.now()
        self._compute(vehicle, now)
        async_dispatcher_send(self.hass, self.signal)
        await self._maybe_send(vehicle, now)

    async def _tick(self, _now: datetime | None = None) -> None:
        now = dt_util.now()
        for v in self.vehicles.values():
            if v.history_at is None or now - v.history_at >= HISTORY_INTERVAL:
                await self._load_history(v, now)
            self._compute(v, now)
        async_dispatcher_send(self.hass, self.signal)
        for v in self.vehicles.values():
            await self._maybe_send(v, now)

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
                {"state", "mean", "max"},
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
            if p.departure_hour is None or p.samples < MIN_SAMPLES or (p.drive_share or 0.0) < MIN_DRIVE_SHARE:
                continue
            hour = int(p.departure_hour)
            dep = datetime.combine(day, time(hour, int(round((p.departure_hour - hour) * 60)) % 60), tzinfo=now.tzinfo)
            if dep > now:
                return dep
        return None

    def _departure(self, v: Vehicle, now: datetime) -> tuple[datetime | None, str | None]:
        """The departure an entity names wins over the learned one."""
        eid = v.cfg.get(V_DEPARTURE)
        if eid:
            st = self._state(eid)
            dep = departure_from_state(st.state, now) if st is not None else None
            if dep is not None:
                return dep, "entity"
        dep = self._learned_departure(v, now)
        return dep, ("learned" if dep is not None else None)

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

    def _availability(self, now: datetime) -> dict[datetime, float] | None:
        st = self._state(self.entry.options.get(O_AVAIL))
        if st is None or st.state in _BAD:
            return None
        return availability_from_attributes(dict(st.attributes), now)

    def _compute(self, v: Vehicle, now: datetime) -> None:
        v.plugged = self._is_on(v.cfg.get(V_PLUGGED))
        v.charging = self._is_on(v.cfg.get(V_CHARGING)) is True
        v.soc = self._float(v.cfg.get(V_SOC))
        v.soc_age_s = self._age_s(v.cfg.get(V_SOC), now) if v.soc is not None else None
        v.soc_stale = soc_is_stale(v.soc_age_s, float(v.cfg.get(V_SOC_MAX_AGE, DEFAULT_SOC_MAX_AGE_H)), v.charging)
        if v.soc_stale:  # too old to be believed: like an unknown state of charge (no plan, no warning)
            v.soc = None
        v.departure, v.departure_source = self._departure(v, now)
        weekday = (v.departure or (now + timedelta(days=1))).weekday()  # without a departure: tomorrow
        v.plan = v.model.plan(weekday)
        v.consumption = (v.model.consumption_kwh_per_km() if v.model.consumption_known
                         else float(v.cfg.get(V_CONSUMPTION, DEFAULT_CONSUMPTION_100)) / 100.0)
        v.need = compute_need(
            v.plan, v.reserve_km, v.soc, float(v.cfg.get(V_CAPACITY) or 60.0), v.consumption, learn_km=v.learn_km)

        max_kw = float(v.cfg.get(V_CHARGE_MAX, DEFAULT_CHARGE_MAX))
        if v.soc is None:  # without the state of charge nothing can be said: no plan, no warning (the sensors say so)
            v.charge_plan = {"status": "unknown_soc", "windows": [], "needed_kwh": None, "planned_kwh": None}
            v.notice = None
            v.load_used = v.availability_used = False
            return
        load, target_kw = self._load_inputs(now)
        avail = self._availability(now)
        v.load_used, v.availability_used = load is not None, avail is not None
        v.charge_plan = make_plan(
            now, v.departure or now, v.need.charge_kwh, max_kw, float(v.cfg.get(V_CHARGE_MIN, DEFAULT_CHARGE_MIN)),
            load=load, target_kw=target_kw if load is not None else None, available_kw=avail,
        )
        hours = (v.departure - now).total_seconds() / 3600.0 if v.departure else None
        planned = v.charge_plan["planned_kwh"] if v.charge_plan["status"] == "planned" else None
        v.notice = check_ready(
            v.need, v.soc, plugged=v.plugged, charging=v.charging, hours_to_departure=hours, charge_kw_max=max_kw,
            planned_kwh=planned,
        )

    # ---------- the warning ----------

    async def _maybe_send(self, v: Vehicle, now: datetime) -> None:
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
        delivered = 0
        for service in services:
            domain, name = service.split(".", 1)
            try:
                await self.hass.services.async_call(domain, name, {"title": title, "message": message}, blocking=False)
                delivered += 1
            except Exception as err:  # noqa: BLE001 - a wrong service name must not stop the planner or the other phones
                _LOGGER.warning("Plugwhen: the warning for %s could not be sent through %s: %s", v.name, service, err)
        if not delivered:
            return
        sent.append(key)
        del sent[:-SENT_KEEP]
        self._store.async_delay_save(lambda: {"sent": self._sent}, 10)
        _LOGGER.info("Plugwhen: warning '%s' sent for %s", n.kind, v.name)
