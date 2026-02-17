from __future__ import annotations

from modules.briefing.morning import build_briefing


def test_empty_portfolio_does_not_crash() -> None:
    briefing = build_briefing({"positions": []}, [], [], cfg={"signals": {"thresholds": {"multi_factor_score_min": 2}}})
    assert "holdings_summary" in briefing
    assert isinstance(briefing["top_opportunities"], list)
    assert briefing["holdings_block"]["total_pnl_pct"] == 0.0


def test_no_signals_still_has_summary() -> None:
    snapshot = {
        "positions": [
            {"isin": "DE000BASF111", "name": "BASF", "pnl_pct": 1.2, "quantity": 10, "avg_price": 50, "last_price": 51},
            {"isin": "DE000BAY0017", "name": "Bayer", "pnl_pct": -0.8, "quantity": 10, "avg_price": 50, "last_price": 49.6},
        ]
    }
    briefing = build_briefing(snapshot, [], [], cfg={"signals": {"thresholds": {"multi_factor_score_min": 2}}})
    assert "Total: 0" in briefing["signals_summary"]


def test_news_only_creates_opportunities() -> None:
    news = [{"isin": "DE000ENER6Y0", "name": "Siemens Energy", "title": "X", "title_translated": "Y", "score": 5, "source": "finanznachrichten"}]
    briefing = build_briefing({"positions": []}, [], news, cfg={"signals": {"thresholds": {"multi_factor_score_min": 2}}})
    assert briefing["top_opportunities"]
    assert briefing["top_opportunities"][0]["reason"] == "News-getrieben"


def test_briefing_output_structure() -> None:
    briefing = build_briefing({"positions": []}, [], [], cfg={"signals": {"thresholds": {"multi_factor_score_min": 2}}})
    required = {"holdings_summary", "signals_summary", "top_opportunities", "holdings_block", "holdings_signals", "generated_at", "positions"}
    assert required.issubset(set(briefing.keys()))
