from __future__ import annotations

import json
from pathlib import Path

from modules.virus_bridge import audit_adapter


def _cfg(tmp_path: Path) -> dict:
    return {
        "app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"},
        "paths": {"audit_jsonl": str(tmp_path / "data" / "audit" / "portfolio_audit.jsonl")},
    }


def _payload() -> dict:
    return {
        "ticket_id": "VF-20260309-2200-001",
        "source_proposal_id": "PWV2-20260309-2200-001",
        "asset": {"symbol": "AMD", "isin": "US0079031078", "name": "Advanced Micro Devices"},
        "decision": "APPROVED",
        "status": "OPEN",
        "timestamp": "2026-03-09T22:00:00+01:00",
    }


def test_emit_ticket_event_uses_official_audit_path(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)

    result = audit_adapter.emit_ticket_event("TRADE_CANDIDATE_CREATED", _payload(), cfg)

    assert result["ok"] is True
    assert result["mode"] == "official"
    audit_path = Path(result["path"])
    assert audit_path.exists()
    rows = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rows[-1]["event_type"] == "TRADE_CANDIDATE_CREATED"
    assert rows[-1]["ticket_id"] == "VF-20260309-2200-001"


def test_emit_ticket_event_falls_back_when_official_adapter_unavailable(tmp_path: Path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    monkeypatch.setattr(audit_adapter, "_append_audit_event", None)

    result = audit_adapter.emit_ticket_event("TRADE_DEFERRED", {**_payload(), "status": "DEFERRED"}, cfg)

    assert result["ok"] is True
    assert result["mode"] == "fallback"
    fallback_path = Path(result["path"])
    assert fallback_path.exists()
    rows = [json.loads(line) for line in fallback_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rows[-1]["event_type"] == "TRADE_DEFERRED"
    assert rows[-1]["status"] == "DEFERRED"
