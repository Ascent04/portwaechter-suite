from __future__ import annotations

from pathlib import Path

from modules.common.utils import write_json
from modules.virus_bridge.execution_report import build_execution_report


def _cfg(tmp_path: Path) -> dict:
    return {
        "app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"},
        "v2": {"data_dir": "data/v2"},
        "data_quality": {"max_quote_age_minutes": 30},
        "organism_evaluation": {"monthly_cost_usd": 30, "eurusd_rate_assumption": 0.92},
    }


def _ticket(tmp_path: Path, ticket_id: str, symbol: str, name: str) -> None:
    write_json(
        tmp_path / "data" / "virus_bridge" / "trade_candidates" / "20260310" / f"ticket_{ticket_id}.json",
        {"ticket_id": ticket_id, "asset": {"symbol": symbol, "isin": f"ISIN-{symbol}", "name": name}, "direction": "long", "timestamp": "2026-03-10T09:00:00+01:00"},
    )


def _execution(tmp_path: Path, ticket_id: str, buy_price: float = 100.0, size_eur: float = 1000.0) -> None:
    write_json(
        tmp_path / "data" / "virus_bridge" / "executions" / "20260310" / f"execution_{ticket_id}.json",
        {"ticket_id": ticket_id, "status": "EXECUTED", "buy_price": buy_price, "size_eur": size_eur, "executed_at": "2026-03-10T09:00:00+01:00"},
    )


def _state(tmp_path: Path, rows: dict[str, dict]) -> None:
    write_json(tmp_path / "data" / "virus_bridge" / "ticket_state.json", {"tickets": rows})


def _exit(tmp_path: Path, ticket_id: str, ts: str, *, exit_type: str, exit_price: float | None, size_eur: float | None, pnl_eur: float | None, reason: str) -> None:
    stamp = ts.replace("-", "").replace(":", "").replace("T", "_").replace("+01:00", "")
    payload = {"ticket_id": ticket_id, "exit_type": exit_type, "exit_reason": reason, "timestamp": ts}
    if exit_price is not None:
        payload["exit_price"] = exit_price
    if size_eur is not None:
        payload["size_eur"] = size_eur
    if pnl_eur is not None:
        payload["realized_pnl_eur"] = pnl_eur
    write_json(tmp_path / "data" / "virus_bridge" / "exits" / "20260310" / f"exit_{ticket_id}_{stamp}.json", payload)


def _quotes(tmp_path: Path, rows: list[dict]) -> None:
    write_json(tmp_path / "data" / "v2" / "candidates_20260310_1200.json", {"generated_at": "2026-03-10T12:00:00+01:00", "candidates": rows})


def test_partial_exit_keeps_ticket_open_and_counts_only_realized_part(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _ticket(tmp_path, "VF-A", "AMD", "Advanced Micro Devices")
    _execution(tmp_path, "VF-A")
    _state(tmp_path, {"VF-A": {"status": "PARTIALLY_CLOSED", "entry_price": 100.0, "entry_size_eur": 1000.0, "remaining_size_eur": 600.0}})
    _exit(tmp_path, "VF-A", "2026-03-10T10:00:00+01:00", exit_type="PARTIAL", exit_price=110.0, size_eur=400.0, pnl_eur=40.0, reason="PARTIAL_TAKE_PROFIT")
    _quotes(tmp_path, [{"symbol": "AMD", "isin": "ISIN-AMD", "quote": {"price": 105.0, "currency": "USD", "timestamp": "2026-03-10T12:00:00+01:00"}}])

    report = build_execution_report(cfg)

    assert report["open_positions_count"] == 1
    assert report["closed_positions_count"] == 0
    assert report["closed_trades"] == []
    assert report["partial_exit_count"] == 1
    assert report["realized_pnl_eur"] == 40.0
    assert report["open_positions"][0]["status"] == "PARTIALLY_CLOSED"
    assert report["open_positions"][0]["remaining_quantity"] == 6.0
    assert report["open_positions"][0]["realized_pnl_eur"] == 40.0
    assert report["open_positions"][0]["has_partial_exits"] is True


def test_multiple_exit_parts_are_weighted_and_close_trade_cleanly(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _ticket(tmp_path, "VF-B", "ANET", "Arista Networks")
    _execution(tmp_path, "VF-B")
    _state(tmp_path, {"VF-B": {"status": "CLOSED", "entry_price": 100.0, "entry_size_eur": 1000.0, "remaining_size_eur": 0.0}})
    _exit(tmp_path, "VF-B", "2026-03-10T10:00:00+01:00", exit_type="PARTIAL", exit_price=110.0, size_eur=400.0, pnl_eur=40.0, reason="PARTIAL_TAKE_PROFIT")
    _exit(tmp_path, "VF-B", "2026-03-10T11:00:00+01:00", exit_type="PARTIAL", exit_price=120.0, size_eur=300.0, pnl_eur=60.0, reason="RISK_REDUCTION")
    _exit(tmp_path, "VF-B", "2026-03-10T12:00:00+01:00", exit_type="FULL", exit_price=90.0, size_eur=300.0, pnl_eur=-30.0, reason="TARGET_REACHED")

    report = build_execution_report(cfg)
    trade = report["closed_trades"][0]

    assert report["closed_positions_count"] == 1
    assert report["partial_exit_count"] == 2
    assert report["realized_pnl_eur"] == 70.0
    assert trade["entry_quantity"] == 10.0
    assert trade["exited_quantity_total"] == 10.0
    assert trade["remaining_quantity"] == 0.0
    assert trade["average_exit_price_weighted"] == 107.0
    assert trade["realized_pnl_eur"] == 70.0
    assert trade["closed_at"] == "2026-03-10T12:00:00+01:00"
    assert trade["weighted_exit_method"] is True
    assert trade["has_partial_exits"] is True


def test_exit_reason_prefers_explicit_exit_records_over_status_fallback(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _ticket(tmp_path, "VF-C", "BAYN.DE", "Bayer AG")
    _execution(tmp_path, "VF-C")
    _state(tmp_path, {"VF-C": {"status": "CLOSED", "entry_price": 100.0, "entry_size_eur": 1000.0, "remaining_size_eur": 0.0}})
    _exit(tmp_path, "VF-C", "2026-03-10T10:00:00+01:00", exit_type="PARTIAL", exit_price=110.0, size_eur=400.0, pnl_eur=40.0, reason="PARTIAL_TAKE_PROFIT")
    _exit(tmp_path, "VF-C", "2026-03-10T11:00:00+01:00", exit_type="FULL", exit_price=95.0, size_eur=600.0, pnl_eur=-30.0, reason="STOP_LOSS")

    report = build_execution_report(cfg)
    trade = report["closed_trades"][0]

    assert trade["exit_reason"] == "Stop-Loss"
    assert trade["exit_reason_quality"] == "MITTEL"
    assert trade["lifecycle_status"] == "CLOSED"


def test_mixed_positions_do_not_double_count_open_partial_and_closed_rows(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _ticket(tmp_path, "VF-D1", "AMD", "Advanced Micro Devices")
    _ticket(tmp_path, "VF-D2", "ANET", "Arista Networks")
    _ticket(tmp_path, "VF-D3", "BAYN.DE", "Bayer AG")
    _execution(tmp_path, "VF-D1")
    _execution(tmp_path, "VF-D2")
    _execution(tmp_path, "VF-D3", buy_price=80.0, size_eur=800.0)
    _state(
        tmp_path,
        {
            "VF-D1": {"status": "EXECUTED", "entry_price": 100.0, "entry_size_eur": 1000.0, "remaining_size_eur": 1000.0},
            "VF-D2": {"status": "PARTIALLY_CLOSED", "entry_price": 100.0, "entry_size_eur": 1000.0, "remaining_size_eur": 600.0},
            "VF-D3": {"status": "CLOSED", "entry_price": 80.0, "entry_size_eur": 800.0, "remaining_size_eur": 0.0},
        },
    )
    _exit(tmp_path, "VF-D2", "2026-03-10T10:00:00+01:00", exit_type="PARTIAL", exit_price=110.0, size_eur=400.0, pnl_eur=40.0, reason="PARTIAL_TAKE_PROFIT")
    _exit(tmp_path, "VF-D3", "2026-03-10T11:00:00+01:00", exit_type="FULL", exit_price=72.0, size_eur=800.0, pnl_eur=-80.0, reason="STOP_LOSS")
    _quotes(
        tmp_path,
        [
            {"symbol": "AMD", "isin": "ISIN-AMD", "quote": {"price": 102.0, "currency": "USD", "timestamp": "2026-03-10T12:00:00+01:00"}},
            {"symbol": "ANET", "isin": "ISIN-ANET", "quote": {"price": 105.0, "currency": "USD", "timestamp": "2026-03-10T12:00:00+01:00"}},
        ],
    )

    report = build_execution_report(cfg)

    assert report["summary"]["executed_total"] == 3
    assert report["open_positions_count"] == 2
    assert report["closed_positions_count"] == 1
    assert report["partial_exit_count"] == 1
    assert len(report["open_positions"]) == 2
    assert len(report["closed_trades"]) == 1
    assert report["realized_pnl_eur"] == -40.0
    assert report["unrealized_pnl_eur"] == 50.0


def test_incomplete_exit_data_falls_back_defensively_without_fantasy_values(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _ticket(tmp_path, "VF-E", "MSFT", "Microsoft")
    _execution(tmp_path, "VF-E")
    _state(tmp_path, {"VF-E": {"status": "CLOSED", "entry_price": 100.0, "entry_size_eur": 1000.0, "remaining_size_eur": 0.0}})
    _exit(tmp_path, "VF-E", "2026-03-10T11:00:00+01:00", exit_type="FULL", exit_price=None, size_eur=1000.0, pnl_eur=None, reason="MANUAL_EXIT")

    report = build_execution_report(cfg)
    trade = report["closed_trades"][0]

    assert trade["average_exit_price_weighted"] is None
    assert trade["realized_pnl_eur"] is None
    assert trade["exit_reason"] == "Manuell"
    assert trade["exit_reason_quality"] == "HOCH"
    assert trade["weighted_exit_method"] is False
    assert report["realized_pnl_eur"] is None
    assert any("nicht voll belastbar" in note for note in report["notes"])
