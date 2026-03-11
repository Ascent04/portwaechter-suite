from __future__ import annotations

from pathlib import Path

from modules.common.utils import write_json
from modules.virus_bridge.execution_report import build_execution_report, render_execution_summary


def _cfg(tmp_path: Path) -> dict:
    return {
        "app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"},
        "v2": {"data_dir": "data/v2"},
        "data_quality": {"max_quote_age_minutes": 30},
    }


def _ticket(tmp_path: Path, ticket_id: str, symbol: str, name: str, last_price: float | None = 100.0) -> None:
    write_json(
        tmp_path / "data" / "virus_bridge" / "trade_candidates" / "20260310" / f"ticket_{ticket_id}.json",
        {"ticket_id": ticket_id, "asset": {"symbol": symbol, "isin": f"ISIN-{symbol}", "name": name}, "direction": "long", "last_price": last_price, "currency": "USD", "timestamp": "2026-03-10T10:00:00+01:00"},
    )


def _execution(tmp_path: Path, ticket_id: str, buy_price: float, size_eur: float, executed_at: str = "2026-03-10T09:00:00+01:00") -> None:
    write_json(
        tmp_path / "data" / "virus_bridge" / "executions" / "20260310" / f"execution_{ticket_id}.json",
        {"ticket_id": ticket_id, "status": "EXECUTED", "buy_price": buy_price, "size_eur": size_eur, "executed_at": executed_at},
    )


def _state(tmp_path: Path, rows: dict[str, dict]) -> None:
    write_json(tmp_path / "data" / "virus_bridge" / "ticket_state.json", {"tickets": rows})


def _exit(tmp_path: Path, ticket_id: str, exit_type: str, exit_price: float, size_eur: float, pnl_eur: float, ts: str) -> None:
    stamp = ts.replace("-", "").replace(":", "").replace("T", "_").replace("+01:00", "")
    write_json(
        tmp_path / "data" / "virus_bridge" / "exits" / "20260310" / f"exit_{ticket_id}_{stamp}.json",
        {
            "ticket_id": ticket_id,
            "exit_type": exit_type,
            "exit_reason": "MANUAL_EXIT",
            "exit_price": exit_price,
            "size_eur": size_eur,
            "realized_pnl_eur": pnl_eur,
            "realized_pnl_pct": (pnl_eur / size_eur) * 100 if size_eur else 0,
            "timestamp": ts,
        },
    )


def _quotes(tmp_path: Path, rows: list[dict]) -> None:
    write_json(tmp_path / "data" / "v2" / "candidates_20260310_1000.json", {"generated_at": "2026-03-10T10:00:00+01:00", "candidates": rows})


def test_execution_status_v1_only_open_positions_has_zero_realized(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _ticket(tmp_path, "VF-1", "AMD", "Advanced Micro Devices")
    _execution(tmp_path, "VF-1", 100.0, 1000.0)
    _state(tmp_path, {"VF-1": {"status": "EXECUTED", "entry_price": 100.0, "entry_size_eur": 1000.0, "remaining_size_eur": 1000.0}})
    _quotes(tmp_path, [{"symbol": "AMD", "isin": "ISIN-AMD", "quote": {"price": 105.0, "currency": "USD", "timestamp": "2026-03-10T10:00:00+01:00"}}])

    report = build_execution_report(cfg)

    assert report["open_positions_count"] == 1
    assert report["closed_positions_count"] == 0
    assert report["partial_exit_count"] == 0
    assert report["realized_pnl_eur"] == 0.0
    assert report["unrealized_pnl_eur"] == 50.0


def test_execution_status_v1_closed_trade_counts_and_realized_pnl(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _ticket(tmp_path, "VF-2", "ANET", "Arista Networks")
    _execution(tmp_path, "VF-2", 50.0, 1000.0)
    _state(tmp_path, {"VF-2": {"status": "CLOSED", "entry_price": 50.0, "entry_size_eur": 1000.0, "remaining_size_eur": 0.0}})
    _exit(tmp_path, "VF-2", "FULL", 55.0, 1000.0, 100.0, "2026-03-10T11:00:00+01:00")

    report = build_execution_report(cfg)

    assert report["open_positions_count"] == 0
    assert report["closed_positions_count"] == 1
    assert report["realized_pnl_eur"] == 100.0
    assert report["closed_trades"][0]["average_exit_price"] == 55.0


def test_execution_status_v1_partial_exit_keeps_rest_open(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _ticket(tmp_path, "VF-3", "BAYN.DE", "Bayer AG")
    _execution(tmp_path, "VF-3", 100.0, 1000.0)
    _state(tmp_path, {"VF-3": {"status": "PARTIALLY_CLOSED", "entry_price": 100.0, "entry_size_eur": 1000.0, "remaining_size_eur": 600.0}})
    _exit(tmp_path, "VF-3", "PARTIAL", 110.0, 400.0, 40.0, "2026-03-10T11:30:00+01:00")
    _quotes(tmp_path, [{"symbol": "BAYN.DE", "isin": "ISIN-BAYN.DE", "quote": {"price": 105.0, "currency": "EUR", "timestamp": "2026-03-10T12:00:00+01:00"}}])

    report = build_execution_report(cfg)

    assert report["open_positions_count"] == 1
    assert report["partial_exit_count"] == 1
    assert report["closed_positions_count"] == 0
    assert report["realized_pnl_eur"] == 40.0
    assert report["unrealized_pnl_eur"] == 30.0


def test_execution_status_v1_mixed_trades_do_not_double_count(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _ticket(tmp_path, "VF-4", "AMD", "Advanced Micro Devices")
    _ticket(tmp_path, "VF-5", "ANET", "Arista Networks")
    _ticket(tmp_path, "VF-6", "BAYN.DE", "Bayer AG")
    _execution(tmp_path, "VF-4", 100.0, 1000.0)
    _execution(tmp_path, "VF-5", 50.0, 1000.0)
    _execution(tmp_path, "VF-6", 80.0, 800.0)
    _state(
        tmp_path,
        {
            "VF-4": {"status": "EXECUTED", "entry_price": 100.0, "entry_size_eur": 1000.0, "remaining_size_eur": 1000.0},
            "VF-5": {"status": "PARTIALLY_CLOSED", "entry_price": 50.0, "entry_size_eur": 1000.0, "remaining_size_eur": 500.0},
            "VF-6": {"status": "CLOSED", "entry_price": 80.0, "entry_size_eur": 800.0, "remaining_size_eur": 0.0},
        },
    )
    _exit(tmp_path, "VF-5", "PARTIAL", 55.0, 500.0, 50.0, "2026-03-10T11:30:00+01:00")
    _exit(tmp_path, "VF-6", "FULL", 72.0, 800.0, -80.0, "2026-03-10T12:00:00+01:00")
    _quotes(
        tmp_path,
        [
            {"symbol": "AMD", "isin": "ISIN-AMD", "quote": {"price": 102.0, "currency": "USD", "timestamp": "2026-03-10T12:00:00+01:00"}},
            {"symbol": "ANET", "isin": "ISIN-ANET", "quote": {"price": 56.0, "currency": "USD", "timestamp": "2026-03-10T12:00:00+01:00"}},
        ],
    )

    report = build_execution_report(cfg)

    assert report["summary"]["executed_total"] == 3
    assert report["open_positions_count"] == 2
    assert report["partial_exit_count"] == 1
    assert report["closed_positions_count"] == 1
    assert report["realized_pnl_eur"] == -30.0


def test_execution_status_v1_unpriced_open_positions_do_not_fake_unrealized(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _ticket(tmp_path, "VF-7", "MSFT", "Microsoft", last_price=None)
    _execution(tmp_path, "VF-7", 100.0, 1000.0)
    _state(tmp_path, {"VF-7": {"status": "EXECUTED", "entry_price": 100.0, "entry_size_eur": 1000.0, "remaining_size_eur": 1000.0}})

    report = build_execution_report(cfg)
    text = render_execution_summary(cfg)

    assert report["unrealized_pnl_eur"] is None
    assert report["total_pnl_eur"] is None
    assert "Unrealisierte PnL:\nnicht belastbar verfuegbar" in text
    assert "kein belastbarer Marktpreis" in text
