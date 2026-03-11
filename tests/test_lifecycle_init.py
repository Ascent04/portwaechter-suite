from __future__ import annotations

from pathlib import Path

from modules.common.utils import read_json
from modules.virus_bridge.lifecycle import init_lifecycle


def _cfg(tmp_path: Path) -> dict:
    return {"app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"}}


def test_init_lifecycle_writes_initial_file(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    lifecycle = init_lifecycle(
        {
            "ticket_id": "VF-20260309-2200-001",
            "source_proposal_id": "PWV2-20260309-2200-001",
            "asset": {"symbol": "AMD", "name": "Advanced Micro Devices"},
            "timestamp": "2026-03-09T22:00:00+01:00",
        },
        cfg,
    )

    assert lifecycle["ticket_id"] == "VF-20260309-2200-001"
    assert lifecycle["current_status"] == "CREATED"
    path = tmp_path / "data" / "virus_bridge" / "ticket_lifecycle" / "VF-20260309-2200-001.json"
    stored = read_json(path)
    assert stored["ticket_id"] == "VF-20260309-2200-001"
    assert stored["events"] == []
