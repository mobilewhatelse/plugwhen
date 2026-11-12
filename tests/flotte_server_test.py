"""Plugwhen against the real service (energie-cloud/autodaten) on a local Apache with PHP in Docker:

    python tests/flotte_server_test.py

Builds the trip days with flotte.py exactly as Plugwhen does, sends them, fetches the models and uses them. Needs Docker and
the repository energie-cloud next to this one. Nothing goes to the internet. Not part of the unit tests (needs Docker).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components" / "plugwhen"))

import flotte  # noqa: E402
from learning import DayRecord  # noqa: E402

SRC = ROOT.parent / "energie-cloud" / "autodaten"
PORT_ON, PORT_OFF = 18491, 18492
FAILS = 0


def log(ok: bool, name: str, detail: str = "") -> None:
    global FAILS
    FAILS += 0 if ok else 1
    print(("ok   " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))


def call(port: int, path: str, data: dict | None = None, head: dict | None = None) -> tuple[int, object]:
    req = urllib.request.Request(f"http://localhost:{port}/autodaten/v1/{path}", data=json.dumps(data).encode() if data else None,
                                 headers={"Content-Type": "application/json"} | (head or {}), method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            s, t = r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        s, t = e.code, e.read().decode()
    try:
        return s, json.loads(t)
    except ValueError:
        return s, t


def start(name: str, port: int, work: Path, on: bool) -> None:
    subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    cmd = ["docker", "run", "-d", "--name", name, "-p", f"{port}:80", "-v", f"{work}:/var/www/html/autodaten"]
    subprocess.run(cmd + (["-e", "AUTODATEN_AKTIV=1"] if on else []) + ["php:8.3-apache"], check=True, capture_output=True)
    subprocess.run(["docker", "exec", name, "sh", "-c", "mkdir -p /var/www/html/autodaten/daten && chown -R www-data /var/www/html/autodaten/daten"],
                   capture_output=True)
    for _ in range(60):
        try:
            urllib.request.urlopen(f"http://localhost:{port}/autodaten/v1/modelle.php", timeout=2)
            return
        except urllib.error.HTTPError:
            return
        except Exception:  # noqa: BLE001
            time.sleep(0.5)


def records(n: int, base: float) -> list[DayRecord]:
    """A car over `n` days: 40-80 km, colder days cost more."""
    out = []
    for i in range(n):
        t = 15.0 - (i % 25)                       # 15 .. -9 deg C
        out.append(DayRecord(date(2026, 1, 1) + timedelta(days=i), km=40.0 + (i * 7) % 40, temp_c=t,
                             consumption=round(base + 0.004 * (15.0 - t), 3)))
    return out


def main() -> int:
    if not SRC.exists():
        print("energie-cloud not next to this repository: skipped")
        return 0
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "autodaten"
        shutil.copytree(SRC, work, ignore=shutil.ignore_patterns("daten"))
        try:
            start("pw-flotte-on", PORT_ON, work, True)
            start("pw-flotte-off", PORT_OFF, work, False)
            model = flotte.model_name("Volkswagen", "e-Golf")
            today = date(2026, 6, 1)

            s, a = call(PORT_OFF, "senden.php", flotte.payload(flotte.trip_days(records(30, 0.15), model, 35.8, None, today)[0], True))
            log(s == 503, "Service off (as delivered): 503, Plugwhen just tries again tomorrow", str(s))

            key = None
            for car in range(6):   # six cars of the same model: from five the model is delivered
                days, last = flotte.trip_days(records(120, 0.15 + car * 0.005), model, 35.8, None, today)
                s, a = call(PORT_ON, "senden.php", flotte.payload(days, True))
                ok = s == 200 and isinstance(a, dict) and a.get("angenommen") == len(days)
                log(ok, f"Car {car + 1}: {len(days)} trip days accepted", f"{s} {a}")
                key = a.get("schluessel") if isinstance(a, dict) else key
            days, last2 = flotte.trip_days(records(120, 0.15), model, 35.8, last, today)
            log(days == [], "The next day: nothing sent twice")

            s, m = call(PORT_ON, "modelle.php", head={"X-Schluessel": key or ""})
            log(s == 200 and isinstance(m, dict) and m.get("schema") == 1, "Models fetched with the key", f"{s} {str(m)[:200]}")
            entry, src = flotte.entry_for(m if isinstance(m, dict) else None, model)
            log(src == "fleet_model" and entry and entry.get("autos") == 6, "Own model found (6 cars)", f"{src} {entry}")
            cold, mild = flotte.consumption(entry, -8.0), flotte.consumption(entry, 12.0)
            log(cold is not None and mild is not None and cold > mild and 0.14 < mild < 0.25, "Colder costs more, plausible values",
                f"{cold} {mild}")
            e2, s2 = flotte.entry_for(m if isinstance(m, dict) else None, "tesla model y")
            log(s2 == "fleet_all", "Another model: all cars together", str(s2))

            s, _ = call(PORT_ON, "modelle.php", head={"X-Schluessel": "0" * 48})
            log(s == 403, "Unknown key: 403 (Plugwhen forgets it and gets a new one with the next days)", str(s))
            raw = (work / "daten" / "fahrtage.jsonl").read_text(encoding="utf-8") if (work / "daten" / "fahrtage.jsonl").exists() else ""
            log("2026" not in raw and key not in raw, "Stored without date and without key")
        finally:
            subprocess.run(["docker", "rm", "-f", "pw-flotte-on", "pw-flotte-off"], capture_output=True)
    print(f"\n{'ALL OK' if not FAILS else f'{FAILS} FAILED'}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
