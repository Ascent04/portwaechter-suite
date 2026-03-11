from __future__ import annotations

from pathlib import Path

from modules.common.utils import read_json, write_json
from modules.virus_bridge.execution_report import build_execution_report, render_execution_summary, write_execution_report


def _cfg(tmp_path: Path) -> dict:
    return {
        "app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"},
        "v2": {"data_dir": "data/v2"},
        "data_quality": {"max_quote_age_minutes": 30},
    }


def test_execution_report_is_written_with_positions_and_summary(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    ticket_id = "VF-1"
    write_json(
        tmp_path / "data" / "virus_bridge" / "trade_candidates" / "20260310" / f"ticket_{ticket_id}.json",
        {"ticket_id": ticket_id, "asset": {"symbol": "AMD", "isin": "ISIN-AMD", "name": "Advanced Micro Devices"}, "direction": "long", "last_price": 105.0, "currency": "USD", "timestamp": "2026-03-10T10:00:00+01:00"},
    )
    write_json(
        tmp_path / "data" / "virus_bridge" / "executions" / "20260310" / f"execution_{ticket_id}.json",
        {"ticket_id": ticket_id, "status": "EXECUTED", "buy_price": 100.0, "size_eur": 1000.0, "executed_at": "2026-03-10T09:00:00+01:00"},
    )
    write_json(
        tmp_path / "data" / "virus_bridge" / "ticket_state.json",
        {"tickets": {ticket_id: {"status": "EXECUTED", "entry_price": 100.0, "entry_size_eur": 1000.0, "remaining_size_eur": 1000.0}}},
    )
    write_json(
        tmp_path / "data" / "v2" / "candidates_20260310_1000.json",
        {"generated_at": "2026-03-10T10:00:00+01:00", "candidates": [{"symbol": "AMD", "isin": "ISIN-AMD", "quote": {"price": 105.0, "currency": "USD", "timestamp": "2026-03-10T10:00:00+01:00"}}]},
    )

    report = build_execution_report(cfg)
    path = write_execution_report(report, cfg)
    saved = read_json(path)
    text = render_execution_summary(cfg)

    assert Path(path).exists()
    assert saved["summary"]["executed_total"] == 1
    assert saved["open_positions"][0]["current_price"] == 105.0
    assert saved["open_positions_count"] == 1
    assert saved["realized_pnl_eur"] == 0.0
    assert saved["operating_cost_reference"]["amount_usd"] == 30.0
    assert saved["cost_coverage_status"] == "NICHT_GEDECKT"
    assert "CB Fund Desk - Ausfuehrungsstand" in text
    assert "Echte Ausfuehrungen:\n1" in text
    assert "Warnlage:\n- KOSTEN NICHT GEDECKT: Die laufende Kostenhuerde ist nicht gedeckt." in text
    assert "KOSTENSTATUS:" in text


def test_execution_report_warns_when_open_pnl_has_no_quotes(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    ticket_id = "VF-2"
    write_json(
        tmp_path / "data" / "virus_bridge" / "trade_candidates" / "20260310" / f"ticket_{ticket_id}.json",
        {"ticket_id": ticket_id, "asset": {"symbol": "AMD", "isin": "ISIN-AMD", "name": "Advanced Micro Devices"}, "direction": "long"},
    )
    write_json(
        tmp_path / "data" / "virus_bridge" / "executions" / "20260310" / f"execution_{ticket_id}.json",
        {"ticket_id": ticket_id, "status": "EXECUTED", "buy_price": 100.0, "size_eur": 1000.0, "executed_at": "2026-03-10T09:00:00+01:00"},
    )
    write_json(
        tmp_path / "data" / "virus_bridge" / "ticket_state.json",
        {"tickets": {ticket_id: {"status": "EXECUTED", "entry_price": 100.0, "entry_size_eur": 1000.0, "remaining_size_eur": 1000.0}}},
    )

    text = render_execution_summary(cfg)

    assert "VERALTET: Fehlende belastbare Quotes fuer offene PnL." in text
