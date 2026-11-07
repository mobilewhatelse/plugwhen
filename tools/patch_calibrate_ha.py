"""One-off: step A in the coordinator: early departure, preferred power, learned house numbers, solar accuracy (kept for the record)."""
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen" / "coordinator.py"
s = p.read_text(encoding="utf-8")


def rep(a, b):
    global s
    assert s.count(a) == 1, a[:90]
    s = s.replace(a, b)


rep("from .history import records_from_hourly, to_km, to_kwh\nfrom .insight import learning_check\n",
    "from .calibrate import SolarAccuracy, base_load_from_hourly, efficiency_from_records, quarter_add_from_5min\n"
    "from .history import records_from_hourly, to_km, to_kwh\nfrom .insight import learning_check\n")
rep("from .need import MIN_SAMPLES, Need, compute_need\n", "from .need import DEFAULT_EFFICIENCY, MIN_SAMPLES, Need, compute_need\n")
rep("    V_RESERVE, V_SOC, V_SOC_MAX_AGE, V_WALLBOX_ENERGY,\n)",
    "    V_RESERVE, V_SOC, V_SOC_MAX_AGE, V_WALLBOX_ENERGY, V_CHARGE_PREF, DEFAULT_CHARGE_PREF, CALIBRATE_INTERVAL,\n)")

rep("    insight_cache: tuple | None = None       # ((reserve, number of records, loaded at), result)\n",
    "    insight_cache: tuple | None = None       # ((reserve, number of records, loaded at), result)\n"
    "    efficiency: float | None = None          # learned share of the wallbox energy that reaches the battery (None = default)\n")

rep('        self._shadow_store: Store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.shadow")\n',
    '        self._shadow_store: Store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.shadow")\n'
    '        self._calib_store: Store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.calib")\n'
    '        self._calib: dict[str, Any] = {"quarter_add_kw": None, "base_load_kw": None, "at": None}\n'
    '        self._calib_at: datetime | None = None\n'
    '        self._solar_acc = SolarAccuracy()\n')

rep('        shadows = (await self._shadow_store.async_load() or {}).get("vehicles", {})\n',
    '        shadows = (await self._shadow_store.async_load() or {}).get("vehicles", {})\n'
    '        calib = await self._calib_store.async_load() or {}\n'
    '        if isinstance(calib.get("calib"), dict):\n'
    '            self._calib.update({k: calib["calib"].get(k) for k in ("quarter_add_kw", "base_load_kw", "at")})\n'
    '        self._solar_acc = SolarAccuracy(calib.get("solar"))\n')

rep("            self._solar = await self._solar_kw()\n",
    "            self._solar = await self._solar_kw()\n"
    "            self._note_solar_prediction(now)\n"
    "        if self._calib_at is None or now - self._calib_at >= CALIBRATE_INTERVAL:\n"
    "            self._calib_at = now\n"
    '            self.entry.async_create_background_task(self.hass, self._calibrate(now), f"{DOMAIN} calibrate")\n')

rep("        v.records = records\n", "        v.records = records\n        v.efficiency = efficiency_from_records(records)\n")

rep("""            p = v.model.plan(day.weekday())
            if p.departure_hour is None or p.samples < MIN_SAMPLES or (p.drive_share or 0.0) < MIN_DRIVE_SHARE:
                continue
            hour = int(p.departure_hour)
            dep = datetime.combine(day, time(hour, int(round((p.departure_hour - hour) * 60)) % 60), tzinfo=now.tzinfo)""",
    """            p = v.model.plan(day.weekday())
            target = p.departure_early if p.departure_early is not None else p.departure_hour   # the early departure: ready in time
            if target is None or p.samples < MIN_SAMPLES or (p.drive_share or 0.0) < MIN_DRIVE_SHARE:
                continue
            hour = int(target)
            dep = datetime.combine(day, time(hour, int(round((target - hour) * 60)) % 60), tzinfo=now.tzinfo)""")

rep("""            fixed_kw=min(full, POTENTIAL_FIXED_KW), guard_kw=guard_kw, quarter_add_kw=POTENTIAL_QUARTER_ADD_KW,""",
    """            fixed_kw=min(full, POTENTIAL_FIXED_KW), guard_kw=guard_kw, quarter_add_kw=self.quarter_add_kw(),""")
rep("""                        "guard_kw": guard_kw},""",
    """                        "guard_kw": guard_kw, "quarter_add_kw": self.quarter_add_kw(),
                        "quarter_add_learned": self._calib.get("quarter_add_kw") is not None},""")

rep("""            from_sun = surplus_from_solar(self._solar, float(self.entry.options.get(O_SOLAR_DEDUCT, DEFAULT_SOLAR_DEDUCT)), now)""",
    """            from_sun = surplus_from_solar(self._solar_scaled(), self.solar_deduct_kw(), now)""")

rep("""    # ---------- plug-in times ----------
""", '''    # ---------- learned house-specific numbers ----------

    def quarter_add_kw(self) -> float:
        """How far a quarter hour lies above its hour's mean: learned from the 5-minute statistics of the grid import, else the default."""
        return float(self._calib.get("quarter_add_kw") or POTENTIAL_QUARTER_ADD_KW)

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
        self._calib_store.async_delay_save(lambda: {"calib": self._calib, "solar": self._solar_acc.to_dict()}, 30)

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
                q = quarter_add_from_5min(series)
                if q is not None:
                    self._calib["quarter_add_kw"], changed = q, True
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
''')

rep("""        v.need = compute_need(
            v.plan, v.reserve_km, v.soc, float(v.cfg.get(V_CAPACITY) or 60.0), v.consumption, learn_km=v.learn_km)""",
    """        v.need = compute_need(
            v.plan, v.reserve_km, v.soc, float(v.cfg.get(V_CAPACITY) or 60.0), v.consumption, learn_km=v.learn_km,
            efficiency=v.efficiency or DEFAULT_EFFICIENCY)""")
rep("""            load=load, target_kw=target_kw if load is not None else None, available_kw=avail,
        )""", """            load=load, target_kw=target_kw if load is not None else None, available_kw=avail,
            pref_kw=float(v.cfg.get(V_CHARGE_PREF, DEFAULT_CHARGE_PREF)),
        )""")
p.write_text(s, encoding="utf-8")
print("ok")
