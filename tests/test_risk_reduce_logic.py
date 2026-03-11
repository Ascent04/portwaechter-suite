from __future__ import annotations

from modules.v2.recommendations.classify import classify_candidate
from modules.v2.telegram.copy import classification_label


def test_defensive_regime_and_high_weight_becomes_risk_reduce() -> None:
    candidate = {
        "group": "holding",
        "quote": {"timestamp": "2026-03-10T10:00:00+01:00", "status": "ok", "percent_change": -1.3},
        "details": {"news": {"negative_hits": 1, "drivers": ["news_burden"]}},
        "portfolio_context": {"weight_pct": 19.0, "concentration_weight_pct": 20.0, "concentration_risk": "low"},
        "weight_pct": 19.0,
        "regime": "risk_off",
        "scores": {"news": 0, "volume": 0},
    }
    opp = {"total_score": 3.8, "confidence": "mittel", "reasons": ["portfolio_priority"]}
    defense = {
        "defense_score": 5.8,
        "sell_score": 4.0,
        "risk_reduce_score": 5.8,
        "sell_reasons": ["negative_momentum_light", "high_weight"],
        "risk_reduce_reasons": ["high_weight", "news_burden", "risk_off_regime"],
    }

    classification = classify_candidate(candidate, opp, defense)

    assert classification == "DEFENSE"
    assert classification_label(classification, {**candidate, "defense_score": defense}) == "RISIKO REDUZIEREN"
