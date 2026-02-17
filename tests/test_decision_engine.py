from __future__ import annotations

from modules.decision_engine.engine import classify_candidate, score_candidates


def test_classify_setup_watch_drop() -> None:
    setup = classify_candidate(
        {
            "score": 8,
            "news_score": 4,
            "signal_factor_score": 3,
            "volume_light": "green",
            "regime": "neutral",
            "direction": "bullish",
            "expectancy_3d": 0.6,
            "expectancy_confidence": "high",
        },
        "long-only",
    )
    watch = classify_candidate({"score": 5, "news_score": 4, "signal_factor_score": 1, "volume_light": "yellow", "regime": "neutral", "direction": "neutral"}, "long-only")
    drop = classify_candidate({"score": 0, "news_score": 0, "signal_factor_score": 0, "volume_light": "gray", "regime": "neutral", "direction": "neutral"}, "long-only")
    assert setup["bucket"] == "SETUP"
    assert watch["bucket"] == "WATCH"
    assert drop["bucket"] == "DROP"


def test_expectancy_gate_blocks_setup() -> None:
    gated = classify_candidate(
        {
            "score": 8,
            "news_score": 4,
            "signal_factor_score": 3,
            "volume_light": "green",
            "regime": "neutral",
            "direction": "bullish",
            "expectancy_3d": -0.1,
            "expectancy_confidence": "high",
        },
        "long-only",
    )
    assert gated["bucket"] != "SETUP"
    assert "expectancy_gate" in gated["reasons"]


def test_score_candidates_merges_sources() -> None:
    holdings = [{"isin": "DE000BASF111", "name": "BASF"}]
    radar = [{"isin": "US02079K3059", "name": "Alphabet", "opportunity_score": 4}]
    signals = [{"isin": "DE000BASF111", "name": "BASF", "factor_score": 3, "direction": "bullish", "reasons": ["price_intraday"]}]
    news = [{"isin": "DE000BASF111", "name": "BASF", "score": 4}]

    rows = score_candidates(holdings, radar, signals, news, "neutral", {"DE000BASF111": "green"})
    assert rows
    top = rows[0]
    assert top["isin"] == "DE000BASF111"
    assert top["score"] >= 8
