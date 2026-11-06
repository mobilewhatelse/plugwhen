"""One-off: the potential calculator in the Home Assistant layer (kept for the record)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
B = ROOT / "custom_components" / "plugwhen"


def patch(path, pairs):
    s = path.read_text(encoding="utf-8")
    for a, b in pairs:
        assert s.count(a) == 1, (str(path), a[:70], s.count(a))
        s = s.replace(a, b)
    path.write_text(s, encoding="utf-8")


# ---------------- potential.py: cleaning of the counter (pure)
patch(B / "potential.py", [(
    '''def car_quarter_kw(''', '''def clean_grid(grid: dict[datetime, float], max_kw: float = 30.0) -> dict[datetime, float]:
    """Drop counter jumps: an hour after a gap collects the missing hours, and nothing above `max_kw` is a real hourly mean."""
    return {t: v for t, v in grid.items() if 0.0 <= v <= max_kw and (t - HOUR) in grid}


def car_quarter_kw(''')])

# ---------------- const
patch(B / "const.py", [
    ('O_AVAIL = "availability_entity"', 'O_AVAIL = "availability_entity"\nO_GRID_ENERGY = "grid_energy_entity"       # grid import energy counter (for the potential calculator); taken from the guard if chosen\nO_PRICE_LOW = "price_low"                  # demand charge per kW and year (up to the threshold); taken from the guard if empty\nO_PRICE_HIGH = "price_high"                # ... above the threshold\nO_PRICE_THRESHOLD = "price_threshold"      # kW, 0 = one price'),
    ('PLAN_STATES = ', 'POTENTIAL_DAYS = 90\nPOTENTIAL_INTERVAL = timedelta(hours=24)\nPOTENTIAL_FIXED_KW = 4.1                   # "ready by" of the wallbox with 6 A on three phases\nPOTENTIAL_QUARTER_ADD_KW = 0.7             # how far the house goes above its hourly mean within an hour (measured 0.68 kW)\nPOTENTIAL_STATES = ["worth_it", "setting_enough", "little", "too_little_data", "no_data"]\nPLAN_STATES = '),
])

# ---------------- coordinator
patch(B / "coordinator.py", [
    ("    HISTORY_DAYS, HISTORY_INTERVAL, O_AVAIL, O_LOAD, O_WAECHTER,", "    HISTORY_DAYS, HISTORY_INTERVAL, O_AVAIL, O_GRID_ENERGY, O_LOAD, O_PRICE_HIGH, O_PRICE_LOW, O_PRICE_THRESHOLD,\n    O_WAECHTER, POTENTIAL_DAYS, POTENTIAL_FIXED_KW, POTENTIAL_INTERVAL, POTENTIAL_QUARTER_ADD_KW,"),
    ("from .plan import make_plan\n", "from .plan import make_plan\nfrom .potential import Prices, calculate as calculate_potential, clean_grid\n"),
    ("    availability_used: bool = False\n    load_used: bool = False", "    availability_used: bool = False\n    load_used: bool = False\n    potential: dict[str, Any] | None = None\n    potential_at: datetime | None = None"),
    ('''            self._compute(v, now)
        async_dispatcher_send(self.hass, self.signal)
        for v in self.vehicles.values():
            await self._maybe_send(v, now)

    # ---------- reading ----------''', '''            self._compute(v, now)
            if v.potential_at is None or now - v.potential_at >= POTENTIAL_INTERVAL:
                v.potential_at = now
                self.entry.async_create_background_task(self.hass, self._potential_and_tell(v), f"{DOMAIN} potential")
        async_dispatcher_send(self.hass, self.signal)
        for v in self.vehicles.values():
            await self._maybe_send(v, now)

    # ---------- reading ----------'''),
    ('''    def _load_entity(self) -> str | None:''', '''    # ---------- potential calculator ----------

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
            fixed_kw=min(full, POTENTIAL_FIXED_KW), guard_kw=guard_kw, quarter_add_kw=POTENTIAL_QUARTER_ADD_KW,
            prices=prices, measured_peaks=w.get("measured") or None,
        )
        result.update({
            "computed_at": now.isoformat(), "history_days": days,
            "sources": {"grid_energy": grid_id, "wallbox_energy": wb_id, "odometer": odo_id,
                        "prices": "settings" if self.entry.options.get(O_PRICE_LOW) else ("guard" if w.get("price_low") else None),
                        "guard_kw": guard_kw},
        })
        v.potential = result
        return result

    def _load_entity(self) -> str | None:'''),
])

# ---------------- __init__: service
patch(B / "__init__.py", [
    ("from homeassistant.config_entries import ConfigEntry\nfrom homeassistant.core import HomeAssistant\n",
     "from typing import Any\n\nimport voluptuous as vol\nfrom homeassistant.config_entries import ConfigEntry\nfrom homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse\nfrom homeassistant.exceptions import ServiceValidationError\nfrom homeassistant.helpers.service import async_register_admin_service\n"),
    ("from .const import PLATFORMS\n", "from .const import DOMAIN, PLATFORMS, POTENTIAL_DAYS\n"),
    ('''    entry.async_on_unload(entry.add_update_listener(_reload))
    return True''', '''    entry.async_on_unload(entry.add_update_listener(_reload))
    _register_services(hass)
    return True


def _register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, "calculate_potential"):
        return

    async def handle(call: ServiceCall) -> dict[str, Any]:
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries or getattr(entries[0], "runtime_data", None) is None:
            raise ServiceValidationError("Plugwhen is not set up")
        plug = entries[0].runtime_data
        out = {}
        for v in plug.vehicles.values():
            r = await plug.async_potential(v, int(call.data.get("days", POTENTIAL_DAYS)))
            out[v.name] = {k: r.get(k) for k in ("status", "verdict", "saving_spread_per_year", "saving_spread_vs_guard_per_year",
                                                 "peak_as_is_kw", "peak_spread_kw", "days", "sessions", "model_error_kw", "missing")}
        from homeassistant.helpers.dispatcher import async_dispatcher_send

        async_dispatcher_send(hass, plug.signal)
        return {"vehicles": out}

    async_register_admin_service(
        hass, DOMAIN, "calculate_potential", handle,
        schema=vol.Schema({vol.Optional("days", default=POTENTIAL_DAYS): vol.All(vol.Coerce(int), vol.Range(min=14, max=365))}),
        supports_response=SupportsResponse.OPTIONAL,
    )'''),
])

# ---------------- sensor
patch(B / "sensor.py", [
    ("from .const import PLAN_STATES, READINESS_STATES\n", "from .const import PLAN_STATES, POTENTIAL_STATES, READINESS_STATES\n"),
    ("            ReadinessSensor(plug, v),\n", "            ReadinessSensor(plug, v),\n            PotentialSensor(plug, v),\n"),
    ('''class WeekPlanSensor(PlugwhenEntity, SensorEntity):''', '''class PotentialSensor(PlugwhenEntity, SensorEntity):
    """What spreading the charging would bring in this household, from its own history (an estimate, see potential.py).
    State: worth_it, setting_enough (the wallbox's own "ready by" with a low current is about as good), little,
    too_little_data, no_data (an entity is missing)."""

    _unrecorded_attributes = frozenset({"strategies"})
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
                "session_kwh_median", "window_h_median", "model_error_kw", "computed_at", "history_days", "sources", "missing", "error",
                "strategies")
        return {k: p.get(k) for k in keys if k in p}


class WeekPlanSensor(PlugwhenEntity, SensorEntity):'''),
])

# ---------------- config flow options
patch(B / "config_flow.py", [
    ("DEFAULT_RESERVE_KM, DEFAULT_SOC_MAX_AGE_H, DOMAIN, O_AVAIL, O_LOAD, O_WAECHTER,",
     "DEFAULT_RESERVE_KM, DEFAULT_SOC_MAX_AGE_H, DOMAIN, O_AVAIL, O_GRID_ENERGY, O_LOAD, O_PRICE_HIGH, O_PRICE_LOW,\n    O_PRICE_THRESHOLD, O_WAECHTER,"),
    ('''            _opt(O_AVAIL, current): _ent("sensor"),
        }))''', '''            _opt(O_AVAIL, current): _ent("sensor"),
            _opt(O_GRID_ENERGY, current): _ent("sensor", "energy"),
            _opt(O_PRICE_LOW, current): _num(0, 5000, 0.01, "/kW/a"),
            _opt(O_PRICE_HIGH, current): _num(0, 5000, 0.01, "/kW/a"),
            _opt(O_PRICE_THRESHOLD, current): _num(0, 100, 0.1, "kW"),
        }))'''),
])
print("ok")
