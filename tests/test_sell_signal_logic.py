from __future__ import annotations

from modules.v2.recommendations.classify import classify_candidate
from modules.v2.telegram.copy import classification_label


def test_strong_negative_move_and_high_weight_becomes_sell_pruefen() -> None:
    candidate = {
        "group": "holding",
        "quote": {"timestamp": "2026-03-10T10:00:00+01:00", "status": "ok", "percent_change": -5.2},
        "details": {"news": {"negative_hits": 2, "drivers": ["negative_news"]}},
        "portfolio_context": {"weight_pct": 18.0, "concentration_weight_pct": 28.0, "concentration_risk": "medium"},
        "weight_pct": 18.0,
        "regime": "risk_off",
        "scores": {"news": 0, "volume": 0},
    }
    opp = {"total_score": 1.0, "confidence": "spekulativ", "reasons": []}
    defense = {
        "defense_score": 8.0,
        "sell_score": 8.0,
        "risk_reduce_score": 6.0,
        "sell_reasons": ["negative_momentum_strong", "news_burden", "high_weight"],
        "risk_reduce_reasons": ["high_weight", "risk_off_regime"],
    }

    classification = classify_candidate(candidate, opp, defense)

    assert classification == "DEFENSE"
    assert classification_label(classification, {**candidate, "defense_score": defense}) == "VERKAUFEN PRUEFEN"
