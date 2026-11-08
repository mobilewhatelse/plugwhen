"""One-off: the look-ahead in the Home Assistant layer: coordinator, notice, sensor attributes, charts, dashboard (kept for the record)."""
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


# ---------------- coordinator ----------------
edit(PKG / "coordinator.py", [
    ("from .messages import notice_text\n", "from .horizon import Trip, horizon_plan\nfrom .messages import ahead_text, notice_text\n"),
    ("from .notice import Notice, check_ready, dedupe_key, should_check\n", "from .notice import Notice, ahead_key, check_ahead, check_ready, dedupe_key, should_check\n"),
    ("LOOKAHEAD_DAYS = 7\n", "LOOKAHEAD_DAYS = 7\nHORIZON_DAYS = 5              # days looked at for the look-ahead\nHORIZON_TRIPS = 4             # departures in the look-ahead\n"),
    ("    habit: dict | None = None                # when the car is charged (per weekday: day, night, in between)\n",
     "    habit: dict | None = None                # when the car is charged (per weekday: day, night, in between)\n"
     "    horizon: dict | None = None              # look-ahead over the next departures (deficits, pre-charging with the sun)\n"),
    ("            v.charge_plan = {\"status\": \"unknown_soc\", \"windows\": [], \"needed_kwh\": None, \"planned_kwh\": None}\n            v.notice = None\n",
     "            v.charge_plan = {\"status\": \"unknown_soc\", \"windows\": [], \"needed_kwh\": None, \"planned_kwh\": None}\n            v.notice = None\n            v.horizon = None\n"),
    ("        hours = (v.departure - now).total_seconds() / 3600.0 if v.departure else None\n        planned = v.charge_plan[\"planned_kwh\"] if v.charge_plan[\"status\"] == \"planned\" else None\n",
     "        v.horizon = self._horizon(v, now, avail, max_kw)\n"
     "        hours = (v.departure - now).total_seconds() / 3600.0 if v.departure else None\n        planned = v.charge_plan[\"planned_kwh\"] if v.charge_plan[\"status\"] == \"planned\" else None\n"),
    ("    # ---------- the warning ----------\n\n    async def _maybe_send(self, v: Vehicle, now: datetime) -> None:\n        n = v.notice\n",
     '''    # ---------- the look-ahead ----------

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
'''),
    ("""        title, message = notice_text(self.hass.config.language, n, v.name, v.departure)
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
        _LOGGER.info("Plugwhen: warning '%s' sent for %s", n.kind, v.name)""",
     """        title, message = notice_text(self.hass.config.language, n, v.name, v.departure)
        if await self._deliver(v, services, title, message, key):
            _LOGGER.info("Plugwhen: warning '%s' sent for %s", n.kind, v.name)"""),
])

# ---------------- charts ----------------
edit(PKG / "charts.py", [
    ("* `chart_habit`: when the car is charged, per weekday: energy during the day, at night and in between.\n",
     "* `chart_habit`: when the car is charged, per weekday: energy during the day, at night and in between.\n"
     "* `chart_horizon`: the next departures: where the energy comes from (sun in the same window, sun charged in advance, grid) and the latest start.\n"),
    ('GREEN, RED, BLUE, GREY, SUN = "#2fbf71", "#e5534b", "#5b8def", "#8a94a6", "#f2b632"',
     'GREEN, RED, BLUE, GREY, SUN = "#2fbf71", "#e5534b", "#5b8def", "#8a94a6", "#f2b632"\nORANGE = "#f0883e"'),
    ('        habit_few="Ladegewohnheit: noch zu wenig Daten (28 Tage nötig)",',
     '        latest="spätestens ab", hz_title="Die nächsten Abfahrten: woher kommt der Strom?", hz_sun="Sonne im selben Fenster", hz_pre="mit Sonne vorgeladen",\n'
     '        hz_grid="Netz", hz_none="Für die nächsten Abfahrten ist nichts nachzuladen", hz_unknown="Ladestand unbekannt: keine Vorschau",\n'
     '        hz_trips="Keine Abfahrten gelernt: keine Vorschau", hz_saved="Vorladen mit Sonne spart {x} kWh Netzstrom", hz_nosun="Ohne Solarprognose kommt alles aus dem Netz, verteilt",\n'
     '        habit_few="Ladegewohnheit: noch zu wenig Daten (28 Tage nötig)",'),
    ('        habit_few="Charging habit: too little data yet (28 days needed)",',
     '        latest="latest start", hz_title="The next departures: where does the energy come from?", hz_sun="sun in the same window", hz_pre="charged ahead with the sun",\n'
     '        hz_grid="grid", hz_none="Nothing to charge for the next departures", hz_unknown="State of charge unknown: no preview",\n'
     '        hz_trips="No departures learned: no preview", hz_saved="Charging ahead with the sun saves {x} kWh of grid energy", hz_nosun="Without a solar forecast everything comes from the grid, spread",\n'
     '        habit_few="Charging habit: too little data yet (28 days needed)",'),
    ("""    xd = x(end)
    body.append(f"<line x1='{xd:.1f}' y1='{top - 8}' x2='{xd:.1f}' y2='{top + ph}' stroke='{RED}' stroke-width='2'/>")""",
     """    ls = _as_dt((plan or {}).get("latest_start"))
    if ls is not None and start <= ls < end and status in ("planned", "infeasible"):          # the latest start at full power
        xl = x(ls)
        body.append(f"<line x1='{xl:.1f}' y1='{top}' x2='{xl:.1f}' y2='{top + ph}' stroke='{RED}' stroke-width='1.5' stroke-dasharray='5 4'/>")
        body.append(_text(xl - 5, top + 14, f"{t['latest']} {t['wd'][ls.weekday()]} {ls:%H:%M}", "end", fill=RED, size=11))
    xd = x(end)
    body.append(f"<line x1='{xd:.1f}' y1='{top - 8}' x2='{xd:.1f}' y2='{top + ph}' stroke='{RED}' stroke-width='2'/>")"""),
])
cs = (PKG / "charts.py").read_text(encoding="utf-8")
cs += '''

def chart_horizon(horizon: dict[str, Any] | None, lang: str | None = None) -> str:
    """Per coming departure one stacked bar of the energy it needs from the wallbox: sun in the same window (yellow), sun charged in
    advance (orange), grid (blue); below the bar the latest start at the preferred power. Without a solar forecast everything is grid."""
    t = _t(lang)
    status = (horizon or {}).get("status")
    if horizon is None or status == "unknown_soc":
        return _msg(t["hz_unknown"])
    if status == "no_trips":
        return _msg(t["hz_trips"])
    if status == "no_need":
        return _msg(f"✓ {t['hz_none']}", GREEN)
    days = horizon.get("days") or []
    if not days:
        return _msg(t["hz_trips"])
    W, L, R, top, ph = 640, 40, 16, 40, 150
    H = 300
    vmax = float(int(max(4.0, max(float(d.get("need_kwh") or 0) for d in days))) + 1)
    step = max(1, int(vmax) // 4)
    body = [_text(10, 20, t["hz_title"], weight="700", size=13)]
    for k in range(0, int(vmax) + 1, step):
        y = top + ph - ph * k / vmax
        body.append(f"<line x1='{L}' y1='{y:.1f}' x2='{W - R}' y2='{y:.1f}' stroke='{GREY}' stroke-opacity='0.2'/>")
        body.append(_text(L - 6, y + 4, f"{k}", "end", size=10))
    bw = (W - L - R) / len(days)
    for i, d in enumerate(days):
        dep = _as_dt(d.get("departure"))
        x = L + i * bw
        base = top + ph
        for key, colour in (("sun_direct_kwh", SUN), ("precharge_kwh", ORANGE), ("grid_kwh", BLUE)):
            h = ph * float(d.get(key) or 0) / vmax
            if h > 0.5:
                base -= h
                body.append(f"<rect x='{x + 14:.1f}' y='{base:.1f}' width='{bw - 28:.1f}' height='{h:.1f}' fill='{colour}'/>")
        need = float(d.get("need_kwh") or 0)
        if need > 0:
            body.append(_text(x + bw / 2, base - 5, f"{need:.1f} kWh", "middle", size=11))
        if dep is not None:
            body.append(_text(x + bw / 2, top + ph + 16, f"{t['wd'][dep.weekday()]} {dep:%H:%M}", "middle"))
        ls = _as_dt(d.get("latest_start_pref"))
        if ls is not None and float(d.get("grid_kwh") or 0) > 0:
            body.append(_text(x + bw / 2, top + ph + 30, f"{t['latest']}", "middle", size=10))
            body.append(_text(x + bw / 2, top + ph + 42, f"{t['wd'][ls.weekday()]} {ls:%H:%M}", "middle", size=10, weight="700"))
    ly = H - 30
    for j, (key, colour) in enumerate((("hz_sun", SUN), ("hz_pre", ORANGE), ("hz_grid", BLUE))):
        xx = L + j * 200
        body.append(f"<rect x='{xx}' y='{ly - 9}' width='10' height='10' fill='{colour}'/>" + _text(xx + 15, ly, t[key], size=11))
    saved = float(horizon.get("saved_grid_kwh") or 0)
    if saved > 0:
        body.append(_text(L, H - 8, t["hz_saved"].format(x=f"{saved:.0f}"), fill=ORANGE, weight="700", size=12))
    elif not horizon.get("sun_used"):
        body.append(_text(L, H - 8, t["hz_nosun"], size=11))
    return _svg(W, H, "".join(body))
'''
(PKG / "charts.py").write_text(cs, encoding="utf-8")

# ---------------- sensor ----------------
edit(PKG / "sensor.py", [
    ("from .charts import chart_habit, chart_learning, chart_plan, chart_plugs, chart_potential, chart_shadow\n",
     "from .charts import chart_habit, chart_horizon, chart_learning, chart_plan, chart_plugs, chart_potential, chart_shadow\n"),
    ('    _unrecorded_attributes = frozenset({"windows", "chart"})', '    _unrecorded_attributes = frozenset({"windows", "chart", "horizon", "horizon_chart"})'),
    ('            "pref_kw": float(v.cfg.get("charge_kw_pref") or 4.0),\n',
     '            "pref_kw": float(v.cfg.get("charge_kw_pref") or 4.0),\n'
     '            "horizon": v.horizon, "horizon_chart": chart_horizon(v.horizon, self.hass.config.language),\n'),
])

# ---------------- dashboard ----------------
edit(PKG / "dashboard.py", [
    ('        learn_h="Lernmodus", mode_name="Betriebsart", would="Würde schalten",',
     '        hz_h="Die nächsten Abfahrten", hz_next="Nächstes nötiges Laden", hz_for="für", hz_latest="spätestens ab", hz_at="bei", hz_pre="Mit Sonne vorladen",\n'
     '        hz_replaces="ersetzt Netzstrom vor", hz_note="Eine Empfehlung: Plugwhen schaltet nichts. Ohne Solaranlage zeigt die Grafik nur den Bedarf je Abfahrt.",\n'
     '        learn_h="Lernmodus", mode_name="Betriebsart", would="Würde schalten",'),
    ('        learn_h="Learn mode", mode_name="Mode", would="Would switch",',
     '        hz_h="The next departures", hz_next="Next charging needed", hz_for="for", hz_latest="latest start", hz_at="at", hz_pre="Charge ahead with the sun",\n'
     '        hz_replaces="replaces grid energy before", hz_note="A recommendation: Plugwhen switches nothing. Without a solar plant the chart only shows the need per departure.",\n'
     '        learn_h="Learn mode", mode_name="Mode", would="Would switch",'),
    ('    hb_id = ids["habit"]\n', '''    hz_tpl = (
        "{% set wd = " + t["wd"] + " %}{% set a = " + _s(ids["charge_plan"]) + ".attributes %}{% set h = a.horizon %}"
        "{% if h and h.status == 'ok' %}"
        "{% set ns = namespace(first=none) %}"
        "{% for d in h.days %}{% if ns.first is none and d.grid_kwh > 0 %}{% set ns.first = d %}{% endif %}{% endfor %}"
        "{% if ns.first %}{% set ws = ns.first.window_start | as_datetime | as_local %}{% set dp = ns.first.departure | as_datetime | as_local %}"
        "**@NEXT@:** {{ wd[ws.weekday()] }} {{ ws.strftime('%H:%M') }} (@FOR@ {{ wd[dp.weekday()] }} {{ dp.strftime('%H:%M') }}): {{ ns.first.grid_kwh }} kWh"
        "{% if ns.first.latest_start_pref %}{% set ls = ns.first.latest_start_pref | as_datetime | as_local %}"
        ", @LATEST@ {{ wd[ls.weekday()] }} {{ ls.strftime('%H:%M') }} @AT@ {{ a.pref_kw }} kW{% endif %}{% endif %}"
        "{% for p in h.precharge %}{% set sf = p.sun_from | as_datetime | as_local %}{% set st = p.sun_to | as_datetime | as_local %}{% set fd = p.for_departure | as_datetime | as_local %}"
        "\\n\\n**@PRE@:** {{ wd[sf.weekday()] }} {{ sf.strftime('%H:%M') }}–{{ st.strftime('%H:%M') }}: {{ p.kwh }} kWh (@REPL@ {{ wd[fd.weekday()] }} {{ fd.strftime('%H:%M') }})"
        "{% endfor %}"
        "{% endif %}"
    )
    for key, text in (("@NEXT@", t["hz_next"]), ("@FOR@", t["hz_for"]), ("@LATEST@", t["hz_latest"]), ("@AT@", t["hz_at"]), ("@PRE@", t["hz_pre"]), ("@REPL@", t["hz_replaces"])):
        hz_tpl = hz_tpl.replace(key, text)
    hb_id = ids["habit"]
'''),
    ('            {"type": "markdown", "content": _chart(ids["charge_plan"])},\n            {"type": "markdown", "content": calib_line},\n',
     '            {"type": "markdown", "content": _chart(ids["charge_plan"])},\n            {"type": "markdown", "content": calib_line},\n'
     '            {"type": "heading", "heading": head(t["hz_h"]), "icon": "mdi:calendar-arrow-right"},\n'
     '            {"type": "markdown", "content": _chart(ids["charge_plan"], "horizon_chart")},\n'
     '            {"type": "markdown", "content": hz_tpl},\n'),
])

# ---------------- installation test ----------------
edit(ROOT / "tests" / "install" / "itest.py", [
    ('        hb = find("sensor", "charging_habit")\n',
     '        pa_h = state(pid)["attributes"]\n'
     '        log("horizon" in pa_h and str(pa_h.get("horizon_chart", "")).startswith("<svg"),\n'
     '            "the charge plan carries the look-ahead and its chart (valid SVG), also without a solar plant", f"{(pa_h.get(\'horizon\') or {}).get(\'status\')} / {str(pa_h.get(\'horizon_chart\'))[:30]}")\n'
     '        hb = find("sensor", "charging_habit")\n'),
])
print("ok")
