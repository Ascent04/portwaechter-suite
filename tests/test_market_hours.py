from __future__ import annotations

from datetime import datetime

from modules.virus_bridge.market_hours import get_market_status


def test_xetra_and_us_market_hours_basic_windows() -> None:
    xetra_open = get_market_status({"market": "XETRA"}, datetime.fromisoformat("2026-03-10T10:15:00+01:00"), {})
    xetra_closed = get_market_status({"market": "XETRA"}, datetime.fromisoformat("2026-03-10T18:15:00+01:00"), {})
    nasdaq_open = get_market_status({"market": "NASDAQ"}, datetime.fromisoformat("2026-03-10T16:15:00+01:00"), {})
    nasdaq_closed = get_market_status({"market": "NASDAQ"}, datetime.fromisoformat("2026-03-10T14:15:00+01:00"), {})

    assert xetra_open["is_open"] is True
    assert xetra_closed["is_open"] is False
    assert xetra_closed["next_open_hint"] == "09:00 Uhr"
    assert nasdaq_open["is_open"] is True
    assert nasdaq_closed["is_open"] is False
    assert nasdaq_closed["next_open_hint"] == "15:30 Uhr"


def test_unknown_market_falls_back_cleanly() -> None:
    status = get_market_status({"market": "OTC"}, datetime.fromisoformat("2026-03-10T10:15:00+01:00"), {})

    assert status["is_open"] is False
    assert status["market"] == "OTC"
    assert status["next_open_hint"] == "Marktzeit manuell pruefen"
