"""Connects the learning and the need with Home Assistant: reads statistics and states, computes, tells the entities."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import (
    DEFAULT_CONSUMPTION_100, DEFAULT_RESERVE_KM, DOMAIN, HISTORY_DAYS, HISTORY_INTERVAL, SUBENTRY_VEHICLE, UPDATE_INTERVAL,
    V_CAPACITY, V_CONSUMPTION, V_NAME, V_ODOMETER, V_PLUGGED, V_RESERVE, V_SOC, V_WALLBOX_ENERGY,
)
from .history import records_from_hourly, to_km, to_kwh
from .learning import MobilityModel, WeekdayPlan
from .need import MIN_SAMPLES, Need, compute_need

_LOGGER = logging.getLogger(__name__)
_BAD = (None, "", STATE_UNKNOWN, STATE_UNAVAILABLE)
LOOKAHEAD_DAYS = 7
MIN_DRIVE_SHARE = 0.5        # a weekday counts as a day of departure if the car is used on at least half of its days


@dataclass
class Vehicle:
    sub_id: str
    name: str
    cfg: dict[str, Any]
    reserve_km: float = DEFAULT_RESERVE_KM
    learn_km: bool = True
    model: MobilityModel = field(default_factory=MobilityModel)
    plan: WeekdayPlan | None = None
    need: Need | None = None
    departure: datetime | None = None
    soc: float | None = None
    plugged: bool | None = None
    history_days: int = 0
    history_at: datetime | None = None
    history_error: str | None = None


class Plugwhen:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.signal = f"{DOMAIN}_{entry.entry_id}_update"
        self.vehicles: dict[str, Vehicle] = {}
        self._unsub = None
        for sub in entry.subentries.values():
            if sub.subentry_type == SUBENTRY_VEHICLE:
                d = dict(sub.data)
                self.vehicles[sub.subentry_id] = Vehicle(
                    sub.subentry_id, d.get(V_NAME, "?"), d, reserve_km=float(d.get(V_RESERVE, DEFAULT_RESERVE_KM)))

    # ---------- life cycle ----------

    async def async_start(self) -> None:
        self._unsub = async_track_time_interval(self.hass, self._tick, UPDATE_INTERVAL)
        self.entry.async_create_background_task(self.hass, self._tick(), f"{DOMAIN} first run")

    async def async_stop(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None

    async def async_recompute(self, vehicle: Vehicle) -> None:
        """A setting of the vehicle changed (reserve, switch): compute again and tell the entities."""
        self._compute(vehicle, dt_util.now())
        async_dispatcher_send(self.hass, self.signal)

    async def _tick(self, _now: datetime | None = None) -> None:
        now = dt_util.now()
        for v in self.vehicles.values():
            if v.history_at is None or now - v.history_at >= HISTORY_INTERVAL:
                await self._load_history(v, now)
            self._compute(v, now)
        async_dispatcher_send(self.hass, self.signal)

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

    # ---------- the need ----------

    def _next_departure(self, v: Vehicle, now: datetime) -> datetime | None:
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

    def _compute(self, v: Vehicle, now: datetime) -> None:
        v.soc = self._float(v.cfg.get(V_SOC))
        v.plugged = self._is_on(v.cfg.get(V_PLUGGED))
        v.departure = self._next_departure(v, now)
        weekday = (v.departure or (now + timedelta(days=1))).weekday()  # without a learned departure: tomorrow
        v.plan = v.model.plan(weekday)
        consumption = (v.model.consumption_kwh_per_km() if v.model.consumption_known
                       else float(v.cfg.get(V_CONSUMPTION, DEFAULT_CONSUMPTION_100)) / 100.0)
        v.need = compute_need(
            v.plan, v.reserve_km, v.soc, float(v.cfg.get(V_CAPACITY) or 60.0), consumption, learn_km=v.learn_km)
