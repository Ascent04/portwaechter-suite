from __future__ import annotations

from modules.v2.recommendations.classify import classify_candidate


def _candidate(
    group: str = "holding",
    news_score: int = 0,
    volume_score: int = 0,
    timestamp: str = "2026-03-09T10:00:00+01:00",
) -> dict:
    return {
        "group": group,
        "scores": {"news": news_score, "volume": volume_score},
        "quote": {"timestamp": timestamp},
    }


def test_action_watch_defense_ignore_classification() -> None:
    assert classify_candidate(_candidate(group="scanner"), {"total_score": 6.5, "confidence": "mittel"}, {"defense_score": 2}) == "ACTION"
    assert (
        classify_candidate(
            _candidate(group="scanner"),
            {"total_score": 5.0, "confidence": "mittel", "reasons": ["momentum", "relative_strength"]},
            {"defense_score": 1},
        )
        == "IGNORE"
    )
    assert classify_candidate(_candidate(group="holding"), {"total_score": 7.0, "confidence": "hoch"}, {"defense_score": 6}) == "DEFENSE"
    assert classify_candidate(_candidate(group="scanner"), {"total_score": 1.5, "confidence": "spekulativ"}, {"defense_score": 0}) == "IGNORE"


def test_speculative_scanner_is_dropped_but_holding_priority_survives() -> None:
    speculative_scanner = classify_candidate(
        _candidate(group="scanner"),
        {"total_score": 3.0, "confidence": "spekulativ", "reasons": ["momentum", "relative_strength"]},
        {"defense_score": 0},
    )
    holding_watch = classify_candidate(
        _candidate(group="holding"),
        {"total_score": 5.0, "confidence": "mittel", "reasons": ["portfolio_priority", "relative_strength"]},
        {"defense_score": 1},
    )
    news_watch = classify_candidate(
        _candidate(group="scanner", news_score=2),
        {"total_score": 3.2, "confidence": "spekulativ", "reasons": ["news"]},
        {"defense_score": 0},
    )
    volume_watch = classify_candidate(
        _candidate(group="scanner", volume_score=1),
        {"total_score": 5.1, "confidence": "mittel", "reasons": ["momentum", "volume", "relative_strength"]},
        {"defense_score": 0},
    )
    stale_holding = classify_candidate(
        _candidate(group="holding", timestamp="2026-02-27"),
        {"total_score": 5.0, "confidence": "mittel", "reasons": ["portfolio_priority", "momentum"]},
        {"defense_score": 1},
    )

    assert speculative_scanner == "IGNORE"
    assert holding_watch == "WATCH"
    assert news_watch == "WATCH"
    assert volume_watch == "WATCH"
    assert stale_holding == "IGNORE"
