"""One-off: the quarter-hour add of the house, measured on hours without wallbox charging and by load level (kept for the record).

Finding 08.11.2026: one learned value (0.26 kW) was dominated by quiet hours (80th percentile 0.13 kW) and in loaded hours (3 to 4 kW)
it contained the car's own current steps and the throttling of the guard, which the potential calculator models separately.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "custom_components" / "plugwhen"


def edit(path, pairs):
    p = path if isinstance(path, Path) else ROOT / path
    s = p.read_text(encoding="utf-8")
    for a, b in pairs:
        assert s.count(a) == 1, f"{p.name}: {a[:90]}"
        s = s.replace(a, b)
    p.write_text(s, encoding="utf-8")


edit(PKG / "potential.py", [
    ("          fixed_kw: float, quarter_add_kw: float) -> tuple[dict[datetime, float], float]:",
     "          fixed_kw: float, quarter_add) -> tuple[dict[datetime, float], float]:"),
    ("            hq = (_house(grid, car, h) or 0.0) + quarter_add_kw\n",
     "            hh = _house(grid, car, h) or 0.0\n            hq = hh + quarter_add(hh)\n"),
    ("    quarter_add_kw: float = 0.7,\n", "    quarter_add_kw: float | Callable[[float], float] = 0.7,\n"),
    ("            plan, miss = _plan(st, s, grid, car, full_kw, min_kw, guard_kw, fixed_kw, quarter_add_kw)",
     "            plan, miss = _plan(st, s, grid, car, full_kw, min_kw, guard_kw, fixed_kw, qa)"),
    ("            peaks[t.strftime(\"%Y-%m\")] = max(peaks[t.strftime(\"%Y-%m\")], house + quarter_add_kw + c)",
     "            peaks[t.strftime(\"%Y-%m\")] = max(peaks[t.strftime(\"%Y-%m\")], house + qa(house) + c)"),
    ("    hours = sorted(t for t in grid if t in car)\n    days = len({t.date() for t in hours})\n    sessions = find_sessions(grid, car, trips, plugged)",
     "    qa = quarter_add_kw if callable(quarter_add_kw) else (lambda _h, v=float(quarter_add_kw): v)   # a number or a function of the house load\n"
     "    hours = sorted(t for t in grid if t in car)\n    days = len({t.date() for t in hours})\n    sessions = find_sessions(grid, car, trips, plugged)"),
])
ps = (PKG / "potential.py").read_text(encoding="utf-8")
if "from collections.abc import Callable" not in ps:
    ps = ps.replace("from __future__ import annotations\n", "from __future__ import annotations\n\nfrom collections.abc import Callable\n", 1)
(PKG / "potential.py").write_text(ps, encoding="utf-8")

edit(PKG / "coordinator.py", [
    ("from .calibrate import SolarAccuracy, base_load_from_hourly, efficiency_from_records, quarter_add_from_5min\n",
     "from .calibrate import QuarterAddModel, SolarAccuracy, base_load_from_hourly, efficiency_from_records, quarter_add_samples\n"),
    ("        self._solar_acc = SolarAccuracy()\n", "        self._solar_acc = SolarAccuracy()\n        self._add_model = QuarterAddModel()\n"),
    ("        self._solar_acc = SolarAccuracy(calib.get(\"solar\"))\n", "        self._solar_acc = SolarAccuracy(calib.get(\"solar\"))\n        self._add_model = QuarterAddModel(calib.get(\"add\"))\n"),
    ("quarter_add_kw=self.quarter_add_kw(),", "quarter_add_kw=self.quarter_add_fn(),"),
    ('"guard_kw": guard_kw, "quarter_add_kw": self.quarter_add_kw(),\n                        "quarter_add_learned": self._calib.get("quarter_add_kw") is not None},',
     '"guard_kw": guard_kw, "quarter_add": self._add_model.summary(), "quarter_add_default_kw": POTENTIAL_QUARTER_ADD_KW},'),
    ('''    def quarter_add_kw(self) -> float:
        """How far a quarter hour lies above its hour's mean: learned from the 5-minute statistics of the grid import, else the default."""
        return float(self._calib.get("quarter_add_kw") or POTENTIAL_QUARTER_ADD_KW)''',
     '''    def quarter_add_fn(self):
        """How far a quarter hour lies above its hour's mean, as a function of the house load: learned for the house alone (hours without
        wallbox charging) by load level; the default applies for a level that has too few hours."""
        model = self._add_model

        def add(house_kw: float) -> float:
            v = model.value(house_kw)
            return POTENTIAL_QUARTER_ADD_KW if v is None else v

        return add'''),
    ("self._calib_store.async_delay_save(lambda: {\"calib\": self._calib, \"solar\": self._solar_acc.to_dict()}, 30)",
     "self._calib_store.async_delay_save(lambda: {\"calib\": self._calib, \"solar\": self._solar_acc.to_dict(), \"add\": self._add_model.to_dict()}, 30)"),
    ("""                q = quarter_add_from_5min(series)
                if q is not None:
                    self._calib["quarter_add_kw"], changed = q, True""",
     """                wb_ids = {x.cfg.get(V_WALLBOX_ENERGY) for x in self.vehicles.values()} - {None, ""}
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
                    changed = True"""),
])
print("ok")
