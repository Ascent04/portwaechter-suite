from __future__ import annotations

from pathlib import Path

from modules.common.utils import write_json
from modules.virus_bridge.execution_performance import load_executed_tickets


def _cfg(tmp_path: Path) -> dict:
    return {"app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"}, "v2": {"data_dir": "data/v2"}}


def test_load_executed_tickets_reconstructs_only_bought_positions(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    write_json(
        tmp_path / "data" / "virus_bridge" / "trade_candidates" / "20260310" / "ticket_VF-1.json",
        {"ticket_id": "VF-1", "asset": {"symbol": "AMD", "name": "Advanced Micro Devices"}, "direction": "long"},
    )
    write_json(
        tmp_path / "data" / "virus_bridge" / "trade_candidates" / "20260310" / "ticket_VF-2.json",
        {"ticket_id": "VF-2", "asset": {"symbol": "BAYN.DE", "name": "Bayer AG"}, "direction": "long"},
    )
    write_json(
        tmp_path / "data" / "virus_bridge" / "executions" / "20260310" / "execution_VF-1.json",
        {"ticket_id": "VF-1", "status": "EXECUTED", "buy_price": 100.0, "size_eur": 1000.0, "executed_at": "2026-03-10T09:00:00+01:00"},
    )
    write_json(
        tmp_path / "data" / "virus_bridge" / "ticket_state.json",
        {"tickets": {"VF-1": {"status": "EXECUTED", "entry_price": 100.0, "entry_size_eur": 1000.0, "remaining_size_eur": 1000.0}}},
    )

    rows = load_executed_tickets(cfg)

    assert len(rows) == 1
    assert rows[0]["ticket_id"] == "VF-1"
    assert rows[0]["entry_price"] == 100.0
    assert rows[0]["entry_size_eur"] == 1000.0
