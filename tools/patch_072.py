"""One-off: version 0.7.2 (learn-mode chart says 'still learning' until it can say something; kept for the record)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "CHANGELOG.md"
s = p.read_text(encoding="utf-8")
crlf = "\r\n" in s
s = s.replace("\r\n", "\n")
a = "# Changelog\n"
assert s.count(a) == 1
s = s.replace(a, """# Changelog

## 0.7.2 (unreleased) - learn mode says when it is still learning

- The learn-mode chart *Plan against reality* shows **"Still learning · x of 7 days with a comparison"** instead of bars until seven days
  could be compared (days on which Plugwhen decided to charge or pause). A value only when it says something.
""", 1)
if crlf:
    s = s.replace("\n", "\r\n")
p.write_text(s, encoding="utf-8", newline="")
m = ROOT / "custom_components" / "plugwhen" / "manifest.json"
d = json.loads(m.read_text(encoding="utf-8"))
d["version"] = "0.7.2"
m.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("ok")
