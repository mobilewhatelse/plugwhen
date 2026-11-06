"""One-off: installation test for learn mode (kept for the record)."""
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "tests" / "install" / "itest.py"
s = p.read_text(encoding="utf-8")


def rep(a, b):
    global s
    assert s.count(a) == 1, a[:70]
    s = s.replace(a, b)


rep('log(len(ents) == 11, "entities of the vehicle exist"', 'log(len(ents) == 13, "entities of the vehicle exist"')

rep('''    log(bool(ok), "plugged in with a plan: ready for departure", state(rdid)["state"])
''', '''    log(bool(ok), "plugged in with a plan: ready for departure", state(rdid)["state"])

    # learn mode: default on, says what it would switch, switches nothing
    mode_s = find("select", "mode")
    would_s = find("sensor", "would_switch")
    log(bool(mode_s) and bool(would_s), "mode select and the sensor 'would switch' exist")
    if mode_s and would_s:
        mid, wid = mode_s["entity_id"], would_s["entity_id"]
        log(state(mid)["state"] == "learn", "the mode is learn by default", state(mid)["state"])
        ok = wait_for(lambda: state(wid)["state"] in ("charge", "pause"), 30)
        wa = state(wid)["attributes"]
        log(bool(ok) and wa.get("reason") in ("in_window", "waiting_for_window", "plan_done", "cannot_reach_target") and "summary" in wa,
            "plugged in with a plan: it says charge or pause with a reason and a summary", f"{state(wid)['state']} / {wa.get('reason')}")
''')

rep('''    log(bool(ok), "unplugged: readiness says plug in", state(rdid)["state"])
''', '''    log(bool(ok), "unplugged: readiness says plug in", state(rdid)["state"])
    if mode_s and would_s:
        ok = wait_for(lambda: state(wid)["state"] == "none" and state(wid)["attributes"].get("reason") == "not_plugged", 30)
        log(bool(ok), "unplugged: no decision (the wallbox keeps doing what it does)", f"{state(wid)['state']} / {state(wid)['attributes'].get('reason')}")
        svc("select", "select_option", {"entity_id": mid, "option": "off"})
        ok = wait_for(lambda: state(wid)["state"] == "off", 30)
        log(bool(ok), "mode off: the sensor says off", state(wid)["state"])
        svc("select", "select_option", {"entity_id": mid, "option": "learn"})
        ok = wait_for(lambda: state(wid)["state"] != "off", 30)
        log(bool(ok), "mode learn again: it decides again", state(wid)["state"])
''')

rep('''    # ---------- restart: settings are restored ----------
    svc("switch", "turn_off", {"entity_id": lid})
''', '''    # ---------- restart: settings are restored ----------
    svc("switch", "turn_off", {"entity_id": lid})
    if mode_s:
        svc("select", "select_option", {"entity_id": mid, "option": "off"})
''')

rep('''    log(state(lid)["state"] == "off", "learning switch state is restored (off)")
''', '''    log(state(lid)["state"] == "off", "learning switch state is restored (off)")
    if mode_s:
        ok = wait_for(lambda: (state(mid) or {}).get("state") == "off", 30)
        log(bool(ok), "the mode is restored after the restart (off, as chosen)", str((state(mid) or {}).get("state")))
''')
p.write_text(s, encoding="utf-8")
print("ok")
