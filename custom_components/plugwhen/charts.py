"""The two charts of the dashboard as SVG text (pure Python, no Home Assistant imports).

* `chart_learning`: does the learning bring anything for this car (from `insight.learning_check`): how many days the range would
  have been enough with the fixed reserve alone and with the learned value, and how often the departure hour was guessed right
  per weekday.
* `chart_shadow`: learn mode, per day: how long plan and wallbox agreed (green) and how long they differed (red).
* `chart_plan`: the charge plan as a timeline from now to the departure: charging windows as bars (yellow = sun, blue = grid).
* `chart_potential`: per way of charging the highest quarter hour of a month and the demand charge per year.
* `chart_plugs`: the last 14 days, when the car was plugged in (one strip per day, 0 to 24 h).
* `chart_habit`: when the car is charged, per weekday: energy during the day, at night and in between.
* `chart_horizon`: the next departures: where the energy comes from (sun in the same window, sun charged in advance, grid) and the latest start.

The sensors hand the SVG over as an attribute; a markdown card shows it with `![](data:image/svg+xml;utf8,...)`, so no custom card
is needed. Colours are mid tones that read on a dark and a light background.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any
from xml.sax.saxutils import escape

GREEN, RED, BLUE, GREY, SUN = "#2fbf71", "#e5534b", "#5b8def", "#8a94a6", "#f2b632"
ORANGE = "#f0883e"

T = {
    "de": dict(
        cover="Tage, an denen die Reichweite gereicht hätte", only_reserve="nur feste Reserve ({km} km)", with_learning="Reserve plus Gelerntes",
        departure="Rechtzeitig fertig je Wochentag (Plan bis zur frühen Abfahrt)", days_checked="{n} Tage geprüft", no_data="Noch zu wenig Daten",
        ready_title="Tage, an denen das Auto rechtzeitig fertig gewesen wäre", ready_median="Plan bis zur üblichen Abfahrt", ready_early="Plan bis zur frühen Abfahrt",
        wd=["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"], agree="Plan und Wallbox stimmten überein", differ="abweichend",
        shadow_title="Plan gegen Wirklichkeit, Stunden je Tag", no_shadow="Noch keine Daten: der Vergleich füllt sich Tag für Tag",
        hours="h", sun="Sonne", grid="Netz", now="jetzt", departure_at="Abfahrt", nothing="Es muss nichts geladen werden",
        unknown_soc="Ladestand unbekannt: kein Plan", no_dep="Keine Abfahrt bekannt", missing="Es fehlen {kwh} kWh bis zur Abfahrt",
        pot_title="Höchste Viertelstunde und Leistungspreis je Ladeweise", not_ready="{n}× nicht fertig",
        w_as_is="wie bisher", w_guard="nur Spitzenwächter", w_fixed="Wallbox fertig-bis", w_spread="verteilt (Plugwhen)",
        pot_few="Potenzial: noch zu wenig Daten", pot_missing="Potenzial: es fehlen Daten",
        plugs_title="Angesteckt in den letzten 14 Tagen", no_plugs="Noch keine Steckzeiten mitgeschrieben",
        habit_title="Wann laden Sie? kWh je Wochentag im Durchschnitt", habit_day="tagsüber (9–17 Uhr)", habit_night="nachts (20–7 Uhr)", habit_rest="sonst",
        latest="spätestens ab", hz_title="Die nächsten Abfahrten: woher kommt der Strom?", hz_sun="Sonne im selben Fenster", hz_pre="mit Sonne vorgeladen",
        hz_grid="Netz", hz_none="Für die nächsten Abfahrten ist nichts nachzuladen", hz_unknown="Ladestand unbekannt: keine Vorschau",
        hz_trips="Keine Abfahrten gelernt: keine Vorschau", hz_saved="Vorladen mit Sonne spart {x} kWh Netzstrom", hz_nosun="Ohne Solarprognose kommt alles aus dem Netz, verteilt",
        habit_few="Ladegewohnheit: noch zu wenig Daten (28 Tage nötig)", habit_foot="nachts {n} % · tagsüber {d} % · Wochenende {w} % der Energie",
        sw_title="Sonnenfenster: wann das Anstecken bei Sonne Sinn macht", sw_home="Auto zu Hause", sw_sun="Sonne verfügbar", sw_rec="empfohlen: Anstecken lohnt",
        sw_nosun="Ohne Solarprognose gibt es keine Sonnenfenster", sw_none="Keine Sonne in den Zeiten, in denen das Auto zu Hause ist",
        sw_best="Am sinnvollsten: {d} {a}–{b}, bis zu {k} kWh", sw_only="Sonne da, aber nichts zu laden: {d} {a}–{b}",
    ),
    "en": dict(
        cover="Days on which the range would have been enough", only_reserve="fixed reserve only ({km} km)", with_learning="reserve plus learned",
        departure="Ready in time per weekday (plan until the early departure)", days_checked="{n} days checked", no_data="Too little data yet",
        ready_title="Days on which the car would have been ready in time", ready_median="plan until the usual departure", ready_early="plan until the early departure",
        wd=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], agree="plan and wallbox agreed", differ="differed",
        shadow_title="Plan against reality, hours per day", no_shadow="No data yet: the comparison fills up day by day",
        hours="h", sun="sun", grid="grid", now="now", departure_at="departure", nothing="Nothing needs to be charged",
        unknown_soc="State of charge unknown: no plan", no_dep="No departure known", missing="{kwh} kWh missing at departure",
        pot_title="Highest quarter hour and demand charge per way of charging", not_ready="{n}x not ready",
        w_as_is="as it was", w_guard="peak guard only", w_fixed="wallbox ready-by", w_spread="spread (Plugwhen)",
        pot_few="Potential: too little data yet", pot_missing="Potential: data missing",
        plugs_title="Plugged in over the last 14 days", no_plugs="No plug-in times recorded yet",
        habit_title="When do you charge? kWh per weekday on average", habit_day="during the day (9 to 17 h)", habit_night="at night (20 to 7 h)", habit_rest="otherwise",
        latest="latest start", hz_title="The next departures: where does the energy come from?", hz_sun="sun in the same window", hz_pre="charged ahead with the sun",
        hz_grid="grid", hz_none="Nothing to charge for the next departures", hz_unknown="State of charge unknown: no preview",
        hz_trips="No departures learned: no preview", hz_saved="Charging ahead with the sun saves {x} kWh of grid energy", hz_nosun="Without a solar forecast everything comes from the grid, spread",
        habit_few="Charging habit: too little data yet (28 days needed)", habit_foot="night {n} % · day {d} % · weekend {w} % of the energy",
        sw_title="Sun windows: when plugging in with the sun makes sense", sw_home="car at home", sw_sun="sun available", sw_rec="recommended: worth plugging in",
        sw_nosun="Without a solar forecast there are no sun windows", sw_none="No sun at the times the car is at home",
        sw_best="Best: {d} {a}-{b}, up to {k} kWh", sw_only="Sun, but nothing to charge: {d} {a}-{b}",
    ),
}


def _t(lang: str | None) -> dict[str, Any]:
    return T["de" if (lang or "").lower().startswith("de") else "en"]


def _svg(w: int, h: int, body: str) -> str:
    return f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {w} {h}' width='{w}' font-family='sans-serif' font-size='12'>{body}</svg>"


def _text(x: float, y: float, s: str, anchor: str = "start", fill: str = GREY, weight: str = "400", size: int | None = None) -> str:
    sz = f" font-size='{size}'" if size else ""
    return f"<text x='{x:.1f}' y='{y:.1f}' text-anchor='{anchor}' fill='{fill}' font-weight='{weight}'{sz}>{escape(str(s))}</text>"


def chart_learning(check: dict[str, Any] | None, lang: str | None = None) -> str:
    t = _t(lang)
    W, H = 640, 330
    n = (check or {}).get("days") or 0
    if not check or check.get("coverage_reserve_pct") is None or n == 0:
        return _svg(W, 60, _text(10, 34, t["no_data"], size=14))
    body = [_text(10, 20, t["cover"], weight="700", size=13)]
    rows = [(t["only_reserve"].format(km=int(check.get("reserve_km") or 0)), check["coverage_reserve_pct"], GREY),
            (t["with_learning"], check["coverage_learned_pct"], GREEN)]
    left, bar_w = 190, 380
    for i, (label, pct, colour) in enumerate(rows):
        y = 34 + i * 34
        body.append(_text(left - 8, y + 17, label, "end"))
        body.append(f"<rect x='{left}' y='{y}' width='{bar_w}' height='24' rx='5' fill='{GREY}' fill-opacity='0.18'/>")
        body.append(f"<rect x='{left}' y='{y}' width='{max(2.0, bar_w * pct / 100):.1f}' height='24' rx='5' fill='{colour}'/>")
        body.append(_text(left + bar_w + 8, y + 17, f"{pct} %", weight="700", fill=colour if colour != GREY else GREY, size=13))
    body.append(_text(left, 112, t["days_checked"].format(n=n), size=11))

    shift = 0
    if check.get("ready_median_pct") is not None:
        H, shift = 440, 104
        body.append(_text(10, 150, t["ready_title"], weight="700", size=13))
        for i, (label, pct, colour) in enumerate(((t["ready_median"], check["ready_median_pct"], GREY),
                                                   (t["ready_early"], check["ready_early_pct"], GREEN))):
            y = 164 + i * 34
            body.append(_text(left - 8, y + 17, label, "end"))
            body.append(f"<rect x='{left}' y='{y}' width='{bar_w}' height='24' rx='5' fill='{GREY}' fill-opacity='0.18'/>")
            body.append(f"<rect x='{left}' y='{y}' width='{max(2.0, bar_w * pct / 100):.1f}' height='24' rx='5' fill='{colour}'/>")
            body.append(_text(left + bar_w + 8, y + 17, f"{pct} %", weight="700", fill=colour, size=13))

    body.append(_text(10, 150 + shift, t["departure"], weight="700", size=13))
    top, ph = 176 + shift, 110
    step = (W - 36) / 7
    bw = step - 22
    body.append(f"<line x1='10' y1='{top + ph}' x2='{W - 10}' y2='{top + ph}' stroke='{GREY}' stroke-opacity='0.4'/>")
    for wd, day in enumerate(check.get("departure_by_weekday") or []):
        x = 22 + wd * step
        pct = day.get("ready_early_pct")
        if pct is None:
            body.append(f"<rect x='{x}' y='{top + ph - 3}' width='{bw}' height='3' fill='{GREY}' fill-opacity='0.35'/>")
        else:
            hh = max(2.0, ph * pct / 100)
            colour = GREEN if pct >= 75 else BLUE if pct >= 50 else RED
            body.append(f"<rect x='{x}' y='{top + ph - hh:.1f}' width='{bw}' height='{hh:.1f}' rx='4' fill='{colour}'/>")
            body.append(_text(x + bw / 2, top + ph - hh - 5, f"{pct} %", "middle", size=11))
        body.append(_text(x + bw / 2, top + ph + 16, t["wd"][wd], "middle"))
        if day.get("days"):
            body.append(_text(x + bw / 2, top + ph + 30, f"n={day['days']}", "middle", size=10))
    return _svg(W, H, "".join(body))


def chart_shadow(days: dict[str, dict[str, float]] | None, today: date, lang: str | None = None, count: int = 14) -> str:
    """One bar per day of the last `count` days: green = hours in which the decision and the wallbox agreed, red = hours in
    which they differed (the wallbox charged although Plugwhen would have paused, or stood still in a planned window)."""
    t = _t(lang)
    W, H = 640, 250
    rows = []
    for i in range(count - 1, -1, -1):
        d = today - timedelta(days=i)
        v = (days or {}).get(d.isoformat())
        agree = ((v.get("charge_charging", 0) + v.get("pause_idle", 0)) / 3600) if v else 0.0
        differ = ((v.get("pause_charging", 0) + v.get("charge_idle", 0)) / 3600) if v else 0.0
        rows.append((d, agree, differ))
    if not any(a + b > 0.05 for _, a, b in rows):
        return _svg(W, 60, _text(10, 34, t["no_shadow"], size=14))
    top, ph = 40, 150
    vmax = max(4.0, max(a + b for _, a, b in rows))
    vmax = float(int(vmax) + 1)
    bw = (W - 60) / count
    body = [_text(10, 20, t["shadow_title"], weight="700", size=13)]
    for k in range(0, int(vmax) + 1, max(1, int(vmax) // 4)):
        y = top + ph - ph * k / vmax
        body.append(f"<line x1='36' y1='{y:.1f}' x2='{W - 10}' y2='{y:.1f}' stroke='{GREY}' stroke-opacity='0.2'/>")
        body.append(_text(30, y + 4, f"{k}", "end", size=10))
    for i, (d, agree, differ) in enumerate(rows):
        x = 40 + i * bw
        h1, h2 = ph * agree / vmax, ph * differ / vmax
        if agree > 0.02:
            body.append(f"<rect x='{x + 2:.1f}' y='{top + ph - h1:.1f}' width='{bw - 4:.1f}' height='{h1:.1f}' fill='{GREEN}'/>")
        if differ > 0.02:
            body.append(f"<rect x='{x + 2:.1f}' y='{top + ph - h1 - h2:.1f}' width='{bw - 4:.1f}' height='{h2:.1f}' fill='{RED}'/>")
        if d.weekday() == 0 or i == count - 1:
            body.append(_text(x + bw / 2, top + ph + 16, d.strftime("%d.%m."), "middle", size=10))
    ly = H - 14
    body.append(f"<rect x='40' y='{ly - 9}' width='10' height='10' fill='{GREEN}'/>" + _text(55, ly, t["agree"], size=11))
    body.append(f"<rect x='300' y='{ly - 9}' width='10' height='10' fill='{RED}'/>" + _text(315, ly, t["differ"], size=11))
    body.append(_text(W - 10, top - 8, t["hours"], "end", size=10))
    return _svg(W, H, "".join(body))


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
        label = t["wd"][tt.weekday()] if tt.hour == 0 else f"{tt.hour}"
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
    ls = _as_dt((plan or {}).get("latest_start"))
    if ls is not None and start <= ls < end and status in ("planned", "infeasible"):          # the latest start at full power
        xl = x(ls)
        body.append(f"<line x1='{xl:.1f}' y1='{top}' x2='{xl:.1f}' y2='{top + ph}' stroke='{RED}' stroke-width='1.5' stroke-dasharray='5 4'/>")
        body.append(_text(xl - 5, top + 14, f"{t['latest']} {t['wd'][ls.weekday()]} {ls:%H:%M}", "end", fill=RED, size=11))
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


def chart_habit(habit: dict[str, Any] | None, lang: str | None = None) -> str:
    """Stacked bars per weekday (kWh on an average day of that weekday): night at the bottom (blue), in between (grey), during the day
    on top (yellow)."""
    t = _t(lang)
    if not habit or habit.get("status") != "ok" or not habit.get("weekday"):
        return _msg(t["habit_few"])
    W, H, L, R, top, ph = 640, 290, 40, 16, 40, 170
    days = habit["weekday"]
    vmax = max(4.0, max(d["kwh_per_day"] for d in days))
    vmax = float(int(vmax) + 1)
    step = max(1, int(vmax) // 4)
    body = [_text(10, 20, t["habit_title"], weight="700", size=13)]
    for k in range(0, int(vmax) + 1, step):
        y = top + ph - ph * k / vmax
        body.append(f"<line x1='{L}' y1='{y:.1f}' x2='{W - R}' y2='{y:.1f}' stroke='{GREY}' stroke-opacity='0.2'/>")
        body.append(_text(L - 6, y + 4, f"{k}", "end", size=10))
    bw = (W - L - R) / 7
    for i, d in enumerate(days):
        x = L + i * bw
        base = top + ph
        for key, colour in (("night_kwh_per_day", BLUE), ("rest_kwh_per_day", GREY), ("day_kwh_per_day", SUN)):
            h = ph * d[key] / vmax
            if h > 0.5:
                base -= h
                body.append(f"<rect x='{x + 8:.1f}' y='{base:.1f}' width='{bw - 16:.1f}' height='{h:.1f}' fill='{colour}'/>")
        if d["kwh_per_day"] > 0:
            body.append(_text(x + bw / 2, base - 5, f"{d['kwh_per_day']:.1f}", "middle", size=11))
        body.append(_text(x + bw / 2, top + ph + 16, t["wd"][d["weekday"]], "middle"))
        body.append(_text(x + bw / 2, top + ph + 29, f"n={d['days']}", "middle", size=10))
    ly = H - 28
    for j, (key, colour) in enumerate((("habit_day", SUN), ("habit_night", BLUE), ("habit_rest", GREY))):
        x = L + j * 190
        body.append(f"<rect x='{x}' y='{ly - 9}' width='10' height='10' fill='{colour}'/>" + _text(x + 15, ly, t[key], size=11))
    foot = t["habit_foot"].format(n=habit.get("night_share_pct"), d=habit.get("day_share_pct"), w=habit.get("weekend_share_pct"))
    body.append(_text(L, H - 8, foot, size=11))
    return _svg(W, H, "".join(body))


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
    days = (horizon.get("days") or [])[:8]                      # the first eight departures fit the chart, the numbers cover more
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
    H = top + days * rh + 50
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
