"""Sensors per vehicle: energy to charge, range needed, target state of charge, expected departure, weekly plan."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PlugwhenEntry
from .entity import PlugwhenEntity


async def async_setup_entry(hass: HomeAssistant, entry: PlugwhenEntry, add: AddConfigEntryEntitiesCallback) -> None:
    plug = entry.runtime_data
    for sub_id, v in plug.vehicles.items():
        add([
            NeedChargeSensor(plug, v),
            NeedRangeSensor(plug, v),
            TargetSocSensor(plug, v),
            DepartureSensor(plug, v),
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
            "consumption_kwh_per_km": v.model.consumption_kwh_per_km(),
        }
