from __future__ import annotations

from datetime import datetime

from modules.virus_bridge.data_quality import compute_quote_age_minutes, is_quote_fresh


def _cfg() -> dict:
    return {"app": {"timezone": "Europe/Berlin"}, "data_quality": {"max_quote_age_minutes": 15}}


def test_quote_age_and_freshness() -> None:
    quote = {"timestamp": "2026-03-10T15:50:00+01:00"}
    now = datetime.fromisoformat("2026-03-10T16:00:00+01:00")

    assert compute_quote_age_minutes(quote, now, _cfg()) == 10.0
    assert is_quote_fresh(quote, now, _cfg()) is True


def test_missing_timestamp_is_not_fresh() -> None:
    now = datetime.fromisoformat("2026-03-10T16:00:00+01:00")
    assert compute_quote_age_minutes({}, now, _cfg()) is None
    assert is_quote_fresh({}, now, _cfg()) is False
