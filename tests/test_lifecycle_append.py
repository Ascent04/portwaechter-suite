from __future__ import annotations

from pathlib import Path

from modules.virus_bridge.lifecycle import append_lifecycle_event, init_lifecycle, load_lifecycle


def _cfg(tmp_path: Path) -> dict:
    return {
        "app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"},
        "paths": {"audit_jsonl": str(tmp_path / "data" / "audit" / "portfolio_audit.jsonl")},
    }


def test_append_lifecycle_event_updates_status_and_blocks_duplicate_executed(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    ticket = {
        "ticket_id": "VF-20260309-2200-001",
        "source_proposal_id": "PWV2-20260309-2200-001",
        "asset": {"symbol": "AMD", "name": "Advanced Micro Devices"},
        "timestamp": "2026-03-09T22:00:00+01:00",
    }
    init_lifecycle(ticket, cfg)
    append_lifecycle_event(ticket["ticket_id"], "TRADE_CANDIDATE_CREATED", ticket, cfg)
    append_lifecycle_event(ticket["ticket_id"], "TRADE_TICKET_SENT", {**ticket, "status": "SENT"}, cfg)
    executed = append_lifecycle_event(
        ticket["ticket_id"],
        "TRADE_EXECUTED_MANUAL",
        {**ticket, "status": "EXECUTED", "buy_price": 257.1, "size_eur": 875.0},
        cfg,
    )
    duplicate = append_lifecycle_event(
        ticket["ticket_id"],
        "TRADE_EXECUTED_MANUAL",
        {**ticket, "status": "EXECUTED", "buy_price": 258.0, "size_eur": 900.0},
        cfg,
    )

    lifecycle = load_lifecycle(ticket["ticket_id"], cfg)
    assert executed["updated"] is True
    assert duplicate["updated"] is False
    assert lifecycle is not None
    assert lifecycle["current_status"] == "EXECUTED"
    assert lifecycle["executed"]["buy_price"] == 257.1
    assert len([row for row in lifecycle["audit_refs"] if row.get("ref")]) == 3
