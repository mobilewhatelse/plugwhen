"""One-off: weak sun that a wallbox cannot use is not counted, and the look-ahead text card never breaks (0.7.4, kept for the record).

Live 09.11.2026: the look-ahead recommended 2 kWh of pre-charging with no sun window (sun_from None): the sun of the next day never
reached 1 kW in a quarter hour. Such sun cannot be charged (a wallbox needs about 1.4 kW at least), so it must not count; and the card
broke on `None | as_datetime`.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "custom_components" / "plugwhen"


def edit(rel, pairs):
    p = ROOT / rel
    s = p.read_text(encoding="utf-8", newline="")
    crlf = "\r\n" in s
    s = s.replace("\r\n", "\n")
    for a, b in pairs:
        assert s.count(a) == 1, (rel, a[:80], s.count(a))
        s = s.replace(a, b)
    if crlf:
        s = s.replace("\n", "\r\n")
    p.write_text(s, encoding="utf-8", newline="")


edit("custom_components/plugwhen/horizon.py", [(
    '''        kw = min(max_kw, max(0.0, sun_kw.get(t, 0.0)))
        if frac > 0 and kw > 0:
            total += kw * QUARTER_H * frac
            if kw >= MIN_SUN_KW:
                first = first or t
                last = nxt
        t = nxt
    return total, first, last''', '''        kw = min(max_kw, max(0.0, sun_kw.get(t, 0.0)))
        if frac > 0 and kw >= MIN_SUN_KW:  # weaker sun cannot be charged (a wallbox needs more than that), so it does not count
            total += kw * QUARTER_H * frac
            first = first or t
            last = nxt
        t = nxt
    return total, first, last''')])
edit("custom_components/plugwhen/dashboard.py", [(
    '''        "{% for p in h.precharge %}{% set sf = p.sun_from | as_datetime | as_local %}{% set st = p.sun_to | as_datetime | as_local %}{% set fd = p.for_departure | as_datetime | as_local %}"''',
    '''        "{% for p in h.precharge if p.sun_from and p.sun_to and p.for_departure %}{% set sf = p.sun_from | as_datetime | as_local %}{% set st = p.sun_to | as_datetime | as_local %}{% set fd = p.for_departure | as_datetime | as_local %}"''')])
edit("tests/test_horizon.py", [(
    '''class HorizonTest(unittest.TestCase):''', '''class WeakSunTest(unittest.TestCase):
    def test_sun_below_one_kw_is_not_counted_and_never_a_pre_charge_without_window(self):
        r = plan(sun_kw=sun(kw=0.5))
        self.assertEqual(r["precharge"], [])
        self.assertEqual(r["saved_grid_kwh"], 0.0)
        for p in plan()["precharge"]:
            self.assertIsNotNone(p["sun_from"])
            self.assertIsNotNone(p["sun_to"])


class HorizonTest(unittest.TestCase):''')])
edit("CHANGELOG.md", [("# Changelog\n", """# Changelog

## 0.7.4 (unreleased) - weak sun

- Sun that never reaches 1 kW in a quarter hour is not counted in the look-ahead any more: a wallbox cannot charge with it. Before,
  a pre-charge could be recommended without a sun window, and the text card *The next departures* broke on it.
""")])
m = PKG / "manifest.json"
d = json.loads(m.read_text(encoding="utf-8"))
d["version"] = "0.7.4"
m.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("ok")
