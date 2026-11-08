"""One-off: the chart 'when do you charge' (kept for the record)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def edit(rel, pairs):
    p = ROOT / rel
    s = p.read_text(encoding="utf-8")
    for a, b in pairs:
        assert s.count(a) == 1, f"{rel}: {a[:90]}"
        s = s.replace(a, b)
    p.write_text(s, encoding="utf-8")


edit("tests/test_habit.py", [
    ('        self.assertEqual(by[0]["rest_kwh_per_day"], 2.0 + 0.0 if False else by[0]["rest_kwh_per_day"])\n', ''),
])

edit("custom_components/plugwhen/charts.py", [
    ("* `chart_plugs`: the last 14 days, when the car was plugged in (one strip per day, 0 to 24 h).\n",
     "* `chart_plugs`: the last 14 days, when the car was plugged in (one strip per day, 0 to 24 h).\n"
     "* `chart_habit`: when the car is charged, per weekday: energy during the day, at night and in between.\n"),
    ('        plugs_title="Angesteckt in den letzten 14 Tagen", no_plugs="Noch keine Steckzeiten mitgeschrieben",\n    ),',
     '        plugs_title="Angesteckt in den letzten 14 Tagen", no_plugs="Noch keine Steckzeiten mitgeschrieben",\n'
     '        habit_title="Wann laden Sie? kWh je Wochentag im Durchschnitt", habit_day="tagsüber (9–17 Uhr)", habit_night="nachts (20–7 Uhr)", habit_rest="sonst",\n'
     '        habit_few="Ladegewohnheit: noch zu wenig Daten (28 Tage nötig)", habit_foot="nachts {n} % · tagsüber {d} % · Wochenende {w} % der Energie",\n    ),'),
    ('        plugs_title="Plugged in over the last 14 days", no_plugs="No plug-in times recorded yet",\n    ),',
     '        plugs_title="Plugged in over the last 14 days", no_plugs="No plug-in times recorded yet",\n'
     '        habit_title="When do you charge? kWh per weekday on average", habit_day="during the day (9 to 17 h)", habit_night="at night (20 to 7 h)", habit_rest="otherwise",\n'
     '        habit_few="Charging habit: too little data yet (28 days needed)", habit_foot="night {n} % · day {d} % · weekend {w} % of the energy",\n    ),'),
])

s = (ROOT / "custom_components/plugwhen/charts.py").read_text(encoding="utf-8")
s += '''

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
'''
(ROOT / "custom_components/plugwhen/charts.py").write_text(s, encoding="utf-8")
print("ok")
