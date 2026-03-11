from __future__ import annotations

from modules.v2.scanner.momentum import score_momentum
from modules.v2.scanner.news_impact import score_news
from modules.v2.scanner.relative_strength import score_relative_strength
from modules.v2.scanner.volume_spike import score_volume


def test_scanner_scores_cover_core_cases() -> None:
    bullish = score_momentum({"status": "ok", "percent_change": 2.4})
    bearish = score_momentum({"status": "ok", "percent_change": -2.2})
    volume = score_volume({"status": "ok", "volume": 3000}, {"median_rolling": 1000, "count": 20})
    news = score_news(
        [{"title": "BASF earnings guidance raised", "summary": "Outlook improved", "source": "IR"}],
        {"name": "BASF SE", "symbol": "BAS.DE", "isin": "DE000BASF111"},
    )
    relative = score_relative_strength({"status": "ok", "percent_change": 2.4}, [0.2, 0.5, 1.0, 1.8, 2.0, 2.4])

    assert bullish["score"] == 3
    assert bearish["defense_bias"] == 3
    assert volume["score"] == 2
    assert news["score"] >= 2
    assert relative["score"] == 2


def test_volume_unavailable_without_history() -> None:
    score = score_volume({"status": "ok", "volume": 100}, {"median_rolling": 50, "count": 2})
    assert score["status"] == "unavailable"

