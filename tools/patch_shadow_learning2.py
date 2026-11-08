"""One-off: the learn-mode chart says 'still learning, 0 of 7 days' also with no comparison yet (kept for the record)."""
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


edit("custom_components/plugwhen/charts.py", [(
    '''    if not any(a + b > 0.05 for _, a, b in rows):
        return _svg(W, 60, _text(10, 34, t["no_shadow"], size=14))
    compared = sum(1 for _, a, b in rows if a + b > 0.05)
''', '''    compared = sum(1 for _, a, b in rows if a + b > 0.05)
''')])
edit("tests/test_charts.py", [(
    '''            self.assertIn("No data yet", svg)''', '''            self.assertIn("Still learning · 0 of 7 days", svg)''')])
print("ok")
