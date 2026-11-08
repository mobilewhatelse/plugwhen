"""One-off: look as far ahead as possible: 'with normal behaviour you have to charge by ...' (kept for the record).

User 08.11.2026: "calculate: with normal behaviour you must charge by Wednesday at the latest, as far into the future as possible".
The look-ahead now covers up to fourteen days and ten departures and states until when the charge lasts and the first charging that
is needed (day, latest start at the preferred power and at full power).
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


edit(PKG / "horizon.py", [
    ("""    with_pre = sum(max(0.0, r["grid"]) for r in rows)""",
     """    # with normal behaviour: until when does the charge last, and what is the first charging that is needed (whatever the sun does)
    first = next((i for i, r in enumerate(rows) if r["need"] >= TINY_KWH), None)
    result["trips_looked_at"] = len(rows)
    result["last_departure"] = iso(rows[-1]["trip"].departure)
    if first is None:
        result["lasts_until"] = iso(rows[-1]["trip"].departure)         # no charging needed within the whole look-ahead
        result["first_need"] = None
    else:
        r0 = rows[first]
        result["lasts_until"] = iso(rows[first - 1]["trip"].departure) if first > 0 else None
        result["first_need"] = {
            "departure": iso(r0["trip"].departure), "window_start": iso(r0["home_from"]), "need_kwh": round(r0["need"], 1),
            "latest_start": iso(r0["trip"].departure - timedelta(hours=r0["need"] / max_kw)),
            "latest_start_pref": iso(r0["trip"].departure - timedelta(hours=r0["need"] / min(max_kw, pref_kw))) if pref_kw else None,
            "covered_by_sun": r0["grid"] < TINY_KWH,
        }
    with_pre = sum(max(0.0, r["grid"]) for r in rows)"""),
])

edit(PKG / "coordinator.py", [
    ("HORIZON_DAYS = 5              # days looked at for the look-ahead\nHORIZON_TRIPS = 4             # departures in the look-ahead\n",
     "HORIZON_DAYS = 14             # days looked at for the look-ahead (as far as possible: with normal behaviour, when is charging needed?)\nHORIZON_TRIPS = 10            # departures in the look-ahead\n"),
])

edit(PKG / "charts.py", [
    ("""    days = horizon.get("days") or []
    if not days:
        return _msg(t["hz_trips"])
    W, L, R, top, ph = 640, 40, 16, 40, 150""",
     """    days = (horizon.get("days") or [])[:8]                      # the first eight departures fit the chart, the numbers cover more
    if not days:
        return _msg(t["hz_trips"])
    W, L, R, top, ph = 640, 40, 16, 40, 150"""),
])

edit(PKG / "dashboard.py", [
    ('        hz_h="Die nächsten Abfahrten", hz_next="Nächstes nötiges Laden",',
     '        hz_covered="Bei normalem Verhalten reicht der Ladestand bis", hz_must="Danach muss geladen werden: spätestens ab", hz_all="Bei normalem Verhalten reicht der Ladestand für alle Abfahrten der nächsten", hz_days="Tage",\n'
     '        hz_sun_ok="die Sonne kann es decken", hz_forecast="Die Sonnenprognose reicht nur so weit, wie Ihr Anbieter sie liefert.",\n'
     '        hz_h="Die nächsten Abfahrten", hz_next="Nächstes nötiges Laden",'),
    ('        hz_h="The next departures", hz_next="Next charging needed",',
     '        hz_covered="With normal behaviour the charge lasts until", hz_must="After that charging is needed: latest start", hz_all="With normal behaviour the charge is enough for all departures of the next", hz_days="days",\n'
     '        hz_sun_ok="the sun can cover it", hz_forecast="The solar forecast only reaches as far as your provider delivers it.",\n'
     '        hz_h="The next departures", hz_next="Next charging needed",'),
    ('''        "{% set ns = namespace(first=none) %}"
        "{% for d in h.days %}{% if ns.first is none and d.grid_kwh > 0 %}{% set ns.first = d %}{% endif %}{% endfor %}"
        "{% if ns.first %}{% set ws = ns.first.window_start | as_datetime | as_local %}{% set dp = ns.first.departure | as_datetime | as_local %}"
        "**@NEXT@:** {{ wd[ws.weekday()] }} {{ ws.strftime('%H:%M') }} (@FOR@ {{ wd[dp.weekday()] }} {{ dp.strftime('%H:%M') }}): {{ ns.first.grid_kwh }} kWh"
        "{% if ns.first.latest_start_pref %}{% set ls = ns.first.latest_start_pref | as_datetime | as_local %}"
        ", @LATEST@ {{ wd[ls.weekday()] }} {{ ls.strftime('%H:%M') }} @AT@ {{ a.pref_kw }} kW{% endif %}{% endif %}"''',
     '''        "{% set fn = h.first_need %}"
        "{% if fn %}"
        "{% if h.lasts_until %}{% set lu = h.lasts_until | as_datetime | as_local %}**@COVERED@** {{ wd[lu.weekday()] }} {{ lu.strftime('%H:%M') }}. {% endif %}"
        "{% set dp = fn.departure | as_datetime | as_local %}{% set ls = (fn.latest_start_pref or fn.latest_start) | as_datetime | as_local %}"
        "**@MUST@** {{ wd[ls.weekday()] }} {{ ls.strftime('%H:%M') }}"
        "{% if fn.latest_start_pref %} @AT@ {{ a.pref_kw }} kW{% endif %} (@FOR@ {{ wd[dp.weekday()] }} {{ dp.strftime('%H:%M') }}: {{ fn.need_kwh }} kWh"
        "{% if fn.covered_by_sun %}, @SUNOK@{% endif %})"
        "{% else %}@ALL@ {{ h.trips_looked_at }} @DAYS@."
        "{% endif %}"'''),
    ('for key, text in (("@NEXT@", t["hz_next"]),', 'for key, text in (("@COVERED@", t["hz_covered"]), ("@MUST@", t["hz_must"]), ("@ALL@", t["hz_all"]), ("@DAYS@", t["hz_days"]), ("@SUNOK@", t["hz_sun_ok"]), ("@NEXT@", t["hz_next"]),'),
])
print("ok")
