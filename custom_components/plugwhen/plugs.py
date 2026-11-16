"""Recorded plug-in times (pure Python, no Home Assistant imports).

Home Assistant keeps the history of a plug sensor only for a few days (recorder `purge_keep_days`, 10 by default) and
binary sensors have no long-term statistics. Plugwhen therefore writes the plug-in and unplug times down itself.
They make the potential calculator use the real parking windows instead of assuming "plugged in from arrival", and show
how the car is actually used (nobody plugs in every day).

The log is a list of `[in, out]` (ISO times, `out` None while plugged in). Unknown states (the sensor unavailable for a
moment, a restart) neither open nor close an interval.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any

KEEP_DAYS = 400
MAX_ENTRIES = 1500
MIN_INTERVAL = timedelta(minutes=2)    # shorter on/off flickers are dropped
SHARE_WEEKS = 8                        # the plugged-in share per weekday and hour looks back this far
SHARE_MIN_DAYS = 14                    # with less recorded time nothing is said (None)


def _parse(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value)) if value else None
    except ValueError:
        return None


class PlugLog:
    def __init__(self, data: list[list[str | None]] | None = None) -> None:
        self.items: list[list[str | None]] = [list(x) for x in (data or []) if isinstance(x, (list, tuple)) and len(x) == 2]

    @property
    def open(self) -> bool:
        return bool(self.items) and self.items[-1][1] is None

    def change(self, plugged: bool | None, t: datetime) -> bool:
        """Note a new state of the plug sensor. Returns True if the log changed (then it should be saved)."""
        if plugged is None:
            return False
        if plugged and not self.open:
            self.items.append([t.isoformat(), None])
            return True
        if not plugged and self.open:
            start = _parse(self.items[-1][0])
            if start is not None and t - start < MIN_INTERVAL:
                self.items.pop()           # a flicker, not a plug-in
            else:
                self.items[-1][1] = t.isoformat()
            return True
        return False

    def seed(self, states: list[tuple[datetime, bool | None]]) -> bool:
        """Fill an empty log once from the short recorder history (states in time order)."""
        if self.items:
            return False
        for t, on in states:
            self.change(on, t)
        return bool(self.items)

    def trim(self, now: datetime) -> None:
        cut = now - timedelta(days=KEEP_DAYS)
        self.items = [x for x in self.items if (_parse(x[1]) or now) >= cut][-MAX_ENTRIES:]

    def intervals(self) -> list[tuple[datetime, datetime | None]]:
        out = []
        for a, b in self.items:
            pa = _parse(a)
            if pa is not None:
                out.append((pa, _parse(b)))
        return out

    def first(self) -> datetime | None:
        iv = self.intervals()
        return iv[0][0] if iv else None

    def share_by_hour(self, now: datetime, weeks: int = SHARE_WEEKS, min_days: int = SHARE_MIN_DAYS) -> dict[tuple[int, int], float] | None:
        """How often the car was plugged in, per (weekday 0=Monday, hour): the share of that hour over the last `weeks` weeks
        (0..1). None while fewer than `min_days` days are recorded: then nothing is known about the habit.
        The sun can only be planned for hours in which the car is usually plugged in."""
        first = self.first()
        if first is None:
            return None
        start = max(first, now - timedelta(weeks=weeks))
        if (now - start).days < min_days:
            return None
        start = start.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        end = now.replace(minute=0, second=0, microsecond=0)
        plugged: dict[tuple[int, int], float] = {}
        total: dict[tuple[int, int], float] = {}
        t = start
        while t < end:
            total[(t.weekday(), t.hour)] = total.get((t.weekday(), t.hour), 0.0) + 1.0
            t += timedelta(hours=1)
        hour = timedelta(hours=1)
        for a, b_ in self.intervals():
            lo, hi = max(a, start), min(b_ or now, end)
            if hi <= lo:
                continue
            t = lo.replace(minute=0, second=0, microsecond=0)
            while t < hi:
                part = (min(hi, t + hour) - max(lo, t)).total_seconds() / 3600.0
                if part > 0:
                    plugged[(t.weekday(), t.hour)] = plugged.get((t.weekday(), t.hour), 0.0) + part
                t += hour
        return {k: min(1.0, plugged.get(k, 0.0) / n) for k, n in total.items() if n > 0}

    def summary(self, now: datetime, days: int = 28) -> dict[str, Any]:
        """How the car was plugged in over the last `days`: how many nights, the typical plug-in and unplug time."""
        since = now - timedelta(days=days)
        iv = [(a, b) for a, b in self.intervals() if (b or now) >= since]
        nights = set()      # a night counts if the car was plugged in at 02:00
        for a, b in iv:
            end = b or now
            d = a.date()
            while d <= end.date():
                night = datetime.combine(d, time(2), tzinfo=a.tzinfo)
                if a <= night <= end and night >= since:
                    nights.add(d)
                d += timedelta(days=1)
        ins = sorted(a.hour + a.minute / 60 for a, _ in iv)
        outs = sorted(b.hour + b.minute / 60 for _, b in iv if b is not None)
        first = self.first()
        covered = min(days, max(0, (now - first).days)) if first else 0

        def med(x: list[float]) -> str | None:
            if not x:
                return None
            m = x[len(x) // 2]
            return f"{int(m):02d}:{int(round((m - int(m)) * 60)) % 60:02d}"

        return {"days": covered, "plug_ins": len(iv), "nights_plugged": len(nights), "typical_plug_in": med(ins),
                "typical_unplug": med(outs), "plugged_now": self.open, "recorded_since": first.isoformat() if first else None}
