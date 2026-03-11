from __future__ import annotations


def score_momentum(quote: dict) -> dict:
    pct = quote.get("percent_change")
    if quote.get("status") != "ok" or pct is None:
        return {"score": 0, "defense_bias": 0, "status": "unavailable", "signal": "none"}

    pct_value = float(pct)
    if pct_value >= 2.0:
        return {"score": 3, "defense_bias": 0, "status": "ok", "signal": "strong_up"}
    if pct_value >= 1.0:
        return {"score": 2, "defense_bias": 0, "status": "ok", "signal": "medium_up"}
    if pct_value >= 0.25:
        return {"score": 1, "defense_bias": 0, "status": "ok", "signal": "mild_up"}
    if pct_value <= -2.0:
        return {"score": 0, "defense_bias": 3, "status": "ok", "signal": "strong_down"}
    if pct_value <= -1.0:
        return {"score": 0, "defense_bias": 2, "status": "ok", "signal": "medium_down"}
    return {"score": 0, "defense_bias": 1 if pct_value < 0 else 0, "status": "ok", "signal": "flat"}

