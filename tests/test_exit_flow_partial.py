from __future__ import annotations

from pathlib import Path

from modules.common.utils import read_json, write_json
from modules.virus_bridge.exit_flow import mark_partial_exit


def _cfg(tmp_path: Path) -> dict:
    return {"app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"}}


def test_mark_partial_exit_persists_exit_and_remaining_size(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    ticket_id = "VF-20260309-2300-001"
    write_json(
        tmp_path / "data" / "virus_bridge" / "trade_candidates" / "20260309" / f"ticket_{ticket_id}.json",
        {"ticket_id": ticket_id, "source_proposal_id": "PWV2-1", "asset": {"name": "Advanced Micro Devices"}, "direction": "long", "decision": "APPROVED"},
    )
    write_json(
        tmp_path / "data" / "virus_bridge" / "ticket_state.json",
        {"tickets": {ticket_id: {"status": "EXECUTED", "entry_price": 100.0, "entry_size_eur": 1000.0, "remaining_size_eur": 1000.0}}},
    )

    mark_partial_exit(ticket_id, {"exit_price": 110.0, "size_eur": 400.0, "exit_reason": "PARTIAL_TAKE_PROFIT"}, cfg)

    state = read_json(tmp_path / "data" / "virus_bridge" / "ticket_state.json")
    row = state["tickets"][ticket_id]
    assert row["status"] == "PARTIALLY_CLOSED"
    assert row["remaining_size_eur"] == 600.0

    exit_path = next((tmp_path / "data" / "virus_bridge" / "exits").rglob(f"exit_{ticket_id}_*.json"))
    payload = read_json(exit_path)
    assert payload["exit_type"] == "PARTIAL"
    assert payload["exit_reason"] == "PARTIAL_TAKE_PROFIT"
    assert payload["closed_fraction"] == 0.4
    assert payload["realized_pnl_eur"] == 40.0
    assert payload["realized_pnl_pct"] == 10.0
