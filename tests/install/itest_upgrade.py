"""Upgrade test: a test HA set up with an older release (by default each of the last three releases in turn), then the working
copy put in its place and HA restarted. Checks that the car, its settings and entity ids survive, that the new entities come
(bug report button), and that nothing errors in the log.

The code is replaced completely by an update, the stored data (settings, cars, entity ids, learned values) is not: the new code
has to take what any of the older releases stored.

Run:  python tests/install/itest_upgrade.py [old tag ...]   (Docker needed; uses port 18129, container pw-upgrade)
Rule: before every release the update from each of the last three releases has to pass."""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))
import itest as it  # noqa: E402

NAME, PORT, RUN = "pw-upgrade", 18129, HERE / "run_upgrade"
it.BASE = f"http://localhost:{PORT}"
it.CONTAINER = NAME
COMP = "custom_components/plugwhen"
results: list[tuple[bool, str, str]] = []


def log(ok: bool, what: str, detail: str = "") -> None:
    results.append((bool(ok), what, detail))
    print(("PASS  " if ok else "FAIL  ") + what + (f"  [{detail}]" if detail else ""), flush=True)


def docker(*args: str) -> str:
    return subprocess.run(["docker", *args], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout


def put_component(ref: str | None) -> None:
    target = RUN / COMP
    if target.exists():
        shutil.rmtree(target)
    if ref is None:
        shutil.copytree(REPO / COMP, target, ignore=shutil.ignore_patterns("__pycache__"))
        return
    data = subprocess.run(["git", "-C", str(REPO), "archive", "--format=tar", ref, COMP], capture_output=True, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        tar.extractall(RUN, filter="data")


def manifest_version() -> str:
    return json.loads((RUN / COMP / "manifest.json").read_text(encoding="utf-8"))["version"]


def last_releases(n: int = 3) -> list[str]:
    tags = subprocess.run(["git", "-C", str(REPO), "tag", "--sort=-v:refname", "--list", "v*"], capture_output=True, text=True).stdout.split()
    current = "v" + json.loads((REPO / COMP / "manifest.json").read_text(encoding="utf-8"))["version"]
    return [t for t in tags if t != current][:n]


def entities() -> list[str]:
    """The entities of Plugwhen and of the car (their ids hold 'plugwhen' or the car's name)."""
    return sorted(e["entity_id"] for e in it.states_like("") if "plugwhen" in e["entity_id"] or "testauto" in e["entity_id"])


def upgrade_from(old: str) -> None:
    docker("rm", "-f", NAME)
    if RUN.exists():
        shutil.rmtree(RUN)
    shutil.copytree(HERE / "config", RUN)
    (RUN / "custom_components").mkdir(exist_ok=True)
    put_component(old)
    old_version = manifest_version()
    # the test instance must never reach the real server (feedback, statistics)
    docker("run", "-d", "--name", NAME, "--add-host", "www.aiwhatelse.eu:127.0.0.1", "--add-host", "aiwhatelse.eu:127.0.0.1",
           "-p", f"{PORT}:8123", "-v", f"{RUN}:/config", "-e", "TZ=Europe/Vienna", "ghcr.io/home-assistant/home-assistant:stable")
    log(it.wait_ready(), f"old version {old_version} ({old}) starts")
    ok, err = it.onboard()
    log(ok, "onboarding", err)
    it.wait_for(lambda: (it.state("sensor.auto_ladestand") or {}).get("state") not in (None, "unknown", "unavailable"), 120)
    entry, err = it.flow_finish("/api/config/config_entries/flow", {"handler": "plugwhen", "show_advanced_options": False}, {})
    log(entry is not None, "old version: integration set up", str(err or ""))
    entry_id = it.api("GET", "/api/config/config_entries/entry?domain=plugwhen")[1][0]["entry_id"]
    car = {"name": "Testauto", "odometer_entity": "sensor.auto_kilometerstand", "soc_entity": "sensor.auto_ladestand",
           "capacity_kwh": 60, "reserve_km": 100, "consumption_kwh_100": 20, "plugged_entity": "binary_sensor.auto_stecker",
           "wallbox_energy_entity": "sensor.wallbox_zaehler", "departure_entity": "input_datetime.abfahrt",
           "charge_kw_max": 11, "charge_kw_min": 1.4}
    res, err = it.flow_finish("/api/config/config_entries/subentries/flow", {"handler": [entry_id, "vehicle"]}, car)
    log(res is not None, "old version: car added", str(err or ""))
    time.sleep(15)
    found = it.find("number", "reserve")
    reserve = found["entity_id"] if found else None
    if reserve:
        it.svc("number", "set_value", {"entity_id": reserve, "value": 80})
        time.sleep(5)
    log(reserve is not None and it.num(reserve) == 80, "old version: reserve changed to 80 km", str(reserve))
    before = entities()
    log(len(before) > 10, "old version: entities there", str(len(before)))

    # ---------- update: stop, new files, start (as the Marketplace does it) ----------
    docker("stop", "-t", "120", NAME)
    put_component(None)
    new_version = manifest_version()
    docker("start", NAME)
    log(it.wait_ready(), f"after the update to {new_version} HA starts")
    it.wait_for(lambda: reserve and (it.state(reserve) or {}).get("state") not in (None, "unknown", "unavailable"), 120)
    time.sleep(10)
    entry = it.api("GET", "/api/config/config_entries/entry?domain=plugwhen")[1][0]
    log(entry["state"] == "loaded", "Plugwhen loads after the update", entry["state"])
    log(reserve is not None and it.num(reserve) == 80, "the reserve stays at 80 km", str(it.num(reserve) if reserve else None))
    after = entities()
    missing = sorted(set(before) - set(after))
    log(not missing, "no entity lost (same ids, so cards and automations keep working)", ", ".join(missing))
    unavailable = [e for e in after if (it.state(e) or {}).get("state") == "unavailable"]
    log(not unavailable, "no entity unavailable after the update", ", ".join(unavailable))
    rep = [e["entity_id"] for e in it.states_like("plugwhen") if e["entity_id"].startswith("button.") and "bug_report" in e["entity_id"]]
    log(len(rep) == 1, "the new button 'Send bug report' is there", str(rep))
    logs = subprocess.run(["docker", "logs", NAME], capture_output=True, text=True, encoding="utf-8", errors="replace")
    bad = [line for line in (logs.stdout + logs.stderr).splitlines()
           if "plugwhen" in line and ("ERROR" in line or "Error importing" in line or "Traceback" in line)]
    log(not bad, f"{old}: no errors of Plugwhen in the log", bad[0][:200] if bad else "")
    docker("rm", "-f", NAME)


def main() -> int:
    olds = sys.argv[1:] or last_releases()
    for old in olds:
        print(f"\n===== update from {old} =====", flush=True)
        try:
            upgrade_from(old)
        except Exception as exc:  # one broken run must not hide the others
            log(False, f"{old}: run broke off", f"{type(exc).__name__}: {exc}")
    passed = sum(1 for ok, _, _ in results if ok)
    print(f"\nERGEBNIS: {passed} von {len(results)} Pruefungen bestanden (Update von {', '.join(olds)})", flush=True)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
