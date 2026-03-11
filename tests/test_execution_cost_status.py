from __future__ import annotations

from pathlib import Path

from modules.common.utils import write_json
from modules.virus_bridge.cost_status import build_cost_status


def _cfg(tmp_path: Path) -> dict:
    return {
        "app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"},
        "organism_evaluation": {"monthly_cost_usd": 30, "eurusd_rate_assumption": 0.92},
    }


def _execution(tmp_path: Path, ticket_id: str, executed_at: str = "2026-03-10T09:00:00+01:00") -> None:
    write_json(
        tmp_path / "data" / "virus_bridge" / "executions" / "20260310" / f"execution_{ticket_id}.json",
        {"ticket_id": ticket_id, "status": "EXECUTED", "buy_price": 100.0, "size_eur": 1000.0, "executed_at": executed_at},
    )
    write_json(
        tmp_path / "data" / "virus_bridge" / "ticket_state.json",
        {"tickets": {ticket_id: {"status": "EXECUTED", "entry_price": 100.0, "entry_size_eur": 1000.0, "remaining_size_eur": 1000.0}}},
    )


def _ticket(tmp_path: Path, ticket_id: str) -> None:
    write_json(
        tmp_path / "data" / "virus_bridge" / "trade_candidates" / "20260310" / f"ticket_{ticket_id}.json",
        {"ticket_id": ticket_id, "asset": {"symbol": "AMD", "isin": "ISIN-AMD", "name": "Advanced Micro Devices"}, "direction": "long", "timestamp": "2026-03-10T09:00:00+01:00"},
    )


def _exit(tmp_path: Path, ticket_id: str, pnl_eur: float, ts: str = "2026-03-10T11:00:00+01:00") -> None:
    stamp = ts.replace("-", "").replace(":", "").replace("T", "_").replace("+01:00", "")
    write_json(
        tmp_path / "data" / "virus_bridge" / "exits" / "20260310" / f"exit_{ticket_id}_{stamp}.json",
        {"ticket_id": ticket_id, "exit_type": "FULL", "exit_reason": "MANUAL_EXIT", "exit_price": 110.0, "size_eur": 1000.0, "realized_pnl_eur": pnl_eur, "timestamp": ts},
    )


def test_cost_status_without_manual_activity_is_not_yet_evaluable(tmp_path: Path) -> None:
    status = build_cost_status(_cfg(tmp_path), "2026-03")

    assert status["cost_coverage_status"] == "NOCH_NICHT_BEWERTBAR"
    assert status["realized_pnl_before_costs"] == 0.0


def test_cost_status_near_break_even_when_realized_pnl_is_close_to_cost_hurdle(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _ticket(tmp_path, "VF-1")
    _execution(tmp_path, "VF-1")
    _exit(tmp_path, "VF-1", 25.0)

    status = build_cost_status(cfg, "2026-03")

    assert status["realized_pnl_before_costs"] == 25.0
    assert status["realized_pnl_after_costs"] == -2.6
    assert status["cost_coverage_status"] == "NAHE_BREAK_EVEN"


def test_cost_status_is_covered_when_realized_pnl_clears_monthly_costs(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _ticket(tmp_path, "VF-2")
    _execution(tmp_path, "VF-2")
    _exit(tmp_path, "VF-2", 40.0)

    status = build_cost_status(cfg, "2026-03")

    assert status["realized_pnl_after_costs"] == 12.4
    assert status["cost_coverage_status"] == "KOSTEN_GEDECKT"


def test_cost_status_is_not_covered_when_realized_pnl_is_negative(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _ticket(tmp_path, "VF-3")
    _execution(tmp_path, "VF-3")
    _exit(tmp_path, "VF-3", -10.0)

    status = build_cost_status(cfg, "2026-03")

    assert status["realized_pnl_after_costs"] == -37.6
    assert status["cost_coverage_status"] == "NICHT_GEDECKT"


def test_cost_status_with_incomplete_exit_data_stays_not_yet_evaluable(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _ticket(tmp_path, "VF-4")
    _execution(tmp_path, "VF-4")
    write_json(
        tmp_path / "data" / "virus_bridge" / "exits" / "20260310" / "exit_VF-4_20260310_110000.json",
        {"ticket_id": "VF-4", "exit_type": "FULL", "exit_reason": "MANUAL_EXIT", "exit_price": 110.0, "size_eur": 1000.0, "timestamp": "2026-03-10T11:00:00+01:00"},
    )

    status = build_cost_status(cfg, "2026-03")

    assert status["realized_pnl_before_costs"] is None
    assert status["realized_pnl_after_costs"] is None
    assert status["realized_pnl_complete"] is False
    assert status["cost_coverage_status"] == "NOCH_NICHT_BEWERTBAR"
