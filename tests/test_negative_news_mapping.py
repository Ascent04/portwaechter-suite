from __future__ import annotations

from modules.v2.scanner.news_impact import score_news
from modules.v2.telegram.copy import human_reason


def test_negative_news_terms_are_detected_as_burden() -> None:
    instrument = {"symbol": "BAYN.DE", "isin": "DE000BAY0017", "name": "Bayer AG"}
    news_items = [
        {"title": "Bayer AG analyst downgrade after profit warning", "summary": "Guidance cut and regulatory risk rising", "source": "news"},
    ]

    result = score_news(news_items, instrument)

    assert result["negative_hits"] >= 3
    assert "negative_news" in result["drivers"]
    assert "news_burden" in result["drivers"]
    assert human_reason("news_burden") == "Nachrichtenlage belastend"
