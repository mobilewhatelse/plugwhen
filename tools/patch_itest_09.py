"""One-off: the installation test renders every markdown card of the dashboard in a real Home Assistant (kept for the record)."""
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "tests" / "install" / "itest.py"
s = p.read_text(encoding="utf-8")
a = '''    log(s_d == 200 and "views" in (dash.get("config") or {}) and rdid in text and pid in text and "yaml" in dash,
        "the dashboard service builds the dashboard with this installation's entities", f"{s_d} {len(text)} chars")
'''
assert s.count(a) == 1
b = a + '''    cards_md = [c for v in (dash.get("config") or {}).get("views", []) for sec in v.get("sections", []) for c in sec.get("cards", [])
                if c.get("type") == "markdown"]
    bad = []
    for c in cards_md:
        sc, body = api("POST", "/api/template", {"template": c["content"]})
        if sc != 200 or "Error" in str(body)[:60] or "UndefinedError" in str(body):
            bad.append(f"{c['content'][:50]!r}: {str(body)[:120]}")
    log(len(cards_md) >= 12 and not bad, f"all {len(cards_md)} markdown cards of the dashboard render in Home Assistant", "; ".join(bad)[:300])
'''
s = s.replace(a, b)
p.write_text(s, encoding="utf-8")
print("ok")
