"""One-off: corrects the expectations of the warning checks in the installation test (kept for the record)."""
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "tests" / "install" / "itest.py"
s = p.read_text(encoding="utf-8")


def rep(a, b):
    global s
    assert s.count(a) == 1, a[:70]
    s = s.replace(a, b)


rep('''    n0 = num("counter.meldungen") or 0
    svc("input_boolean", "turn_off", {"entity_id": "input_boolean.auto_angesteckt"})
    ok = wait_for(lambda: state(rdid)["state"] == "plug_in", 30)
    log(bool(ok), "unplugged: readiness says plug in", state(rdid)["state"])
    ok = wait_for(lambda: (num("counter.meldungen") or 0) == n0 + 1, 30)
    log(bool(ok), "the warning was sent once", f"counter {num('counter.meldungen')}")
    text = state("input_text.meldung")["state"].lower()
    log("anstecken" in text or "plug in" in text, "text of the warning", text[:90])
    svc("number", "set_value", {"entity_id": resid, "value": 150})
    time.sleep(6)
    log((num("counter.meldungen") or 0) == n0 + 1, "the same warning is not sent twice", f"counter {num('counter.meldungen')}")
''', '''    # the first plug-in warning went out earlier, while the battery was low and the car not plugged in
    log((num("counter.meldungen") or 0) == 1, "the warning went out once while the car was unplugged and short", f"counter {num('counter.meldungen')}")
    svc("input_boolean", "turn_off", {"entity_id": "input_boolean.auto_angesteckt"})
    ok = wait_for(lambda: state(rdid)["state"] == "plug_in", 30)
    log(bool(ok), "unplugged: readiness says plug in", state(rdid)["state"])
    text = state("input_text.meldung")["state"].lower()
    log("anstecken" in text or "plug in" in text, "text of the warning", text[:90])
    svc("number", "set_value", {"entity_id": resid, "value": 150})
    time.sleep(6)
    log((num("counter.meldungen") or 0) == 1, "the same warning is not sent twice (same day, same kind)", f"counter {num('counter.meldungen')}")
''')
rep('''    ok = wait_for(lambda: (num("counter.meldungen") or 0) == n0 + 2, 30)
    log(bool(ok), "a worse warning is a new one", f"counter {num('counter.meldungen')}")''',
    '''    ok = wait_for(lambda: (num("counter.meldungen") or 0) == 2, 30)
    log(bool(ok), "a worse warning is a new one", f"counter {num('counter.meldungen')}")''')
rep('''    log((num("counter.meldungen") or 0) == n0 + 2 and state(rdid)["state"] == "too_late", "warning switched off: nothing sent, sensor still shows it")''',
    '''    log((num("counter.meldungen") or 0) == 2 and state(rdid)["state"] == "too_late", "warning switched off: nothing sent, sensor still shows it",
        f"counter {num('counter.meldungen')}, {state(rdid)['state']}")''')
rep('''    log(bool(ok) and num(resid) == 150.0, "reserve is restored", str(num(resid)))''',
    '''    log(bool(ok) and num(resid) == 100.0, "reserve is restored (the value set last)", str(num(resid)))''')
p.write_text(s, encoding="utf-8")
print("ok")
