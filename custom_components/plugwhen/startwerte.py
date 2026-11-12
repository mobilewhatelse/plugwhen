"""Start values from open data, used until the car has its own (the same values the server delivers in
startwerte/v1/startwerte.json; tests/test_startwerte.py checks that they match when the server repository is next to this one).

* `TEMPERATURE`: consumption per km relative to 20 deg C. An own, deliberately middle curve: lowest around 18-24 deg C, about
  +60 % at -15 deg C (in the fleet mean of Geotab only ~54 % of the range is left at -15 deg C, cars with a heat pump lose
  much less, Recurrent), a little air conditioning above 25 deg C. Every car replaces it with its own days.
* `charge_loss(kw)`: the share of the wallbox energy lost when charging with `kw`: a fixed draw of the car while charging
  (~0.28 kW) plus ~4 %, limited to 5..30 %. Own function fitted to the ranges the ADAC measured in August 2026 (2.3 kW
  12.7-24.2 %, ~4.1 kW 8.0-12.8 %, 11 and 22 kW below 7 %). No table of others is copied.
"""

from __future__ import annotations

TEMPERATURE: list[tuple[float, float]] = [
    (-20, 1.75), (-15, 1.60), (-10, 1.45), (-5, 1.32), (0, 1.22), (5, 1.14), (10, 1.08), (15, 1.03),
    (20, 1.00), (25, 1.00), (30, 1.04), (35, 1.10)]

LOSS_BASE_KW = 0.28
LOSS_SHARE = 0.04
LOSS_MIN, LOSS_MAX = 0.05, 0.30


def temperature_factor(temp_c: float) -> float:
    """Consumption at `temp_c` relative to 20 deg C (linear between the points, the end value outside)."""
    pts = TEMPERATURE
    if temp_c <= pts[0][0]:
        return pts[0][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if temp_c <= x1:
            return y0 + (y1 - y0) * (temp_c - x0) / (x1 - x0)
    return pts[-1][1]


def charge_loss(kw: float) -> float:
    return min(LOSS_MAX, max(LOSS_MIN, LOSS_BASE_KW / max(0.5, kw) + LOSS_SHARE))


def charge_efficiency(kw: float) -> float:
    """Share of the wallbox energy that reaches the battery when charging with `kw` (without a learned value)."""
    return round(1.0 - charge_loss(kw), 3)
