from __future__ import annotations


def score_volume(quote: dict, baseline: dict | None) -> dict:
    if quote.get("status") != "ok":
        return {"score": 0, "ratio": None, "status": "unavailable", "reason": "quote_unavailable"}
    if not isinstance(baseline, dict):
        return {"score": 0, "ratio": None, "status": "unavailable", "reason": "baseline_missing"}

    median = baseline.get("median_rolling")
    count = int(baseline.get("count", 0) or 0)
    volume = quote.get("volume")
    if median in (None, 0) or count < 5 or volume in (None, 0):
        return {"score": 0, "ratio": None, "status": "unavailable", "reason": "not_enough_history"}

    ratio = float(volume) / float(median)
    if ratio >= 2.5:
        return {"score": 2, "ratio": round(ratio, 2), "status": "ok", "reason": "strong_spike"}
    if ratio >= 1.5:
        return {"score": 1, "ratio": round(ratio, 2), "status": "ok", "reason": "medium_spike"}
    return {"score": 0, "ratio": round(ratio, 2), "status": "ok", "reason": "normal"}

