from __future__ import annotations


def _score_bucket(base_score: float) -> int:
    if base_score >= 6:
        return 4
    if base_score >= 4:
        return 3
    return 2


def _expectancy_boost(base_score: float, regime: str, expectancy_data: dict) -> tuple[float, list[str]]:
    reasons: list[str] = []
    boost = 0.0
    bucket = _score_bucket(base_score)
    score_key = f"factor_score>={bucket}"
    score_row = ((expectancy_data.get("score_calibration") or {}).get(score_key) or {}).get("3d", {})
    regime_row = ((expectancy_data.get("by_regime") or {}).get(regime) or {}).get("3d", {})

    score_exp = float(score_row.get("expectancy", 0) or 0)
    if score_exp > 0:
        boost += 0.5 if score_row.get("expectancy_confidence") == "low" else 1.0
        reasons.append("positive_setup_expectancy")

    regime_exp = float(regime_row.get("expectancy", 0) or 0)
    if regime_exp > 0:
        boost += 0.25 if regime_row.get("expectancy_confidence") == "low" else 0.5
        reasons.append("positive_regime_expectancy")
    return boost, reasons


def compute_opportunity_score(candidate: dict, regime: str, expectancy_data: dict) -> dict:
    scores = candidate.get("scores", {})
    base_score = sum(float(scores.get(key, 0) or 0) for key in ("momentum", "volume", "news", "relative_strength"))
    reasons = [key for key in ("momentum", "volume", "news", "relative_strength") if float(scores.get(key, 0) or 0) > 0]

    regime_boost = 0.75 if regime == "risk_on" else -0.5 if regime == "risk_off" else 0.0
    if regime_boost > 0:
        reasons.append("risk_on_regime")
    elif regime_boost < 0:
        reasons.append("risk_off_penalty")

    expectancy_boost, expectancy_reasons = _expectancy_boost(base_score, regime, expectancy_data or {})
    reasons.extend(expectancy_reasons)

    priority = float(candidate.get("portfolio_priority", 0) or 0)
    if priority:
        reasons.append("portfolio_priority")

    total_score = max(0.0, min(10.0, base_score + regime_boost + expectancy_boost + priority))
    if total_score >= 7:
        confidence = "hoch"
    elif total_score >= 4.5:
        confidence = "mittel"
    else:
        confidence = "spekulativ"

    return {
        "total_score": round(total_score, 2),
        "confidence": confidence,
        "base_score": round(base_score, 2),
        "reasons": reasons,
    }

