"""One-off: installation test, documentation, changelog and version for the sun windows (0.7.1, kept for the record)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def edit(rel, pairs):
    p = ROOT / rel
    s = p.read_text(encoding="utf-8")
    crlf = "\r\n" in s
    s = s.replace("\r\n", "\n")
    for a, b in pairs:
        assert s.count(a) == 1, f"{rel}: {a[:80]}"
        s = s.replace(a, b)
    if crlf:
        s = s.replace("\n", "\r\n")
    p.write_text(s, encoding="utf-8", newline="")


edit("tests/install/itest.py", [(
    '''            "the charge plan carries the look-ahead and its chart (valid SVG), also without a solar plant", f"{(pa_h.get('horizon') or {}).get('status')} / {str(pa_h.get('horizon_chart'))[:30]}")
''',
    '''            "the charge plan carries the look-ahead and its chart (valid SVG), also without a solar plant", f"{(pa_h.get('horizon') or {}).get('status')} / {str(pa_h.get('horizon_chart'))[:30]}")
        log(str(pa_h.get("sun_chart", "")).startswith("<svg") and "sun_windows" in (pa_h.get("horizon") or {}),
            "the charge plan carries the sun windows and their chart (valid SVG), also without a solar plant", f"{len((pa_h.get('horizon') or {}).get('sun_windows') or [])} windows / {str(pa_h.get('sun_chart'))[:30]}")
''')])

EN = """- **Sun windows:** a strip chart for the next five days: grey where the car is expected at home (red tick = departure), yellow where the
  sun delivers power in that time, an **orange frame where plugging in pays** (it covers a need or replaces grid energy before a later
  departure). Below it: *Best: Sat 10:00-13:00, up to 12 kWh.* Sun without a need is shown without a frame. Without a solar forecast the
  chart says so; nothing else in Plugwhen needs a plant. A recommendation only, nothing is switched. The data is in the attribute
  `sun_windows` (and `best_sun_window`) of the look-ahead.
"""
DE = """- **Sonnenfenster:** eine Streifengrafik für die nächsten fünf Tage: grau, wo das Auto voraussichtlich zu Hause ist (roter Strich = Abfahrt), gelb, wo in
  dieser Zeit die Sonne Leistung liefert, ein **oranger Rahmen, wo sich das Anstecken lohnt** (es deckt einen Bedarf oder ersetzt Netzstrom vor einer
  späteren Abfahrt). Darunter: *Am sinnvollsten: Sa 10:00–13:00, bis zu 12 kWh.* Sonne ohne Bedarf wird ohne Rahmen gezeigt. Ohne Solarprognose sagt die
  Grafik das; sonst braucht Plugwhen keine Anlage. Nur eine Empfehlung, es wird nichts geschaltet. Die Daten stehen im Attribut `sun_windows` (und
  `best_sun_window`) der Vorausschau.
"""
edit("README.md", [("- **Without a solar plant** nothing is pre-charged;", EN + "- **Without a solar plant** nothing is pre-charged;")])
edit("docs/ANLEITUNG.md", [("- **Ohne Solaranlage** wird nichts vorgeladen;", DE + "- **Ohne Solaranlage** wird nichts vorgeladen;")])
edit("CHANGELOG.md", [("# Changelog\n", """# Changelog

## 0.7.1 (unreleased) - sun windows

- **Sun windows:** when does plugging in with the sun make sense? A strip chart for the next five days (car at home, sun available, orange
  frame where charging with the sun covers a need or replaces grid energy later) and the best window as a line below. Attributes
  `sun_windows` and `best_sun_window` in the look-ahead, attribute `sun_chart` at the charge plan; a card in the dashboard under *The next
  departures*. Works without a solar plant (the chart then says there is no forecast).
""")])
m = ROOT / "custom_components" / "plugwhen" / "manifest.json"
d = json.loads(m.read_text(encoding="utf-8"))
d["version"] = "0.7.1"
m.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("ok")
