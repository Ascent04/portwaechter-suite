from __future__ import annotations

from modules.v2.recommendations.classify import classify_candidate
from modules.v2.telegram.copy import classification_label


def test_intact_holding_becomes_halten() -> None:
    candidate = {
        "group": "holding",
        "quote": {"timestamp": "2026-03-10T10:00:00+01:00", "status": "ok", "percent_change": 0.4},
        "details": {"news": {"negative_hits": 0, "drivers": []}},
        "portfolio_context": {"weight_pct": 9.5, "concentration_weight_pct": 18.0, "concentration_risk": "low"},
        "weight_pct": 9.5,
        "regime": "neutral",
        "scores": {"news": 0, "volume": 0},
        "portfolio_priority": 1.0,
    }
    opp = {"total_score": 4.8, "confidence": "mittel", "reasons": ["portfolio_priority", "relative_strength"]}
    defense = {"defense_score": 1.5, "sell_score": 1.0, "risk_reduce_score": 1.5, "risk_reduce_reasons": [], "sell_reasons": []}

    classification = classify_candidate(candidate, opp, defense)

    assert classification == "WATCH"
    assert classification_label(classification, candidate) == "HALTEN"


def test_non_holding_is_not_sell_signal() -> None:
    candidate = {
        "group": "scanner",
        "quote": {"timestamp": "2026-03-10T10:00:00+01:00", "status": "ok", "percent_change": -5.0},
        "details": {"news": {"negative_hits": 2, "drivers": ["negative_news"]}},
        "regime": "risk_off",
        "scores": {"news": 0, "volume": 0},
    }
    opp = {"total_score": 0.0, "confidence": "spekulativ", "reasons": []}
    defense = {"defense_score": 8.0, "sell_score": 8.0, "risk_reduce_score": 6.0, "sell_reasons": ["negative_momentum_strong"]}

    assert classify_candidate(candidate, opp, defense) == "IGNORE"
