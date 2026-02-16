from __future__ import annotations

import json
from pathlib import Path

from modules.signals_engine.multi_factor import compute_multi_factor_signals


def _append_jsonl(path: Path, row: dict) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def _write_ranked(path: Path, title: str, score: float = 6.0) -> None:
    path.write_text(
        json.dumps({"top": [{"id": "n1", "title": title, "score": score, "link": "https://example.org/news/1"}]}),
        encoding="utf-8",
    )


def test_compute_multi_factor_signals_combines_price_news_volume(tmp_path: Path) -> None:
    quotes_path = tmp_path / "quotes.jsonl"
    ranked_path = tmp_path / "ranked.json"

    rows = [
        {"status": "ok", "isin": "US0000000001", "name": "Alpha Tech Inc", "symbol": "alpha.us", "date": "2026-02-16", "time": "09:00:00", "open": 100.0, "close": 100.0, "volume": 1000},
        {"status": "ok", "isin": "US0000000001", "name": "Alpha Tech Inc", "symbol": "alpha.us", "date": "2026-02-16", "time": "10:00:00", "open": 100.0, "close": 101.0, "volume": 1100},
        {"status": "ok", "isin": "US0000000001", "name": "Alpha Tech Inc", "symbol": "alpha.us", "date": "2026-02-16", "time": "11:00:00", "open": 100.0, "close": 104.0, "volume": 3500},
    ]
    for row in rows:
        _append_jsonl(quotes_path, row)
    _write_ranked(ranked_path, "Alpha Tech expands AI infrastructure")

    signals = compute_multi_factor_signals(
        quotes_path,
        ranked_path,
        pct_move_intraday=2.0,
        pct_move_close_to_close=3.0,
        news_keyword_score_min=3,
        volume_spike_ratio=1.8,
        min_volume_points=3,
        multi_factor_score_min=3,
    )

    assert len(signals) == 1
    signal = signals[0]
    assert signal["id"] == "MULTI_FACTOR_SIGNAL"
    assert signal["factors"]["price"] >= 1
    assert signal["factors"]["news"] == 1
    assert signal["factors"]["volume"] == 1


def test_multi_factor_marks_volume_unavailable_if_history_thin(tmp_path: Path) -> None:
    quotes_path = tmp_path / "quotes.jsonl"
    ranked_path = tmp_path / "ranked.json"

    _append_jsonl(
        quotes_path,
        {"status": "ok", "isin": "US0000000002", "name": "Beta AG", "symbol": "beta.us", "date": "2026-02-16", "time": "11:00:00", "open": 100.0, "close": 104.0, "volume": 2000},
    )
    _write_ranked(ranked_path, "Beta AG wins large contract")

    signals = compute_multi_factor_signals(
        quotes_path,
        ranked_path,
        min_volume_points=20,
        multi_factor_score_min=2,
    )

    assert len(signals) == 1
    assert signals[0]["factors"]["volume"] == "unavailable"
    assert any("Volume history insufficient" in reason for reason in signals[0]["reasons"])


def test_multi_factor_without_news_requires_strong_price(tmp_path: Path) -> None:
    quotes_path = tmp_path / "quotes.jsonl"
    ranked_path = tmp_path / "ranked.json"

    _append_jsonl(
        quotes_path,
        {"status": "ok", "isin": "US0000000003", "name": "Gamma Corp", "symbol": "gamma.us", "date": "2026-02-16", "time": "11:00:00", "open": 100.0, "close": 102.1, "volume": 5000},
    )
    ranked_path.write_text(json.dumps({"top": []}), encoding="utf-8")

    signals = compute_multi_factor_signals(
        quotes_path,
        ranked_path,
        min_volume_points=1,
        volume_spike_ratio=1.0,
        multi_factor_score_min=2,
        pct_move_intraday_no_news=2.5,
        pct_move_close_to_close_no_news=3.5,
    )

    assert signals == []
