from __future__ import annotations

import json
from pathlib import Path

from modules.virus_bridge import audit_adapter


def _cfg(tmp_path: Path) -> dict:
    return {
        "app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"},
        "paths": {"audit_jsonl": str(tmp_path / "data" / "audit" / "portfolio_audit.jsonl")},
    }


def test_build_audit_payload_contains_expected_fields(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    payload = audit_adapter.build_audit_payload(
        {
            "ticket_id": "VF-1",
            "source_proposal_id": "PWV2-1",
            "asset": {"symbol": "AMD", "name": "Advanced Micro Devices"},
            "status": "EXECUTED",
            "decision": "APPROVED",
            "buy_price": 257.1,
            "size_eur": 875.0,
            "timestamp": "2026-03-09T22:00:00+01:00",
        },
        {"exit_reason": "MANUAL_EXIT"},
    )

    assert payload == {
        "ticket_id": "VF-1",
        "source_proposal_id": "PWV2-1",
        "asset": {"symbol": "AMD", "name": "Advanced Micro Devices"},
        "status": "EXECUTED",
        "decision": "APPROVED",
        "buy_price": 257.1,
        "size_eur": 875.0,
        "exit_price": None,
        "exit_reason": "MANUAL_EXIT",
        "closed_fraction": None,
        "realized_pnl_eur": None,
        "realized_pnl_pct": None,
        "timestamp": "2026-03-09T22:00:00+01:00",
    }
    assert cfg["paths"]["audit_jsonl"].endswith("portfolio_audit.jsonl")


def test_emit_ticket_event_falls_back_when_official_adapter_unavailable(tmp_path: Path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    monkeypatch.setattr(audit_adapter, "_append_audit_event", None)

    result = audit_adapter.emit_ticket_event(
        "TRADE_DEFERRED",
        {
            "ticket_id": "VF-1",
            "source_proposal_id": "PWV2-1",
            "asset": {"symbol": "AMD"},
            "status": "DEFERRED",
            "timestamp": "2026-03-09T22:00:00+01:00",
        },
        cfg,
    )

    assert result["status"] == "fallback"
    assert result["event_type"] == "TRADE_DEFERRED"
    assert result["ref"]
    path = Path(result["path"])
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rows[-1]["event_type"] == "TRADE_DEFERRED"
    assert rows[-1]["status"] == "DEFERRED"
