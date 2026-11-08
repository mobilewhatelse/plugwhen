"""One-off: shorter tile names and state texts so nothing is cut off on a phone (kept for the record).

User 08.11.2026: tile 'Potenzial durch verteiltes Laden' and the learning tile are cut off in the mobile view.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def edit(rel, pairs):
    p = ROOT / rel
    s = p.read_text(encoding="utf-8")
    crlf = "\r\n" in s
    s = s.replace("\r\n", "\n")
    for a, b in pairs:
        assert s.count(a) == 1, (rel, a[:70])
        s = s.replace(a, b)
    if crlf:
        s = s.replace("\n", "\r\n")
    p.write_text(s, encoding="utf-8", newline="")


edit("custom_components/plugwhen/dashboard.py", [
    ('pot="Potenzial durch verteiltes Laden"', 'pot="Potenzial"'),
    ('pot="Potential of spreading the charging"', 'pot="Potential"'),
    ('lc_tile="Lernen: lohnt es sich?"', 'lc_tile="Nutzt das Lernen?"'),
    ('lc_tile="Does learning help?"', 'lc_tile="Learning useful?"'),
])
edit("tools/gen_strings.py", [
    ('p_setting="Wallbox setting is enough"', 'p_setting="Setting is enough"'),
    ('lc_dep="Learning helps for the departure"', 'lc_dep="Helps with departure"'),
    ('p_setting="Wallbox-Einstellung reicht"', 'p_setting="Einstellung reicht"'),
    ('lc_dep="Lernen hilft bei der Abfahrt"', 'lc_dep="Hilft bei Abfahrt"'),
])
print("ok")
