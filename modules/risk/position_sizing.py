from __future__ import annotations

from statistics import stdev


def _extract_r_pct(item: dict, horizon: str) -> float | None:
    if "r_pct" in item and item.get("r_pct") is not None:
        try:
            return float(item.get("r_pct"))
        except (TypeError, ValueError):
            return None

    horizons = item.get("horizons") if isinstance(item.get("horizons"), dict) else {}
    h = horizons.get(horizon) if isinstance(horizons.get(horizon), dict) else {}
    if h.get("status") == "ok" and h.get("r_pct") is not None:
        try:
            return float(h.get("r_pct"))
        except (TypeError, ValueError):
            return None
    return None


def compute_volatility(outcomes: list[dict], horizon: str = "3d") -> float:
    vals = []
    for item in outcomes:
        r = _extract_r_pct(item, horizon)
        if r is not None:
            vals.append(r)
    if len(vals) < 2:
        return 0.0
    return round(float(stdev(vals)), 6)


def recommended_position_multiplier(volatility: float, regime: str) -> float:
    threshold_high = 1.5
    mult = 1.0

    if float(volatility) > threshold_high:
        mult *= 0.7
    if str(regime) == "risk_off":
        mult *= 0.6

    if mult < 0.4:
        mult = 0.4
    if mult > 1.2:
        mult = 1.2
    return round(mult, 4)


def adjust_position_size(base_size: float, multiplier: float) -> float:
    return round(float(base_size) * float(multiplier), 6)
