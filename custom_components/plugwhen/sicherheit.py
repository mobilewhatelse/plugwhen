"""Safety check before every departure (pure Python, no Home Assistant imports).

Wish of the user after the field test of 16.11.2026: the car must be charged in any case. Two errors of Plugwhen's own (the full
target dropped at midnight, the wallbox paused at every new energy value) went unnoticed because the existing warning trusts
Plugwhen's own plan. This check does not:

* **Promise.** While the car is plugged in, the highest target Plugwhen planned for a departure is kept. If the planned target falls
  below it without the battery having got there, something is wrong (a setting changed by the user resets the promise).
* **From LEAD_H hours before every departure** (every day, weeks do not matter) it compares the promise with reality: still missing
  energy that only just fits into the time left at the wallbox's power, a planned target that fell, or a wallbox that does not charge
  although it should. Then Plugwhen switches the wallbox to "charge now" (the wallbox's grid mode, start, or evcc "now") and sends a
  message with the reason. A message alone in the night would not be read.
* "Charge now" ends when the target is reached, the departure is past, or the car was unplugged; the wallbox is given back.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta

LEAD_H = 3.0            # the check starts this many hours before a departure
MIN_KWH = 0.5           # less missing energy is no reason to act
TIGHT = 0.6             # missing energy above this share of what still fits into the time left: charge now
STALL_MIN = 10          # a planned window without charging this long: charge now
DROP_PCT = 2.0          # the planned target fell this much below the promise: charge now
DONE_MARGIN = 1.0       # the promise counts as kept this many percent below it (cars often stop at 99 %; the weekly full
                        # charge is booked as done there too, and its target then falls back on purpose)
SAME_DEPARTURE = timedelta(hours=3)   # a departure that moved by up to this much is still the same one
QUIET = timedelta(hours=3)            # after a message to the user no further one for this long (the wallbox is still switched)


@dataclass(frozen=True)
class Promise:
    departure: datetime
    target: float            # highest planned target in % for this departure


@dataclass(frozen=True)
class Alarm:
    reason: str              # "tight", "stalled", "target_fell"
    missing_kwh: float
    target: float
    soc: float | None
    hours_left: float


def update_promise(promise: Promise | None, departure: datetime | None, target: float | None, plugged: bool | None,
                   now: datetime, still_expected: bool = True) -> Promise | None:
    """The promise for the coming departure, kept while the car stays plugged in.

    `still_expected` = the promised departure is still one Plugwhen expects. False when the user took it away (a calendar
    trip deleted or moved, a departure entity changed): then the promise goes with it. Otherwise a planned departure that
    suddenly lies later is not believed, the promise stays as it was (never raised by the later departure's target)."""
    if plugged is False or departure is None or target is None:
        return None
    if promise is not None and now >= promise.departure + SAME_DEPARTURE:
        promise = None   # that departure is over
    if promise is None or abs((departure - promise.departure).total_seconds()) > SAME_DEPARTURE.total_seconds():
        if promise is not None and still_expected and departure > promise.departure and now < promise.departure:
            return promise   # a later departure is planned while the promised one is still ahead: the promise stays
        return Promise(departure, float(target))
    return Promise(max(departure, promise.departure), max(promise.target, float(target)))


def missing_kwh(target: float, soc: float | None, capacity_kwh: float, efficiency: float) -> float:
    """Wallbox energy still needed for the target (with the charging losses)."""
    if soc is None:
        return 0.0
    return max(0.0, (target - soc) / 100.0 * capacity_kwh / max(0.1, efficiency))


def check(now: datetime, promise: Promise | None, planned_target: float | None, soc: float | None, *, plugged: bool | None,
          charging: bool, stalled_min: float, capacity_kwh: float, efficiency: float, max_kw: float | None) -> Alarm | None:
    """None, or why the car must charge now. `stalled_min` = minutes a planned window has been running without charging."""
    if promise is None or plugged is False or soc is None:
        return None
    hours = (promise.departure - now).total_seconds() / 3600.0
    if hours <= 0 or hours > LEAD_H:
        return None
    if soc >= promise.target - DONE_MARGIN:
        return None   # kept (same margin as the end of "charge now")
    need = missing_kwh(promise.target, soc, capacity_kwh, efficiency)
    if need < MIN_KWH:
        return None

    def alarm(reason: str) -> Alarm:
        return Alarm(reason, round(need, 1), promise.target, soc, round(hours, 2))

    if planned_target is not None and planned_target < promise.target - DROP_PCT:
        return alarm("target_fell")
    if not charging and stalled_min >= STALL_MIN:
        return alarm("stalled")
    if max_kw and need >= TIGHT * hours * max_kw:
        return alarm("tight")
    return None


def stall_start(since: datetime | None, now: datetime, window_running: bool, plugged: bool | None, charging_known: bool,
                charging: bool) -> datetime | None:
    """Since when a planned window has been running without charging, or None. Only a wallbox that says it does not charge
    counts: one that is not reachable (the Wi-Fi restarts at night) says nothing, and that is no reason to alarm."""
    if window_running and plugged is not False and charging_known and not charging:
        return since or now
    return None


def charge_now_done(now: datetime, promise: Promise | None, soc: float | None, plugged: bool | None) -> bool:
    """Ends "charge now": target reached, departure past, car unplugged, or nothing promised any more."""
    if promise is None or plugged is False:
        return True
    if now >= promise.departure:
        return True
    return soc is not None and soc >= promise.target - DONE_MARGIN


def alarm_text(language: str | None, a: Alarm, name: str, switched: bool = True) -> tuple[str, str]:
    """The message that Plugwhen switched to "charge now" and why - or, if the wallbox did not take it, that the user must
    start charging."""
    de = (language or "").lower().startswith("de")
    why = {
        "target_fell": ("das geplante Ziel war plötzlich niedriger als zugesagt", "the planned target suddenly fell below the promise"),
        "stalled": ("die Wallbox lädt nicht, obwohl sie laut Plan laden sollte", "the wallbox does not charge although the plan says so"),
        "tight": ("die Zeit bis zur Abfahrt wird knapp", "the time until the departure is getting short"),
    }[a.reason]
    h, m = int(a.hours_left), int(round((a.hours_left - int(a.hours_left)) * 60))
    if de:
        kwh = f"{a.missing_kwh:.1f}".replace(".", ",")
        return (f"Plugwhen · {name}: lädt jetzt" if switched else f"Plugwhen · {name}: bitte Laden starten",
                f"Sicherheitsprüfung: {why[0]}. Es fehlen noch {kwh} kWh bis {a.target:.0f} % "
                f"(jetzt {a.soc:.0f} %), Abfahrt in {h} h {m:02d} min. "
                + ("Plugwhen hat auf „Jetzt laden“ geschaltet." if switched
                   else "Plugwhen konnte die Wallbox nicht auf „Jetzt laden“ schalten – bitte das Laden selbst starten."))
    return (f"Plugwhen · {name}: charging now" if switched else f"Plugwhen · {name}: please start charging",
            f"Safety check: {why[1]}. {a.missing_kwh:.1f} kWh missing to {a.target:.0f} % (now {a.soc:.0f} %), departure in "
            f"{h} h {m:02d} min. "
            + ("Plugwhen switched to “charge now”." if switched
               else "Plugwhen could not switch the wallbox to “charge now” – please start charging yourself."))
