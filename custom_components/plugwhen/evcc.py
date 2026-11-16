"""evcc as an optional source of Plugwhen (read only, through evcc's REST API; evcc may run anywhere, not only as an add-on).

Plugwhen still needs the car's own sensors in Home Assistant (odometer and state of charge): evcc usually asks the car only while it
is plugged in, so it cannot tell the kilometres per day. What evcc adds:

* adding a vehicle: name, capacity and the charging power of the loadpoint are filled in (`vehicle_from_evcc`);
* at run time: plugged in and charging, when no sensor for them is set (`live_vehicle`).

The address and password come from Plugwhen's own settings or, if empty there, from the quarter-hour peak guard (`connection`).
Pure Python except for the client, which only needs an object with aiohttp's `request` (so it can be tested with a fake).
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

TIMEOUT_S = 6.0
VOLTAGE = 230.0

# settings of the guard that hold evcc's address and password
GUARD_URL = "evcc_site_url"
GUARD_PASSWORD = "evcc_site_password"


class EvccError(Exception):
    """evcc could not be reached or answered with an error."""


class EvccAuthError(EvccError):
    """evcc wants a password (or the password was refused)."""


def normalize_url(url: str | None) -> str:
    u = (url or "").strip().rstrip("/")
    if u and "://" not in u:
        u = "http://" + u
    return u


def connection(own_url: str | None, own_password: str | None, guard_cfg: dict[str, Any] | None) -> tuple[str, str | None, str] | None:
    """(url, password, source) of evcc: Plugwhen's own setting wins, else the guard's, else None. `source` is "own" or "guard".
    The password belongs to its address: an own address never takes the guard's password."""
    if normalize_url(own_url):
        return normalize_url(own_url), (own_password or None), "own"
    g = guard_cfg or {}
    if normalize_url(g.get(GUARD_URL)):
        return normalize_url(g.get(GUARD_URL)), (g.get(GUARD_PASSWORD) or None), "guard"
    return None


def _num(v: Any) -> float | None:
    try:
        return float(v) if v is not None and v != "" else None
    except (TypeError, ValueError):
        return None


def parse_vehicles(state: dict[str, Any] | None) -> list[dict[str, Any]]:
    """evcc's vehicles: [{"key", "title", "capacity_kwh"}] sorted by title. `key` is evcc's name (e.g. "db:3" or "my_car")."""
    raw = (state or {}).get("vehicles")
    out = []
    if isinstance(raw, dict):
        for key, v in raw.items():
            if isinstance(v, dict):
                out.append({"key": str(key), "title": str(v.get("title") or key), "capacity_kwh": _num(v.get("capacity"))})
    return sorted(out, key=lambda x: (x["title"].lower(), x["key"]))


def _loadpoints(state: dict[str, Any] | None) -> list[dict[str, Any]]:
    lps = (state or {}).get("loadpoints")
    return [lp for lp in lps if isinstance(lp, dict)] if isinstance(lps, list) else []


def loadpoint_kw(lp: dict[str, Any] | None, voltage: float = VOLTAGE) -> tuple[float, float] | None:
    """(lowest, highest) charging power in kW of a loadpoint from its currents: the highest on three phases (one if the
    loadpoint is fixed to one phase), the lowest on one phase if it can switch, else on the configured phases."""
    if not lp:
        return None
    lo_a, hi_a = _num(lp.get("minCurrent")), _num(lp.get("maxCurrent"))
    if not lo_a or not hi_a or lo_a <= 0 or lo_a > hi_a:
        return None
    configured = int(_num(lp.get("phasesConfigured")) or 0)   # 0 = automatic, 1 or 3 = fixed
    hi_ph = 1 if configured == 1 else 3
    lo_ph = 1 if (lp.get("chargerPhases1p3p") or configured == 1) else 3
    return round(lo_a * voltage * lo_ph / 1000.0, 1), round(hi_a * voltage * hi_ph / 1000.0, 1)


def loadpoint_of(state: dict[str, Any] | None, key: str) -> dict[str, Any] | None:
    """The loadpoint evcc has assigned this vehicle to right now, or None."""
    for lp in _loadpoints(state):
        if str(lp.get("vehicleName") or "") == key:
            return lp
    return None


def vehicle_from_evcc(state: dict[str, Any] | None, key: str) -> dict[str, Any]:
    """Plugwhen vehicle settings for evcc vehicle `key`: name, capacity and, from its loadpoint (or the first one), the charging
    power. Only keys with a value; the evcc key itself is returned as `evcc_vehicle`."""
    v = next((x for x in parse_vehicles(state) if x["key"] == key), None)
    if v is None:
        return {}
    out: dict[str, Any] = {"evcc_vehicle": key, "name": v["title"]}
    if v["capacity_kwh"]:
        out["capacity_kwh"] = v["capacity_kwh"]
    lps = _loadpoints(state)
    kw = loadpoint_kw(loadpoint_of(state, key) or (lps[0] if lps else None))
    if kw is not None:
        out["charge_kw_min"], out["charge_kw_max"] = kw
    return out


def match_vehicle(state: dict[str, Any] | None, name: str | None, taken: set[str]) -> str | None:
    """The evcc key for a car: same title as `name` (case-insensitive) if there is one, else a vehicle evcc has at a loadpoint
    right now (in the order of the loadpoints), else the first vehicle not taken yet. None without evcc vehicles."""
    vehicles = [x for x in parse_vehicles(state) if x["key"] not in taken]
    if name:
        for x in vehicles:
            if x["title"].strip().lower() == name.strip().lower():
                return x["key"]
    keys = {x["key"] for x in vehicles}
    for lp in _loadpoints(state):   # the car at a loadpoint is the likely one (an e-bike or a guest car comes later)
        k = str(lp.get("vehicleName") or "")
        if k in keys:
            return k
    return vehicles[0]["key"] if vehicles else None


def note_loadpoint_mode(state: dict[str, Any] | None, number: int, mode: str) -> None:
    """Write the mode Plugwhen just set into the state read last. evcc is read every few minutes, Plugwhen acts more often:
    without this the next run sees the old mode, takes it for a change by the user and forgets what it has to give back."""
    lps = _loadpoints(state)
    if 1 <= number <= len(lps):
        lps[number - 1]["mode"] = mode


def loadpoint_index(state: dict[str, Any] | None, key: str) -> tuple[int, str | None] | None:
    """(number 1.., current mode) of the loadpoint evcc has assigned vehicle `key` to, or None."""
    for i, lp in enumerate(_loadpoints(state), 1):
        if str(lp.get("vehicleName") or "") == key:
            return i, lp.get("mode")
    return None


def live_vehicle(state: dict[str, Any] | None, key: str) -> dict[str, Any] | None:
    """Plugged in and charging of vehicle `key` from its loadpoint: {"plugged", "charging", "power_kw"}. None if evcc has not
    assigned the vehicle to a loadpoint (then evcc does not know whether this car is plugged in)."""
    lp = loadpoint_of(state, key)
    if lp is None:
        return None
    p = _num(lp.get("chargePower"))
    return {"plugged": bool(lp.get("connected")), "charging": bool(lp.get("charging")),
            "power_kw": round(p / 1000.0, 2) if p is not None else None}


LOCAL_URLS = ("http://localhost:7070",)   # evcc on the same machine as Home Assistant (add-on, or Docker with host network)
PROBE_TIMEOUT_S = 2.0


class EvccClient:
    """Reads evcc's state; writes a vehicle's one-time plan only when the user switched that on. With a password it logs in itself."""

    def __init__(self, session: Any, url: str, password: str | None = None, timeout: float = TIMEOUT_S) -> None:
        self._session = session
        self._base = normalize_url(url)
        self._password = password or ""
        self._timeout = timeout
        self._cookie: str | None = None

    async def _login(self) -> None:
        try:
            async with asyncio.timeout(self._timeout):
                async with self._session.request("POST", self._base + "/api/auth/login", json={"password": self._password}) as resp:
                    if resp.status in (400, 401, 403):
                        raise EvccAuthError("login refused")
                    if resp.status >= 400:
                        raise EvccError(f"login answered {resp.status}")
                    cookie = resp.cookies.get("auth")
                    self._cookie = getattr(cookie, "value", cookie)
        except EvccError:
            raise
        except Exception as err:  # noqa: BLE001
            raise EvccError(str(err) or type(err).__name__) from err

    async def _get(self, path: str, retry: bool = True) -> Any:
        headers = {"Cookie": f"auth={self._cookie}"} if self._cookie else {}
        try:
            async with asyncio.timeout(self._timeout):
                async with self._session.request("GET", self._base + path, headers=headers) as resp:
                    status = resp.status
                    text = await resp.text()
        except Exception as err:  # noqa: BLE001
            raise EvccError(str(err) or type(err).__name__) from err
        if status == 401:
            if self._password and retry:
                await self._login()
                return await self._get(path, retry=False)
            raise EvccAuthError("evcc wants a password" if not self._password else "password refused")
        if status >= 400:
            raise EvccError(f"evcc answered {status}: {text[:120]}")
        try:
            return json.loads(text)
        except ValueError as err:
            raise EvccError("evcc did not answer with JSON") from err

    async def _send(self, method: str, path: str, retry: bool = True) -> None:
        headers = {"Cookie": f"auth={self._cookie}"} if self._cookie else {}
        try:
            async with asyncio.timeout(self._timeout):
                async with self._session.request(method, self._base + path, headers=headers) as resp:
                    status = resp.status
                    text = await resp.text()
        except Exception as err:  # noqa: BLE001
            raise EvccError(str(err) or type(err).__name__) from err
        if status == 401:
            if self._password and retry:
                await self._login()
                return await self._send(method, path, retry=False)
            raise EvccAuthError("evcc wants a password" if not self._password else "password refused")
        if status >= 400:
            raise EvccError(f"evcc answered {status}: {text[:120]}")

    async def set_plan(self, vehicle: str, soc: int, when: datetime) -> None:
        """evcc's one-time plan of a vehicle: charge to `soc` % by `when`."""
        t = when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        await self._send("POST", f"/api/vehicles/{quote(vehicle, safe='')}/plan/soc/{int(soc)}/{t}")

    async def set_loadpoint_mode(self, loadpoint: int, mode: str) -> None:
        """evcc's charge mode of loadpoint number `loadpoint` (1 = first): off, pv, minpv, now (or smart in newer versions)."""
        await self._send("POST", f"/api/loadpoints/{int(loadpoint)}/mode/{quote(mode, safe='')}")

    async def delete_plan(self, vehicle: str) -> None:
        await self._send("DELETE", f"/api/vehicles/{quote(vehicle, safe='')}/plan/soc")

    async def state(self) -> dict[str, Any]:
        data = await self._get("/api/state")
        if not isinstance(data, dict):
            raise EvccError("unexpected answer of /api/state")
        return data["result"] if isinstance(data.get("result"), dict) else data
