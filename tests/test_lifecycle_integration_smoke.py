from __future__ import annotations

from pathlib import Path

from modules.common.utils import read_json, write_json
from modules.virus_bridge import main as vb_main
from modules.virus_bridge.execution_workflow import (
    handle_pending_ticket_input,
    handle_ticket_action,
    render_ticket_command_text,
)


def _cfg(tmp_path: Path) -> dict:
    return {
        "app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"},
        "notifications": {"quiet_hours": {"enabled": False}},
        "notify": {"telegram": {"enabled": True, "bot_token_env": "TG_BOT_TOKEN", "chat_id_env": "TG_CHAT_ID"}},
        "integration": {"bridge": {"proposal_dir": "data/integration/signal_proposals", "consumed_dir": "data/integration/consumed"}},
        "paths": {"audit_jsonl": str(tmp_path / "data" / "audit" / "portfolio_audit.jsonl")},
        "virus_bridge": {"tr_universe_path": "config/universe_tr_verified.json"},
        "hedgefund": {
            "budget_eur": 5000,
            "max_positions": 3,
            "max_risk_per_trade_pct": 1.0,
            "max_total_exposure_pct": 60,
            "sizing": {
                "high_conf_min_eur": 1000,
                "high_conf_max_eur": 1500,
                "medium_conf_min_eur": 750,
                "medium_conf_max_eur": 1000,
                "speculative_min_eur": 0,
                "speculative_max_eur": 500,
            },
        },
    }


def _proposal() -> dict:
    return {
        "proposal_id": "PWV2-20260309-2110-001",
        "source": "portwaechter_v2",
        "asset": {"symbol": "BAYN.DE", "isin": "DE000BAY0017", "name": "Bayer AG"},
        "classification": "KAUFIDEE_PRUEFEN",
        "direction": "long",
        "quote": {"last_price": 25.0, "currency": "EUR", "percent_change": 2.7, "timestamp": "2026-03-09T09:10:00+01:00"},
        "score": 7.2,
        "signal_strength": "hoch",
        "market_regime": "positiv",
        "reasons": ["Momentum", "Ungewoehnlich hohes Volumen"],
        "portfolio_context": {"is_holding": False, "weight_pct": 0.0},
        "budget_context": {"budget_eur": 5000},
        "timestamp": "2026-03-09T09:10:00+01:00",
    }


def test_main_execution_and_exit_write_lifecycle_and_audit_refs(tmp_path: Path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    sent: list[dict] = []
    write_json(
        tmp_path / "config" / "universe_tr_verified.json",
        {
            "DE000BAY0017": {
                "symbol": "BAYN.DE",
                "name": "Bayer AG",
                "tr_verified": True,
                "asset_type": "stock",
                "market": "XETRA",
                "currency": "EUR",
            }
        },
    )
    write_json(
        tmp_path / "data" / "integration" / "signal_proposals" / "20260309" / "proposal_PWV2-20260309-2110-001.json",
        _proposal(),
    )
    monkeypatch.setenv("TG_BOT_TOKEN", "token")
    monkeypatch.setenv("TG_CHAT_ID", "-123")
    monkeypatch.setattr(
        vb_main,
        "send_message_result",
        lambda token, chat_id, text, cfg, keyboard_rows=None: sent.append({"text": text, "rows": keyboard_rows}) or {"ok": True, "message_id": 42, "reason": "ok"},
    )

    result = vb_main.run(cfg)
    ticket_path = Path(result["written_paths"][0])
    ticket = read_json(ticket_path)
    ticket_id = ticket["ticket_id"]

    handle_ticket_action(f"BOUGHT:{ticket_id}", "123", cfg)
    handle_pending_ticket_input("25", "123", cfg)
    handle_pending_ticket_input("875", "123", cfg)
    handle_ticket_action(f"PARTIAL_EXIT:{ticket_id}", "123", cfg)
    handle_pending_ticket_input("27.5", "123", cfg)
    handle_pending_ticket_input("300", "123", cfg)
    handle_pending_ticket_input("1", "123", cfg)
    handle_pending_ticket_input("-", "123", cfg)

    lifecycle = read_json(tmp_path / "data" / "virus_bridge" / "ticket_lifecycle" / f"{ticket_id}.json")
    event_types = [row["event_type"] for row in lifecycle["events"]]
    detail_text, _ = render_ticket_command_text(ticket_id, cfg)

    assert sent
    assert "TRADE_CANDIDATE_CREATED" in event_types
    assert "TRADE_TICKET_SENT" in event_types
    assert "TRADE_EXECUTED_MANUAL" in event_types
    assert "TRADE_PARTIAL_EXIT" in event_types
    assert lifecycle["current_status"] == "PARTIALLY_CLOSED"
    assert len([row for row in lifecycle["audit_refs"] if row.get("ref")]) >= 4
    assert "Verlauf:" in detail_text
    assert "teilverkauft:" in detail_text
