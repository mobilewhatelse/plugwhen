"""Sensors per vehicle: energy to charge, range needed, target state of charge, expected departure, weekly plan."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PlugwhenEntry
from .const import PLAN_STATES, READINESS_STATES
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
        return n.charge_kwh if n is not None else None

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
            "plugged": v.plugged,
            "reserve_km": v.reserve_km,
            "learn_km": v.learn_km,
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
    (for example the quarter-hour peak guard): `windows`, `needed_kwh`, `planned_kwh`, `departure`, `target_soc`."""

    _unrecorded_attributes = frozenset({"windows"})
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
            "target_soc": v.need.target_soc if v.need else None,
            "ready_at": iso(p.get("ready_at")), "latest_start": iso(p.get("latest_start")),
            "load_forecast_used": v.load_used, "availability_used": v.availability_used,
        }


class ReadinessSensor(PlugwhenEntity, SensorEntity):
    """Will the car be ready at the next departure? `ready`, or what to do: `plug_in`, `low`, `too_late`, `not_reachable`."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = READINESS_STATES
    _attr_icon = "mdi:car-electric"

    def __init__(self, plug, vehicle) -> None:
        super().__init__(plug, vehicle, "readiness")

    @property
    def native_value(self) -> str:
        n = self.vehicle.notice
        return n.kind if n is not None else "ready"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        n = self.vehicle.notice
        return {"shortfall_kwh": n.shortfall_kwh if n else 0.0, "max_possible_kwh": n.max_possible_kwh if n else None}


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
