"""One-off: installation test for the two charts (kept for the record)."""
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "tests" / "install" / "itest.py"
s = p.read_text(encoding="utf-8")


def rep(a, b):
    global s
    assert s.count(a) == 1, a[:70]
    s = s.replace(a, b)


rep('log(len(ents) == 13, "entities of the vehicle exist"', 'log(len(ents) == 14, "entities of the vehicle exist"')
rep('''        log(state(mid)["state"] == "learn", "the mode is learn by default", state(mid)["state"])
''', '''        log(state(mid)["state"] == "learn", "the mode is learn by default", state(mid)["state"])
        lc = find("sensor", "does_learning_help")
        log(bool(lc), "the sensor 'does learning help' exists")
        if lc:
            ok = wait_for(lambda: state(lc["entity_id"])["state"] in ("too_little_data", "learning_helps", "reserve_enough", "little"), 30)
            la = state(lc["entity_id"])["attributes"]
            log(bool(ok) and state(lc["entity_id"])["state"] == "too_little_data" and str(la.get("chart", "")).startswith("<svg"),
                "no history yet: too little data, and the chart says so (valid SVG)", f"{state(lc['entity_id'])['state']} / {str(la.get('chart'))[:40]}")
        wa0 = state(wid)["attributes"] if would_s else {}
        log(str(wa0.get("chart", "")).startswith("<svg"), "learn mode: the chart of plan against reality is delivered as SVG", str(wa0.get("chart"))[:40])
''')
p.write_text(s, encoding="utf-8")
print("ok")
