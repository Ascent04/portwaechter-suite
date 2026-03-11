from __future__ import annotations

from pathlib import Path

from modules.virus_bridge.execution_performance import attach_mark_to_market, build_position_state


def _cfg(tmp_path: Path) -> dict:
    return {
        "app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"},
        "data_quality": {"max_quote_age_minutes": 30},
    }


def test_partial_exit_and_mark_to_market_are_computed_correctly(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    ticket = {
        "ticket_id": "VF-1",
        "asset": {"symbol": "AMD", "name": "Advanced Micro Devices"},
        "direction": "long",
        "entry_price": 100.0,
        "entry_size_eur": 1000.0,
        "remaining_size_eur": 1000.0,
        "status": "EXECUTED",
    }
    exits = [
        {
            "ticket_id": "VF-1",
            "exit_type": "PARTIAL",
            "exit_price": 110.0,
            "size_eur": 400.0,
            "realized_pnl_eur": 40.0,
            "realized_pnl_pct": 10.0,
            "timestamp": "2026-03-10T10:00:00+01:00",
        }
    ]

    position = build_position_state(ticket, exits, cfg)
    position = attach_mark_to_market(position, {"price": 105.0, "currency": "USD", "timestamp": "2099-03-10T10:05:00+01:00"}, cfg)

    assert position["status"] == "PARTIALLY_CLOSED"
    assert position["remaining_size_eur"] == 600.0
    assert position["realized_pnl_eur"] == 40.0
    assert position["realized_pnl_pct"] == 10.0
    assert position["unrealized_pnl_pct"] == 5.0
    assert position["unrealized_pnl_eur"] == 30.0
    assert position["price_status"] in {"fresh", "stale"}


def test_full_exit_sets_closed_and_unrealized_none(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    ticket = {
        "ticket_id": "VF-2",
        "asset": {"symbol": "BAYN.DE", "name": "Bayer AG"},
        "direction": "long",
        "entry_price": 50.0,
        "entry_size_eur": 1000.0,
        "remaining_size_eur": 1000.0,
        "status": "EXECUTED",
    }
    exits = [
        {
            "ticket_id": "VF-2",
            "exit_type": "FULL",
            "exit_price": 45.0,
            "size_eur": 1000.0,
            "realized_pnl_eur": -100.0,
            "realized_pnl_pct": -10.0,
            "timestamp": "2026-03-10T11:00:00+01:00",
        }
    ]

    position = build_position_state(ticket, exits, cfg)
    position = attach_mark_to_market(position, None, cfg)

    assert position["status"] == "CLOSED"
    assert position["remaining_size_eur"] == 0.0
    assert position["realized_pnl_eur"] == -100.0
    assert position["unrealized_pnl_eur"] is None
