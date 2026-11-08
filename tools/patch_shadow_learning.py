"""One-off: the learn-mode chart says 'still learning, x of 7 days with a comparison' until it can say something (kept for the record).

User 08.11.2026: "ja bitte lernt noch anzeigen" (values only when they say something).
"""
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "custom_components" / "plugwhen"


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
    ('shadow_title="Plan gegen Wirklichkeit, Stunden je Tag", no_shadow="Noch keine Daten: der Vergleich füllt sich Tag für Tag",',
     'shadow_title="Plan gegen Wirklichkeit, Stunden je Tag", no_shadow="Noch keine Daten: der Vergleich füllt sich Tag für Tag",\n'
     '        shadow_learning="Lernt noch · {n} von {m} Tagen mit Vergleich",'),
    ('shadow_title="Plan against reality, hours per day", no_shadow="No data yet: the comparison fills up day by day",',
     'shadow_title="Plan against reality, hours per day", no_shadow="No data yet: the comparison fills up day by day",\n'
     '        shadow_learning="Still learning · {n} of {m} days with a comparison",'),
    ('ORANGE = "#f0883e"\n', 'ORANGE = "#f0883e"\nSHADOW_MIN_DAYS = 7              # days with a comparison before the learn-mode chart shows bars\n'),
    ('''    if not any(a + b > 0.05 for _, a, b in rows):
        return _svg(W, 60, _text(10, 34, t["no_shadow"], size=14))
''', '''    if not any(a + b > 0.05 for _, a, b in rows):
        return _svg(W, 60, _text(10, 34, t["no_shadow"], size=14))
    compared = sum(1 for _, a, b in rows if a + b > 0.05)
    if compared < SHADOW_MIN_DAYS:                                 # a value only when it says something
        return _svg(W, 60, _text(10, 34, t["shadow_learning"].format(n=compared, m=SHADOW_MIN_DAYS), size=14))
'''),
])
print("ok")
