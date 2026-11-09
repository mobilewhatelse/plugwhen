"""Sensors per vehicle: energy to charge, range needed, target state of charge, expected departure, weekly plan."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import PlugwhenEntry
from .charts import (chart_habit, chart_horizon, chart_learning, chart_plan, chart_plugs, chart_potential, chart_shadow,
                     chart_sun_windows)
from .const import LEARNING_STATES, PLAN_STATES, POTENTIAL_STATES, READINESS_STATES, WOULD_STATES
from .entity import PlugwhenEntity


async def async_setup_entry(hass: HomeAssistant, entry: PlugwhenEntry, add: AddConfigEntryEntitiesCallback) -> None:
    plug = entry.runtime_data
    for sub_id, v in plug.vehicles.items():
        add([
            NeedChargeSensor(plug, v),
            NeedRangeSensor(plug, v),
            TargetSocSensor(plug, v),
            DepartureSensor(plug, v),
            ChargePlanSensor(plug, v),
            ReadinessSensor(plug, v),
            PotentialSensor(plug, v),
            WouldSwitchSensor(plug, v),
            LearningCheckSensor(plug, v),
            ChargingHabitSensor(plug, v),
            WeekPlanSensor(plug, v),
        ], config_subentry_id=sub_id)


class NeedChargeSensor(PlugwhenEntity, SensorEntity):
    """Energy still to take from the wallbox to be ready at the next departure."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 1
    _attr_icon = "mdi:ev-plug-type2"

    def __init__(self, plug, vehicle) -> None:
        super().__init__(plug, vehicle, "need_charge")

    @property
    def native_value(self) -> float | None:
        n = self.vehicle.need
        return n.charge_kwh if n is not None and self.vehicle.soc is not None else None  # unknown state of charge: unknown

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        v, n = self.vehicle, self.vehicle.need
        return {
            "source": n.source if n else None,
            "reachable": n.reachable if n else None,
            "range_km": n.km if n else None,
            "energy_kwh": n.kwh if n else None,
            "target_soc": n.target_soc if n else None,
            "soc": v.soc,
            "soc_stale": v.soc_stale,
            "soc_age_h": round(v.soc_age_s / 3600.0, 2) if v.soc_age_s is not None else None,
            "plugged": v.plugged,
            "reserve_km": v.reserve_km,
            "learn_km": v.learn_km,
            "efficiency": v.efficiency or 0.9, "efficiency_learned": v.efficiency is not None,
            "departure": v.departure.isoformat() if v.departure else None,
            "samples": v.plan.samples if v.plan else 0,
        }


class NeedRangeSensor(PlugwhenEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_suggested_display_precision = 0
    _attr_icon = "mdi:map-marker-distance"

    def __init__(self, plug, vehicle) -> None:
        super().__init__(plug, vehicle, "need_range")

    @property
    def native_value(self) -> float | None:
        n = self.vehicle.need
        return n.km if n is not None else None


class TargetSocSensor(PlugwhenEntity, SensorEntity):
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_suggested_display_precision = 0
    _attr_icon = "mdi:battery-charging-high"

    def __init__(self, plug, vehicle) -> None:
        super().__init__(plug, vehicle, "target_soc")

    @property
    def native_value(self) -> float | None:
        n = self.vehicle.need
        return n.target_soc if n is not None else None


class DepartureSensor(PlugwhenEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:car-clock"

    def __init__(self, plug, vehicle) -> None:
        super().__init__(plug, vehicle, "departure")

    @property
    def native_value(self) -> datetime | None:
        return self.vehicle.departure


class ChargePlanSensor(PlugwhenEntity, SensorEntity):
    """The charging plan until the next departure. The attributes are the interface other integrations read
    (for example the quarter-hour peak guard): `windows`, `needed_kwh`, `planned_kwh`, `departure`, `target_soc`, `executed`."""

    _unrecorded_attributes = frozenset({"windows", "chart", "horizon", "horizon_chart", "sun_chart"})
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = PLAN_STATES
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, plug, vehicle) -> None:
        super().__init__(plug, vehicle, "charge_plan")

    @property
    def native_value(self) -> str | None:
        p = self.vehicle.charge_plan
        return p["status"] if p else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        v, p = self.vehicle, self.vehicle.charge_plan or {}
        iso = lambda t: t.isoformat() if t else None  # noqa: E731
        return {
            "windows": [{"start": iso(w["start"]), "end": iso(w["end"]), "energy_kwh": w["energy_kwh"],
                         "available_kwh": w["available_kwh"], "peak_kw": w["peak_kw"]} for w in p.get("windows", [])],
            "needed_kwh": p.get("needed_kwh"), "planned_kwh": p.get("planned_kwh"),
            "available_kwh": p.get("available_kwh"), "grid_kwh": p.get("grid_kwh"), "shortfall_kwh": p.get("shortfall_kwh"),
            "departure": iso(v.departure), "departure_source": v.departure_source,
            # Plugwhen does not switch the wallbox (modes off and learn): readers must not take the plan as what the car will do.
            # Becomes True with a mode that executes the plan.
            "executed": False,
            "target_soc": v.need.target_soc if v.need else None,
            "ready_at": iso(p.get("ready_at")), "latest_start": iso(p.get("latest_start")),
            "load_forecast_used": v.load_used, "load_entity": self.plug._load_entity(), "availability_used": v.availability_used,
            "availability_source": v.availability_source,
            "solar_factor": self.plug.solar_factor(), "solar_deduct_kw": self.plug.solar_deduct_kw(),
            "solar_deduct_source": self.plug.solar_deduct_source(), "spread_floor_kw": p.get("spread_floor_kw"),
            "pref_kw": float(v.cfg.get("charge_kw_pref") or 4.0),
            "horizon": v.horizon, "horizon_chart": chart_horizon(v.horizon, self.hass.config.language),
            "sun_chart": chart_sun_windows(v.horizon, dt_util.now(), self.hass.config.language),
            "chart": chart_plan(p, dt_util.now(), float(v.cfg.get("charge_kw_max") or 11.0), self.hass.config.language),
        }


class ReadinessSensor(PlugwhenEntity, SensorEntity):
    """Will the car be ready at the next departure? `ready`, or what to do: `plug_in`, `low`, `too_late`, `not_reachable`."""

    _unrecorded_attributes = frozenset({"plug_chart"})
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = READINESS_STATES
    _attr_icon = "mdi:car-electric"

    def __init__(self, plug, vehicle) -> None:
        super().__init__(plug, vehicle, "readiness")

    @property
    def native_value(self) -> str:
        if self.vehicle.soc is None:
            return "unknown"
        n = self.vehicle.notice
        return n.kind if n is not None else "ready"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        n = self.vehicle.notice
        v = self.vehicle
        out = {"shortfall_kwh": n.shortfall_kwh if n else 0.0, "max_possible_kwh": n.max_possible_kwh if n else None,
               "soc_stale": v.soc_stale}
        if v.cfg.get("plugged_entity"):   # how the car was actually plugged in over the last four weeks
            out["plugging"] = v.plug_log.summary(dt_util.now())
            out["plug_chart"] = chart_plugs(v.plug_log.intervals(), dt_util.now(), self.hass.config.language)
        return out


class PotentialSensor(PlugwhenEntity, SensorEntity):
    """What spreading the charging would bring in this household, from its own history (an estimate, see potential.py).
    State: worth_it, setting_enough (the wallbox's own "ready by" with a low current is about as good), little,
    too_little_data, no_data (an entity is missing)."""

    _unrecorded_attributes = frozenset({"strategies", "chart"})
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = POTENTIAL_STATES
    _attr_icon = "mdi:chart-bell-curve-cumulative"

    def __init__(self, plug, vehicle) -> None:
        super().__init__(plug, vehicle, "potential")

    @property
    def native_value(self) -> str | None:
        p = self.vehicle.potential
        if not p:
            return None
        return p.get("verdict") if p.get("status") == "ok" else p.get("status")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        p = self.vehicle.potential or {}
        keys = ("saving_spread_per_year", "saving_spread_vs_guard_per_year", "peak_as_is_kw", "peak_spread_kw", "days", "sessions",
                "session_kwh_median", "window_h_median", "sessions_with_plug_times", "model_error_kw", "computed_at", "history_days", "sources", "missing", "error",
                "strategies")
        out = {k: p.get(k) for k in keys if k in p}
        cur = {"EUR": "€", "USD": "$", "GBP": "£"}.get(self.hass.config.currency or "EUR", self.hass.config.currency or "€")
        out["chart"] = chart_potential(p, self.hass.config.language, cur)
        return out


class WeekPlanSensor(PlugwhenEntity, SensorEntity):
    """The learned week. State = days the plan is based on; attribute `week` has one entry per weekday (0 = Monday)."""

    _unrecorded_attributes = frozenset({"week"})
    _attr_icon = "mdi:calendar-week"
    _attr_native_unit_of_measurement = "d"

    def __init__(self, plug, vehicle) -> None:
        super().__init__(plug, vehicle, "week_plan")

    @property
    def native_value(self) -> int:
        return self.vehicle.model.total_days

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        v = self.vehicle
        return {
            "week": [
                {"day": p.weekday, "samples": p.samples, "km_typical": p.km_typical, "km_high": p.km_high,
                 "drive_share": p.drive_share, "departure_hour": p.departure_hour, "home_charge_share": p.home_charge_share}
                for p in v.model.week()
            ],
            "history_days": v.history_days,
            "history_read": v.history_at.isoformat() if v.history_at else None,
            "history_error": v.history_error,
            "consumption_kwh_per_km": round(v.consumption, 3),
            "consumption_learned": v.model.consumption_known,
        }


class WouldSwitchSensor(PlugwhenEntity, SensorEntity):
    """Learn mode: what Plugwhen WOULD do right now (charge, pause, none = no decision, off = mode off). Nothing is switched.
    The attributes give the reason, when it is expected to change, the journal of the last decisions and how they compare with
    what the wallbox really did over the last days."""

    _unrecorded_attributes = frozenset({"journal", "chart"})
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = WOULD_STATES
    _attr_icon = "mdi:eye-outline"

    def __init__(self, plug, vehicle) -> None:
        super().__init__(plug, vehicle, "would_switch")

    @property
    def native_value(self) -> str:
        d = self.vehicle.decision
        return "off" if self.vehicle.mode != "learn" or d is None else d.action

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        v = self.vehicle
        d = v.decision
        iso = lambda t: t.isoformat() if t else None  # noqa: E731
        if v.mode != "learn" or d is None:
            return {"mode": v.mode}
        return {
            "mode": v.mode, "reason": d.reason, "planned_kw": d.kw, "until": iso(d.until),
            "summary": v.shadow.summary(dt_util.now()), "journal": v.shadow.journal[-12:][::-1],
            "chart": chart_shadow(v.shadow.days, dt_util.now().date(), self.hass.config.language),
        }


class LearningCheckSensor(PlugwhenEntity, SensorEntity):
    """Does the learning bring anything for this car? Walks through its history day by day (the model only knows the days before
    each day) and compares the range with the fixed reserve alone against the reserve lifted by what was learned, and how often
    the departure hour was guessed right. State: learning_helps, reserve_enough, little, too_little_data."""

    _unrecorded_attributes = frozenset({"chart", "departure_by_weekday"})
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = LEARNING_STATES
    _attr_icon = "mdi:school-outline"

    def __init__(self, plug, vehicle) -> None:
        super().__init__(plug, vehicle, "learning_check")

    @property
    def native_value(self) -> str:
        return self.plug.insight(self.vehicle)["verdict"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        r = self.plug.insight(self.vehicle)
        keys = ("days", "reserve_km", "coverage_reserve_pct", "coverage_learned_pct", "gain_points", "departure_right_pct",
                "departure_days", "departure_by_weekday", "ready_median_pct", "ready_early_pct", "departure_gain_points")
        return {**{k: r[k] for k in keys}, "chart": chart_learning(r, self.hass.config.language)}


class ChargingHabitSensor(PlugwhenEntity, SensorEntity):
    """When the car is charged: the share of the energy charged at night (20 to 7 h) over the last 90 days. The attributes give the
    day and the weekend share and, per weekday, the energy during the day, at night and in between, and a chart. It works without
    a solar plant: it only needs the energy counter of the wallbox. It does not judge (with a night tariff, night charging is fine)."""

    _unrecorded_attributes = frozenset({"chart", "by_weekday"})
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = "mdi:chart-bar-stacked"

    def __init__(self, plug, vehicle) -> None:
        super().__init__(plug, vehicle, "habit")

    @property
    def native_value(self) -> int | None:
        h = self.vehicle.habit
        return h.get("night_share_pct") if h and h.get("status") == "ok" else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        h = self.vehicle.habit or {"status": "no_data"}
        keys = ("status", "days", "total_kwh", "day_share_pct", "night_share_pct", "weekend_share_pct", "weekdays_night_share_pct")
        return {**{k: h.get(k) for k in keys}, "by_weekday": h.get("weekday"), "chart": chart_habit(h, self.hass.config.language)}
