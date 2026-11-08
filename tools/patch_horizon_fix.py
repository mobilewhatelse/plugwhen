"""One-off: pre-charging respects what earlier pre-charging left in the battery; 'latest start' per departure (kept for the record)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def edit(rel, pairs):
    p = ROOT / rel
    s = p.read_text(encoding="utf-8")
    for a, b in pairs:
        assert s.count(a) == 1, f"{rel}: {a[:90]}"
        s = s.replace(a, b)
    p.write_text(s, encoding="utf-8")


edit("custom_components/plugwhen/horizon.py", [
    ("""    for i, ri in enumerate(rows):
        for j in range(i + 1, len(rows)):
            if ri["spare"] < TINY_KWH:
                break
            rj = rows[j]
            if rj["grid"] < TINY_KWH:
                continue
            room_batt = cap - (ri["soc_end"] + ri["extra"])""",
     """    for i, ri in enumerate(rows):
        # what earlier pre-charging still holds in the battery at the end of this window (the part that has not covered a deficit yet)
        carried = sum(rows[k]["extra"] for k in range(i)) - sum(rows[j]["pre_in"] * eff for j in range(i + 1))
        carried = max(0.0, carried)
        for j in range(i + 1, len(rows)):
            if ri["spare"] < TINY_KWH:
                break
            rj = rows[j]
            if rj["grid"] < TINY_KWH:
                continue
            room_batt = cap - (ri["soc_end"] + carried + ri["extra"])"""),
    ("""            "departure": iso(r["trip"].departure), "window_start": iso(r["home_from"]), "need_kwh": round(r["need"], 1),""",
     """            "departure": iso(r["trip"].departure), "window_start": iso(r["home_from"]), "need_kwh": round(r["need"], 1),
            "latest_start": iso(r["trip"].departure - timedelta(hours=r["need"] / max_kw)) if r["need"] >= TINY_KWH else None,"""),
    ("It recommends only; nothing is switched.", "It recommends only; nothing is switched. For every departure with a need it also says the **latest start**:\nthe time by which charging at full power must begin to be ready (`latest_start`)."),
])

edit("tests/test_horizon.py", [
    ("""        tight = plan(cap_share=0.55)                                                # 33 kWh: only 3 kWh above the 30 now
        self.assertLess(tight["saved_grid_kwh"], loose["saved_grid_kwh"])
        for p in tight["precharge"]:
            self.assertLessEqual(p["kwh"], 3.0 / 0.9 + 0.5)""",
     """        tight = plan(cap_share=0.55)                                                # 33 kWh: 3 kWh above the 30 now
        self.assertLess(tight["saved_grid_kwh"], loose["saved_grid_kwh"])
        # Saturday may add 3 kWh to the battery, Sunday (25.6 kWh without it, 3 kWh from Saturday still in) 4.4 kWh: 7.4 kWh = 8.2 from the wallbox
        self.assertLessEqual(sum(p["kwh"] for p in tight["precharge"]), 8.3)
        self.assertGreaterEqual(sum(p["kwh"] for p in tight["precharge"]), 7.0)"""),
    ("""    def test_nothing_needed(self):""", """    def test_latest_start_is_the_departure_minus_the_time_at_full_power(self):
        r = plan(sun_kw=None)
        by = {d["departure"]: d for d in r["days"]}
        tue = by[at(3, 7).isoformat()]
        expected = at(3, 7) - timedelta(hours=tue["need_kwh"] / 11.0)
        self.assertEqual(datetime.fromisoformat(tue["latest_start"]).replace(microsecond=0), expected.replace(microsecond=0))
        self.assertIsNone(by[at(0, 13).isoformat()]["latest_start"])                  # nothing needed: no latest start

    def test_nothing_needed(self):"""),
])
print("ok")
