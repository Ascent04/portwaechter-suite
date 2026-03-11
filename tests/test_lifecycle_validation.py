from __future__ import annotations

from pathlib import Path

from modules.common.utils import write_json
from modules.virus_bridge.lifecycle import validate_all_lifecycles, validate_lifecycle


def _cfg(tmp_path: Path) -> dict:
    return {"app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"}}


def test_validate_lifecycle_detects_close_without_executed(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    write_json(
        tmp_path / "data" / "virus_bridge" / "ticket_lifecycle" / "VF-20260309-2200-001.json",
        {
            "ticket_id": "VF-20260309-2200-001",
            "source_proposal_id": "PWV2-1",
            "asset": {"symbol": "AMD"},
            "created_at": "2026-03-09T22:00:00+01:00",
            "events": [
                {
                    "event_type": "TRADE_CANDIDATE_CREATED",
                    "timestamp": "2026-03-09T22:00:00+01:00",
                    "data": {"ticket_id": "VF-20260309-2200-001"},
                    "audit_ref": "audit-1",
                },
                {
                    "event_type": "TRADE_CLOSED_MANUAL",
                    "timestamp": "2026-03-09T22:10:00+01:00",
                    "data": {"ticket_id": "VF-20260309-2200-001", "status": "CLOSED"},
                    "audit_ref": "audit-2",
                },
            ],
        },
    )

    result = validate_lifecycle("VF-20260309-2200-001", cfg)
    summary = validate_all_lifecycles(cfg)

    assert result["ok"] is False
    assert "closed_before_executed" in result["errors"]
    assert summary["ok"] is False
    assert summary["invalid"] == 1
