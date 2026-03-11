from __future__ import annotations

from pathlib import Path

from modules.common.utils import read_json, write_json
from modules.telegram_commands import poller
from modules.virus_bridge.execution_performance import (
    compute_closed_trade_returns,
    compute_open_trade_mark_to_market,
    load_executed_tickets,
    write_execution_report,
)


def _cfg(tmp_path: Path) -> dict:
    return {
        "app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"},
        "notify": {"telegram": {"enabled": True, "bot_token_env": "TG_BOT_TOKEN", "chat_id_env": "TG_CHAT_ID"}},
        "telegram_commands": {
            "enabled": True,
            "allowed_chat_ids_env": "TG_CHAT_ID",
            "state_file": "data/telegram/command_state.json",
            "inbox_jsonl": "data/telegram/inbox_YYYYMMDD.jsonl",
            "actions_jsonl": "data/telegram/actions_YYYYMMDD.jsonl",
        },
        "v2": {"data_dir": "data/v2"},
    }


def _write_trade_ticket(tmp_path: Path, ticket_id: str, symbol: str, name: str, last_price: float) -> None:
    write_json(
        tmp_path / "data" / "virus_bridge" / "trade_candidates" / "20260309" / f"ticket_{ticket_id}.json",
        {
            "ticket_id": ticket_id,
            "source_proposal_id": f"PWV2-{ticket_id}",
            "asset": {"symbol": symbol, "isin": f"ISIN-{symbol}", "name": name},
            "direction": "long",
            "last_price": last_price,
            "currency": "USD",
            "decision": "APPROVED",
            "signal_strength": "hoch",
            "market_regime": "positiv",
            "score": 7.0,
            "reasons": ["Momentum"],
            "risk_flags": [],
            "size_min_eur": 1000,
            "size_max_eur": 1500,
            "suggested_eur": 1000,
            "entry_hint": "Einstieg beobachten",
            "stop_hint": "Stop-Idee beobachten",
            "next_step": "Trade-Ticket manuell pruefen",
            "timestamp": "2026-03-09T22:00:00+01:00",
        },
    )


def _write_execution(tmp_path: Path, ticket_id: str, buy_price: float, size_eur: float) -> None:
    write_json(
        tmp_path / "data" / "virus_bridge" / "executions" / "20260309" / f"execution_{ticket_id}.json",
        {
            "ticket_id": ticket_id,
            "status": "EXECUTED",
            "buy_price": buy_price,
            "size_eur": size_eur,
            "executed_at": "2026-03-09T22:05:00+01:00",
            "source": "telegram_manual",
        },
    )


def test_execution_performance_open_and_closed_trades(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    open_ticket = "VF-20260309-2200-001"
    closed_ticket = "VF-20260309-2200-002"
    _write_trade_ticket(tmp_path, open_ticket, "AMD", "Advanced Micro Devices", 103.0)
    _write_trade_ticket(tmp_path, closed_ticket, "ANET", "Arista Networks Inc.", 48.0)
    _write_execution(tmp_path, open_ticket, 100.0, 1000.0)
    _write_execution(tmp_path, closed_ticket, 50.0, 1000.0)

    write_json(
        tmp_path / "data" / "virus_bridge" / "ticket_state.json",
        {
            "tickets": {
                open_ticket: {"status": "EXECUTED", "last_updated": "2026-03-09T22:05:00+01:00", "awaiting_input": None},
                closed_ticket: {"status": "CLOSED", "last_updated": "2026-03-09T23:00:00+01:00", "awaiting_input": None},
            }
        },
    )
    write_json(
        tmp_path / "data" / "virus_bridge" / "ticket_lifecycle" / f"{closed_ticket}.json",
        {
            "ticket_id": closed_ticket,
            "source_proposal_id": f"PWV2-{closed_ticket}",
            "asset": {"symbol": "ANET", "isin": "ISIN-ANET", "name": "Arista Networks Inc."},
            "created": None,
            "executed": {"event_type": "TRADE_EXECUTED_MANUAL", "timestamp": "2026-03-09T22:05:00+01:00", "buy_price": 50.0, "size_eur": 1000.0},
            "rejected": None,
            "deferred": None,
            "closed": {"event_type": "TRADE_CLOSED_MANUAL", "timestamp": "2026-03-09T23:00:00+01:00", "status": "CLOSED", "exit_price": 45.0},
            "audit_refs": [],
        },
    )
    write_json(
        tmp_path / "data" / "v2" / "candidates_20260309_2300.json",
        {
            "generated_at": "2026-03-09T23:00:00+01:00",
            "candidates": [
                {"symbol": "AMD", "isin": "ISIN-AMD", "quote": {"price": 110.0, "currency": "USD", "timestamp": "2026-03-09T23:00:00+01:00"}},
                {"symbol": "ANET", "isin": "ISIN-ANET", "quote": {"price": 47.0, "currency": "USD", "timestamp": "2026-03-09T23:00:00+01:00"}},
            ],
        },
    )

    executed = load_executed_tickets(cfg)
    open_rows = compute_open_trade_mark_to_market(cfg)
    closed_rows = compute_closed_trade_returns(cfg)
    result = write_execution_report(cfg)

    assert len(executed) == 2
    assert len(open_rows) == 1
    assert len(closed_rows) == 1
    assert open_rows[0]["ticket_id"] == open_ticket
    assert open_rows[0]["current_price"] == 110.0
    assert open_rows[0]["pnl_pct"] == 10.0
    assert open_rows[0]["pnl_eur"] == 100.0
    assert closed_rows[0]["ticket_id"] == closed_ticket
    assert closed_rows[0]["current_price"] == 45.0
    assert closed_rows[0]["pnl_pct"] == -10.0
    assert closed_rows[0]["pnl_eur"] == -100.0

    report = result["report"]
    assert Path(result["path"]).exists()
    assert report["summary"]["executed_total"] == 2
    assert report["summary"]["open_total"] == 1
    assert report["summary"]["closed_total"] == 1
    assert report["summary"]["avg_open_pnl_pct"] == 10.0
    assert report["summary"]["avg_closed_pnl_pct"] == -10.0
    assert report["summary"]["win_rate_closed"] == 0.0

    saved = read_json(Path(result["path"]))
    assert saved["summary"]["executed_total"] == 2


def test_execution_command_shows_short_summary(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    ticket_id = "VF-20260309-2200-003"
    _write_trade_ticket(tmp_path, ticket_id, "AMD", "Advanced Micro Devices", 105.0)
    _write_execution(tmp_path, ticket_id, 100.0, 1000.0)
    write_json(
        tmp_path / "data" / "virus_bridge" / "ticket_state.json",
        {"tickets": {ticket_id: {"status": "EXECUTED", "last_updated": "2026-03-09T22:05:00+01:00", "awaiting_input": None}}},
    )
    write_json(
        tmp_path / "data" / "v2" / "candidates_20260309_2305.json",
        {"generated_at": "2026-03-09T23:05:00+01:00", "candidates": [{"symbol": "AMD", "isin": "ISIN-AMD", "quote": {"price": 105.0, "currency": "USD"}}]},
    )

    text, action = poller.handle_command({"normalized_text": "/execution", "chat_id": "123"}, cfg)

    assert action["action"] == "execution"
    assert "CB Fund Desk - Ausfuehrungsstand" in text
    assert "Echte Ausfuehrungen:\n1" in text
    assert "Offene Positionen:\n1" in text
    assert "Unrealisierte PnL:\n+50,00 EUR" in text
