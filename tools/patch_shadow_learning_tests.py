"""One-off: tests for the 'still learning' message of the learn-mode chart (kept for the record)."""
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "tests" / "test_charts.py"
s = p.read_text(encoding="utf-8")
crlf = "\r\n" in s
s = s.replace("\r\n", "\n")
a = '''    def test_shadow_chart_shows_agreement_and_difference(self):
        days = {(TODAY - timedelta(days=1)).isoformat(): {"charge_charging": 7200, "pause_idle": 3600, "pause_charging": 3600, "charge_idle": 0},
                TODAY.isoformat(): {"charge_charging": 0, "pause_idle": 1800, "pause_charging": 0, "charge_idle": 1800}}
        svg = chart_shadow(days, TODAY, "de")
'''
b = '''    def test_shadow_chart_with_few_days_says_still_learning_and_counts(self):
        days = {(TODAY - timedelta(days=1)).isoformat(): {"charge_charging": 7200, "pause_idle": 3600, "pause_charging": 3600, "charge_idle": 0},
                TODAY.isoformat(): {"charge_charging": 0, "pause_idle": 1800, "pause_charging": 0, "charge_idle": 1800}}
        for lang, text in (("de", "Lernt noch · 2 von 7 Tagen"), ("en", "Still learning · 2 of 7 days")):
            svg = chart_shadow(days, TODAY, lang)
            parse(svg)
            self.assertIn(text, svg)
            self.assertNotIn("#2fbf71", svg)                          # no bars until it can say something

    def test_shadow_chart_shows_agreement_and_difference(self):
        days = {(TODAY - timedelta(days=i)).isoformat(): {"charge_charging": 7200, "pause_idle": 3600, "pause_charging": 3600 * (i % 2),
                                                         "charge_idle": 1800 * (i % 3)} for i in range(1, 9)}
        svg = chart_shadow(days, TODAY, "de")
'''
assert s.count(a) == 1
s = s.replace(a, b)
if crlf:
    s = s.replace("\n", "\r\n")
p.write_text(s, encoding="utf-8", newline="")
print("ok")
