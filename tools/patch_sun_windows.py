"""One-off: sun windows (when does plugging in with the sun make sense?) in chart, sensor and dashboard (kept for the record).

User 08.11.2026: "the possible sun windows are missing: show when it would make sense to plug the car in with the sun, in the
times in which charging is possible".
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "custom_components" / "plugwhen"


def edit(name, pairs):
    p = PKG / name
    s = p.read_text(encoding="utf-8")
    crlf = "\r\n" in s
    s = s.replace("\r\n", "\n")
    for a, b in pairs:
        assert s.count(a) == 1, (name, a[:70])
        s = s.replace(a, b)
    if crlf:
        s = s.replace("\n", "\r\n")
    p.write_text(s, encoding="utf-8", newline="")


edit("charts.py", [
    ('''        habit_few="Ladegewohnheit: noch zu wenig Daten (28 Tage nötig)", habit_foot="nachts {n} % · tagsüber {d} % · Wochenende {w} % der Energie",
''', '''        habit_few="Ladegewohnheit: noch zu wenig Daten (28 Tage nötig)", habit_foot="nachts {n} % · tagsüber {d} % · Wochenende {w} % der Energie",
        sw_title="Sonnenfenster: wann das Anstecken bei Sonne Sinn macht", sw_home="Auto zu Hause", sw_sun="Sonne verfügbar", sw_rec="empfohlen: Anstecken lohnt",
        sw_nosun="Ohne Solarprognose gibt es keine Sonnenfenster", sw_none="Keine Sonne in den Zeiten, in denen das Auto zu Hause ist",
        sw_best="Am sinnvollsten: {d} {a}–{b}, bis zu {k} kWh", sw_only="Sonne da, aber nichts zu laden: {d} {a}–{b}",
'''),
    ('''        habit_few="Charging habit: too little data yet (28 days needed)", habit_foot="night {n} % · day {d} % · weekend {w} % of the energy",
''', '''        habit_few="Charging habit: too little data yet (28 days needed)", habit_foot="night {n} % · day {d} % · weekend {w} % of the energy",
        sw_title="Sun windows: when plugging in with the sun makes sense", sw_home="car at home", sw_sun="sun available", sw_rec="recommended: worth plugging in",
        sw_nosun="Without a solar forecast there are no sun windows", sw_none="No sun at the times the car is at home",
        sw_best="Best: {d} {a}-{b}, up to {k} kWh", sw_only="Sun, but nothing to charge: {d} {a}-{b}",
'''),
])

CHART = '''

def chart_sun_windows(horizon: dict[str, Any] | None, now: datetime, lang: str | None = None, days: int = 5) -> str:
    """One strip per day (0 to 24 h) for the next `days` days: grey where the car is expected at home (red tick = departure), yellow where
    the sun delivers power in that time, an orange frame where charging with the sun pays (it covers a need or replaces grid energy before a
    later departure). Needs a solar forecast; without one it says so."""
    t = _t(lang)
    status = (horizon or {}).get("status")
    if horizon is None or status in ("unknown_soc", "no_trips"):
        return _msg(t["hz_unknown"] if status == "unknown_soc" else t["hz_trips"])
    if not horizon.get("sun_used"):
        return _msg(t["sw_nosun"])
    wins = horizon.get("sun_windows") or []
    homes = [(_as_dt(d.get("window_start")), _as_dt(d.get("departure"))) for d in horizon.get("days") or []]
    homes = [(a, b) for a, b in homes if a and b]
    if not wins:
        return _msg(t["sw_none"])
    W, L, R, top, rh = 640, 74, 16, 34, 26
    H = top + days * rh + 62
    pw = W - L - R
    body = [_text(10, 20, t["sw_title"], weight="700", size=13)]
    for h in (0, 6, 12, 18, 24):
        xx = L + pw * h / 24
        body.append(f"<line x1='{xx:.1f}' y1='{top}' x2='{xx:.1f}' y2='{top + days * rh}' stroke='{GREY}' stroke-opacity='0.25'/>")
        body.append(_text(xx, top + days * rh + 14, f"{h}", "middle", size=10))

    def xpos(t0: datetime, d0: datetime) -> float:
        return L + pw * max(0.0, min(86400.0, (t0 - d0).total_seconds())) / 86400

    for i in range(days):
        d = (now + timedelta(days=i)).date()
        d0 = datetime.combine(d, time(0), tzinfo=now.tzinfo)
        d1 = d0 + timedelta(days=1)
        y = top + i * rh
        body.append(f"<rect x='{L}' y='{y + 2}' width='{pw}' height='{rh - 4}' fill='{GREY}' fill-opacity='0.08'/>")
        body.append(_text(L - 6, y + rh - 9, f"{t['wd'][d.weekday()]} {d:%d.%m.}", "end", size=10))
        for a, b in homes:
            lo, hi = max(a, d0), min(b, d1)
            if hi > lo:
                body.append(f"<rect x='{xpos(lo, d0):.1f}' y='{y + 2}' width='{max(1.5, xpos(hi, d0) - xpos(lo, d0)):.1f}' height='{rh - 4}' "
                            f"fill='{GREY}' fill-opacity='0.35'/>")
            if d0 <= b < d1:
                body.append(f"<rect x='{xpos(b, d0) - 1:.1f}' y='{y + 1}' width='2' height='{rh - 2}' fill='{RED}'/>")
        for w in wins:
            a, b = _as_dt(w.get("from")), _as_dt(w.get("to"))
            if not a or not b:
                continue
            lo, hi = max(a, d0), min(b, d1)
            if hi > lo:
                x1, x2 = xpos(lo, d0), xpos(hi, d0)
                wide = max(1.5, x2 - x1)
                body.append(f"<rect x='{x1:.1f}' y='{y + 5}' width='{wide:.1f}' height='{rh - 10}' fill='{SUN}'/>")
                if w.get("purpose") in ("need", "precharge"):
                    body.append(f"<rect x='{x1 - 1.5:.1f}' y='{y + 3}' width='{wide + 3:.1f}' height='{rh - 6}' fill='none' stroke='{ORANGE}' stroke-width='2'/>")
        if i == 0:
            xn = xpos(now, d0)
            body.append(f"<line x1='{xn:.1f}' y1='{y}' x2='{xn:.1f}' y2='{y + rh}' stroke='{BLUE}' stroke-width='2'/>")
    ly = top + days * rh + 32
    for j, (key, colour, frame) in enumerate((("sw_home", GREY, False), ("sw_sun", SUN, False), ("sw_rec", ORANGE, True))):
        x = L - 30 + j * 190
        if frame:
            body.append(f"<rect x='{x}' y='{ly - 9}' width='10' height='10' fill='none' stroke='{colour}' stroke-width='2'/>")
        else:
            opacity = "0.45" if colour == GREY else "1"
            body.append(f"<rect x='{x}' y='{ly - 9}' width='10' height='10' fill='{colour}' fill-opacity='{opacity}'/>")
        body.append(_text(x + 15, ly, t[key], size=11))
    best = horizon.get("best_sun_window")
    if best and _as_dt(best.get("from")) and _as_dt(best.get("to")):
        a, b = _as_dt(best["from"]), _as_dt(best["to"])
        kwh = float(best.get("used_kwh") or best.get("sun_kwh") or 0)
        body.append(_text(L - 30, H - 8, t["sw_best"].format(d=t["wd"][a.weekday()], a=f"{a:%H:%M}", b=f"{b:%H:%M}", k=f"{kwh:.0f}"),
                          fill=ORANGE, weight="700", size=12))
    else:
        w0 = next((w for w in wins if _as_dt(w.get("from")) and _as_dt(w.get("to"))), None)
        if w0:
            a, b = _as_dt(w0["from"]), _as_dt(w0["to"])
            body.append(_text(L - 30, H - 8, t["sw_only"].format(d=t["wd"][a.weekday()], a=f"{a:%H:%M}", b=f"{b:%H:%M}"), size=11))
    return _svg(W, H, "".join(body))
'''
p = PKG / "charts.py"
s = p.read_text(encoding="utf-8")
crlf = "\r\n" in s
s = s.replace("\r\n", "\n").rstrip("\n") + "\n" + CHART
if crlf:
    s = s.replace("\n", "\r\n")
p.write_text(s, encoding="utf-8", newline="")

edit("sensor.py", [
    ("from .charts import chart_habit, chart_horizon, chart_learning, chart_plan, chart_plugs, chart_potential, chart_shadow",
     "from .charts import (chart_habit, chart_horizon, chart_learning, chart_plan, chart_plugs, chart_potential, chart_shadow,\n                     chart_sun_windows)"),
    ('frozenset({"windows", "chart", "horizon", "horizon_chart"})', 'frozenset({"windows", "chart", "horizon", "horizon_chart", "sun_chart"})'),
    ('"horizon": v.horizon, "horizon_chart": chart_horizon(v.horizon, self.hass.config.language),',
     '"horizon": v.horizon, "horizon_chart": chart_horizon(v.horizon, self.hass.config.language),\n'
     '            "sun_chart": chart_sun_windows(v.horizon, dt_util.now(), self.hass.config.language),'),
])
edit("dashboard.py", [
    ('''            {"type": "markdown", "content": _chart(ids["charge_plan"], "horizon_chart")},
''', '''            {"type": "markdown", "content": _chart(ids["charge_plan"], "horizon_chart")},
            {"type": "markdown", "content": _chart(ids["charge_plan"], "sun_chart")},
'''),
])
print("ok")
