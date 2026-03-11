from __future__ import annotations

import json
from pathlib import Path

from modules.common.utils import read_json
from modules.virus_bridge.lifecycle import load_ticket_lifecycle, record_ticket_lifecycle_event


def _cfg(tmp_path: Path) -> dict:
    return {
        "app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"},
        "paths": {"audit_jsonl": str(tmp_path / "data" / "audit" / "portfolio_audit.jsonl")},
    }


def _payload(status: str = "OPEN") -> dict:
    return {
        "ticket_id": "VF-20260309-2200-001",
        "source_proposal_id": "PWV2-20260309-2200-001",
        "asset": {"symbol": "AMD", "isin": "US0079031078", "name": "Advanced Micro Devices"},
        "decision": "APPROVED",
        "status": status,
        "timestamp": "2026-03-09T22:00:00+01:00",
    }


def test_ticket_lifecycle_updates_and_dedupes_executed_event(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)

    created = record_ticket_lifecycle_event("TRADE_CANDIDATE_CREATED", _payload(), cfg)
    executed = record_ticket_lifecycle_event(
        "TRADE_EXECUTED_MANUAL",
        {**_payload("EXECUTED"), "buy_price": 257.1, "size_eur": 875.0, "timestamp": "2026-03-09T22:05:00+01:00"},
        cfg,
    )
    duplicate = record_ticket_lifecycle_event(
        "TRADE_EXECUTED_MANUAL",
        {**_payload("EXECUTED"), "buy_price": 257.1, "size_eur": 875.0, "timestamp": "2026-03-09T22:06:00+01:00"},
        cfg,
    )

    assert created["updated"] is True
    assert executed["updated"] is True
    assert duplicate["updated"] is False

    lifecycle = load_ticket_lifecycle("VF-20260309-2200-001", cfg)
    assert lifecycle is not None
    assert lifecycle["created"]["event_type"] == "TRADE_CANDIDATE_CREATED"
    assert lifecycle["executed"]["event_type"] == "TRADE_EXECUTED_MANUAL"
    assert lifecycle["executed"]["buy_price"] == 257.1
    assert lifecycle["executed"]["size_eur"] == 875.0
    assert lifecycle["rejected"] is None
    assert len(lifecycle["audit_refs"]) == 2

    audit_path = Path(cfg["paths"]["audit_jsonl"])
    rows = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 2
    assert rows[0]["event_type"] == "TRADE_CANDIDATE_CREATED"
    assert rows[1]["event_type"] == "TRADE_EXECUTED_MANUAL"


def test_ticket_lifecycle_tracks_rejected_and_deferred_states(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)

    record_ticket_lifecycle_event("TRADE_REJECTED_MANUAL", {**_payload("REJECTED"), "decision": "REDUCED"}, cfg)
    record_ticket_lifecycle_event(
        "TRADE_DEFERRED",
        {
            "ticket_id": "VF-20260309-2200-002",
            "source_proposal_id": "PWV2-20260309-2200-002",
            "asset": {"symbol": "BAYN.DE", "isin": "DE000BAY0017", "name": "Bayer AG"},
            "decision": "REDUCED",
            "status": "DEFERRED",
            "timestamp": "2026-03-09T22:10:00+01:00",
        },
        cfg,
    )

    rejected = read_json(tmp_path / "data" / "virus_bridge" / "ticket_lifecycle" / "VF-20260309-2200-001.json")
    deferred = read_json(tmp_path / "data" / "virus_bridge" / "ticket_lifecycle" / "VF-20260309-2200-002.json")
    assert rejected["rejected"]["status"] == "REJECTED"
    assert deferred["deferred"]["status"] == "DEFERRED"
