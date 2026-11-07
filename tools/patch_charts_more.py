"""One-off: three more charts (plan timeline, potential bars, plug-in strip) (kept for the record)."""
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen" / "charts.py"
s = p.read_text(encoding="utf-8")


def rep(a, b):
    global s
    assert s.count(a) == 1, a[:70]
    s = s.replace(a, b)


rep("""* `chart_shadow`: learn mode, per day: how long plan and wallbox agreed (green) and how long they differed (red).
""", """* `chart_shadow`: learn mode, per day: how long plan and wallbox agreed (green) and how long they differed (red).
* `chart_plan`: the charge plan as a timeline from now to the departure: charging windows as bars (yellow = sun, blue = grid).
* `chart_potential`: per way of charging the highest quarter hour of a month and the demand charge per year.
* `chart_plugs`: the last 14 days, when the car was plugged in (one strip per day, 0 to 24 h).
""")
rep("from datetime import date, timedelta", "from datetime import date, datetime, time, timedelta")
rep('GREEN, RED, BLUE, GREY = "#2fbf71", "#e5534b", "#5b8def", "#8a94a6"', 'GREEN, RED, BLUE, GREY, SUN = "#2fbf71", "#e5534b", "#5b8def", "#8a94a6", "#f2b632"')
rep('''        hours="h",
    ),
    "en": dict(''', '''        hours="h", sun="Sonne", grid="Netz", now="jetzt", departure_at="Abfahrt", nothing="Es muss nichts geladen werden",
        unknown_soc="Ladestand unbekannt: kein Plan", no_dep="Keine Abfahrt bekannt", missing="Es fehlen {kwh} kWh bis zur Abfahrt",
        pot_title="Höchste Viertelstunde und Leistungspreis je Ladeweise", not_ready="{n}× nicht fertig",
        w_as_is="wie bisher", w_guard="nur Spitzenwächter", w_fixed="Wallbox fertig-bis", w_spread="verteilt (Plugwhen)",
        pot_few="Potenzial: noch zu wenig Daten", pot_missing="Potenzial: es fehlen Daten",
        plugs_title="Angesteckt in den letzten 14 Tagen", no_plugs="Noch keine Steckzeiten mitgeschrieben",
    ),
    "en": dict(''')
rep('''        hours="h",
    ),
}''', '''        hours="h", sun="sun", grid="grid", now="now", departure_at="departure", nothing="Nothing needs to be charged",
        unknown_soc="State of charge unknown: no plan", no_dep="No departure known", missing="{kwh} kWh missing at departure",
        pot_title="Highest quarter hour and demand charge per way of charging", not_ready="{n}x not ready",
        w_as_is="as it was", w_guard="peak guard only", w_fixed="wallbox ready-by", w_spread="spread (Plugwhen)",
        pot_few="Potential: too little data yet", pot_missing="Potential: data missing",
        plugs_title="Plugged in over the last 14 days", no_plugs="No plug-in times recorded yet",
    ),
}''')

s += '''

def _msg(text: str, colour: str = GREY) -> str:
    return _svg(640, 56, _text(10, 34, text, fill=colour, size=15, weight="600"))


def _as_dt(v: Any) -> datetime | None:
    if isinstance(v, datetime):
        return v
    try:
        return datetime.fromisoformat(str(v))
    except (TypeError, ValueError):
        return None


def chart_plan(plan: dict[str, Any] | None, now: datetime, max_kw: float, lang: str | None = None) -> str:
    """Timeline from now to the departure with the planned charging windows (height = power, yellow part = sun, blue = grid)."""
    t = _t(lang)
    status = (plan or {}).get("status")
    dep = _as_dt((plan or {}).get("departure"))
    if status in (None, "unknown_soc"):
        return _msg(t["unknown_soc"])
    if status == "no_departure" or dep is None:
        return _msg(t["no_dep"])
    if status == "not_needed":
        return _msg(f"✓ {t['nothing']} · {t['departure_at']} {t['wd'][dep.weekday()]} {dep:%H:%M}", GREEN)
    W, H, L, R, top, ph = 640, 190, 16, 16, 34, 100
    start = now.replace(minute=0, second=0, microsecond=0)
    end = min(dep, start + timedelta(hours=72))
    span = max(1.0, (end - start).total_seconds())

    def x(tt: datetime) -> float:
        return L + (W - L - R) * max(0.0, min(1.0, (tt - start).total_seconds() / span))

    body = [f"<rect x='{L}' y='{top}' width='{W - L - R}' height='{ph}' rx='6' fill='{GREY}' fill-opacity='0.10'/>"]
    step = 3 if span <= 30 * 3600 else 6
    tt = start + timedelta(hours=(step - start.hour % step) % step)
    while tt <= end:
        xx = x(tt)
        body.append(f"<line x1='{xx:.1f}' y1='{top}' x2='{xx:.1f}' y2='{top + ph}' stroke='{GREY}' stroke-opacity='0.25'/>")
        label = f"{t['wd'][tt.weekday()]} 0" if tt.hour == 0 else f"{tt.hour}"
        body.append(_text(xx, top + ph + 16, label, "middle", size=10))
        tt += timedelta(hours=step)
    peak = max([max_kw] + [float(w.get("peak_kw") or 0) for w in (plan or {}).get("windows", [])]) or 1.0
    for w in (plan or {}).get("windows", []):
        a, b = _as_dt(w.get("start")), _as_dt(w.get("end"))
        if a is None or b is None or b <= start:
            continue
        x1, x2 = x(max(a, start)), x(min(b, end))
        hh = max(6.0, ph * float(w.get("peak_kw") or 0) / peak)
        energy = float(w.get("energy_kwh") or 0)
        sun = min(1.0, float(w.get("available_kwh") or 0) / energy) if energy > 0 else 0.0
        y0 = top + ph - hh
        body.append(f"<rect x='{x1:.1f}' y='{y0:.1f}' width='{max(2.0, x2 - x1):.1f}' height='{hh:.1f}' fill='{BLUE}'/>")
        if sun > 0.01:
            body.append(f"<rect x='{x1:.1f}' y='{top + ph - hh * sun:.1f}' width='{max(2.0, x2 - x1):.1f}' height='{hh * sun:.1f}' fill='{SUN}'/>")
        if x2 - x1 > 34:
            body.append(_text((x1 + x2) / 2, y0 - 5, f"{energy:.1f} kWh", "middle", size=10))
    xd = x(end)
    body.append(f"<line x1='{xd:.1f}' y1='{top - 8}' x2='{xd:.1f}' y2='{top + ph}' stroke='{RED}' stroke-width='2'/>")
    body.append(_text(min(xd, W - R), top - 12, f"{t['departure_at']} {t['wd'][dep.weekday()]} {dep:%H:%M}", "end", fill=RED, weight="700"))
    body.append(_text(L, top - 12, t["now"], weight="700"))
    ly = H - 12
    body.append(f"<rect x='{L}' y='{ly - 9}' width='10' height='10' fill='{SUN}'/>" + _text(L + 15, ly, t["sun"], size=11))
    body.append(f"<rect x='{L + 90}' y='{ly - 9}' width='10' height='10' fill='{BLUE}'/>" + _text(L + 105, ly, t["grid"], size=11))
    if status == "infeasible":
        body.append(_text(W - R, ly, t["missing"].format(kwh=(plan or {}).get("shortfall_kwh")), "end", fill=RED, weight="700"))
    return _svg(W, H, "".join(body))


def chart_potential(potential: dict[str, Any] | None, lang: str | None = None, currency: str = "€") -> str:
    """Per way of charging one bar: the highest quarter hour of a month (kW); behind it the demand charge per year and how often
    the car would not have been ready."""
    t = _t(lang)
    p = potential or {}
    if p.get("status") == "too_little_data":
        return _msg(t["pot_few"])
    if p.get("status") != "ok" or not p.get("strategies"):
        return _msg(t["pot_missing"])
    rows = []
    for key in ("as_is", "guard", "fixed", "spread"):
        st = p["strategies"].get(key)
        if not st or not st.get("peaks"):
            continue
        rows.append((t["w_" + key], max(st["peaks"].values()), st.get("cost_per_year"), int(st.get("not_ready") or 0), key))
    if not rows:
        return _msg(t["pot_missing"])
    W, L, bar_w, rh = 640, 160, 300, 34
    H = 40 + rh * len(rows) + 10
    vmax = max(r[1] for r in rows) or 1.0
    body = [_text(10, 20, t["pot_title"], weight="700", size=13)]
    for i, (label, kw, cost, miss, key) in enumerate(rows):
        y = 34 + i * rh
        colour = GREEN if key == "spread" else BLUE if key == "guard" else GREY
        body.append(_text(L - 8, y + 17, label, "end"))
        body.append(f"<rect x='{L}' y='{y}' width='{max(2.0, bar_w * kw / vmax):.1f}' height='24' rx='5' fill='{colour}'/>")
        info = f"{kw:.1f} kW" + (f" · {int(cost)} {currency}" if cost is not None else "")
        body.append(_text(L + bar_w * kw / vmax + 8, y + 17, info, weight="700", size=12))
        if miss:
            body.append(_text(W - 10, y + 17, t["not_ready"].format(n=miss), "end", fill=RED, weight="700", size=11))
    return _svg(W, H, "".join(body))


def chart_plugs(intervals: list[tuple[datetime, datetime | None]] | None, now: datetime, lang: str | None = None, days: int = 14) -> str:
    """One strip per day (0 to 24 h) for the last `days` days; blue where the car was plugged in."""
    t = _t(lang)
    if not intervals:
        return _msg(t["no_plugs"])
    W, L, R, top, rh = 640, 74, 16, 30, 14
    H = top + days * rh + 30
    pw = W - L - R
    body = [_text(10, 20, t["plugs_title"], weight="700", size=13)]
    for h in (0, 6, 12, 18, 24):
        xx = L + pw * h / 24
        body.append(f"<line x1='{xx:.1f}' y1='{top}' x2='{xx:.1f}' y2='{top + days * rh}' stroke='{GREY}' stroke-opacity='0.25'/>")
        body.append(_text(xx, top + days * rh + 14, f"{h}", "middle", size=10))
    for i in range(days):
        d = (now - timedelta(days=days - 1 - i)).date()
        d0 = datetime.combine(d, time(0), tzinfo=now.tzinfo)
        d1 = d0 + timedelta(days=1)
        y = top + i * rh
        body.append(f"<rect x='{L}' y='{y + 2}' width='{pw}' height='{rh - 4}' fill='{GREY}' fill-opacity='0.10'/>")
        body.append(_text(L - 6, y + rh - 3, f"{t['wd'][d.weekday()]} {d:%d.%m.}", "end", size=10))
        for a, b in intervals:
            b = b or now
            lo, hi = max(a, d0), min(b, d1, now)
            if hi > lo:
                x1 = L + pw * (lo - d0).total_seconds() / 86400
                x2 = L + pw * (hi - d0).total_seconds() / 86400
                body.append(f"<rect x='{x1:.1f}' y='{y + 2}' width='{max(1.5, x2 - x1):.1f}' height='{rh - 4}' fill='{BLUE}'/>")
    return _svg(W, H, "".join(body))
'''
p.write_text(s, encoding="utf-8")
print("ok")
