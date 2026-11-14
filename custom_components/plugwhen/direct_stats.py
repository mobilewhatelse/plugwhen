"""How the wallbox follows in the mode 'direct' (pure Python, no Home Assistant imports; only while sharing).

Per wallbox model (integration, model, firmware from the device registry, never a name or serial): how many commands were sent,
how many were not taken within `REPLY_S` seconds or failed, and the time until the entity showed the new value (median and
95th percentile, rounded to whole seconds). Kept locally until the next weekly statistics, then started afresh.
"""

from __future__ import annotations

from typing import Any

REPLY_S = 120          # no new value within this time: counted as not taken
MAX_TIMES = 50         # reply times kept per model and week
MAX_MODELS = 3


def key(platform: str | None, model: str | None, firmware: str | None) -> str:
    def clean(x: str | None) -> str:
        return str(x or "?").strip().replace("|", "/")[:40] or "?"
    return f"{clean(platform)}|{clean(model)}|{clean(firmware)}"


def record(stats: dict[str, Any], k: str, ok: bool, seconds: float | None = None) -> None:
    if k not in stats and len(stats) >= MAX_MODELS:
        return
    s = stats.setdefault(k, {"n": 0, "fail": 0, "t": []})
    s["n"] += 1
    if not ok:
        s["fail"] += 1
    elif seconds is not None and seconds >= 0:
        s["t"] = (s["t"] + [round(float(seconds), 1)])[-MAX_TIMES:]


def _pct(values: list[float], p: float) -> float:
    v = sorted(values)
    i = min(len(v) - 1, max(0, round(p * (len(v) - 1))))
    return v[i]


def summary(stats: dict[str, Any]) -> list[dict[str, Any]]:
    """What goes out: one entry per model with at least one command."""
    out = []
    for k, s in sorted(stats.items()):
        if not isinstance(s, dict) or not s.get("n"):
            continue
        platform, model, firmware = (k.split("|") + ["?", "?"])[:3]
        e: dict[str, Any] = {"art": "wallbox", "integration": platform, "modell": model, "firmware": firmware,
                             "befehle": int(s["n"]), "fehl_anteil": round(s.get("fail", 0) / s["n"], 2)}
        if s.get("t"):
            e["antwort_s_median"] = round(_pct(s["t"], 0.5))
            e["antwort_s_p95"] = round(_pct(s["t"], 0.95))
        out.append(e)
    return out
