from __future__ import annotations

from pathlib import Path

from modules.common.utils import read_json, write_json
from modules.organism.report_render import render_organism_text
from modules.virus_bridge import main as vb_main
from modules.virus_bridge.cost_status import build_cost_status
from modules.virus_bridge.execution_report import build_execution_report, render_execution_summary
from modules.virus_bridge.execution_workflow import handle_pending_ticket_input, handle_ticket_action
from modules.virus_bridge.exit_flow import load_exit_records
from modules.virus_bridge.lifecycle import load_lifecycle


def _cfg(tmp_path: Path) -> dict:
    return {
        "app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"},
        "notifications": {"quiet_hours": {"enabled": False}},
        "notify": {"telegram": {"enabled": True, "bot_token_env": "TG_BOT_TOKEN", "chat_id_env": "TG_CHAT_ID"}},
        "telegram_commands": {"allowed_chat_ids_env": "TG_CHAT_ID"},
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
        "data_quality": {"max_quote_age_minutes": 15},
        "organism_evaluation": {"monthly_cost_usd": 30, "eurusd_rate_assumption": 0.92},
        "v2": {"data_dir": "data/v2"},
    }


def _write_universe(tmp_path: Path) -> None:
    write_json(
        tmp_path / "config" / "universe_tr_verified.json",
        {
            "US0079031078": {
                "symbol": "AMD",
                "name": "Advanced Micro Devices",
                "tr_verified": True,
                "asset_type": "stock",
                "market": "NASDAQ",
                "currency": "USD",
            },
            "DE000BAY0017": {
                "symbol": "BAYN.DE",
                "name": "Bayer AG",
                "tr_verified": True,
                "asset_type": "stock",
                "market": "XETRA",
                "currency": "EUR",
            },
        },
    )


def _write_proposal(tmp_path: Path, proposal: dict, day: str = "20260310") -> None:
    proposal_id = str(proposal.get("proposal_id") or "PWV2-UNKNOWN-001")
    write_json(tmp_path / "data" / "integration" / "signal_proposals" / day / f"proposal_{proposal_id}.json", proposal)


def _write_recommendations(tmp_path: Path, rows: list[dict], stamp: str = "20260311_0900") -> None:
    write_json(tmp_path / "data" / "v2" / f"recommendations_{stamp}.json", {"recommendations": rows})


def _complete_proposal() -> dict:
    return {
        "proposal_id": "PWV2-20260310-1000-001",
        "source": "portwaechter_v2",
        "asset": {"symbol": "AMD", "isin": "US0079031078", "name": "Advanced Micro Devices"},
        "classification": "KAUFIDEE_PRUEFEN",
        "direction": "long",
        "score": 7.2,
        "signal_strength": "hoch",
        "market_regime": "positiv",
        "reasons": ["Momentum", "Relative Staerke"],
        "quote": {"last_price": 100.0, "currency": "USD", "percent_change": 2.7, "timestamp": "2026-03-10T16:00:00+01:00"},
        "portfolio_context": {"is_holding": False, "weight_pct": 0.0},
        "budget_context": {"budget_eur": 5000.0},
        "timestamp": "2026-03-10T16:00:00+01:00",
    }


def _incomplete_proposal() -> dict:
    return {
        "proposal_id": "PWV2-20260310-1010-001",
        "source": "portwaechter_v2",
        "asset": {"symbol": "BAYN.DE", "isin": "DE000BAY0017", "name": "Bayer AG"},
        "classification": "KAUFIDEE_PRUEFEN",
        "direction": "long",
        "score": 7.0,
        "signal_strength": "hoch",
        "market_regime": "positiv",
        "reasons": ["Momentum"],
        "quote": {"currency": "EUR", "timestamp": "2026-03-10T10:00:00+01:00"},
        "portfolio_context": {"is_holding": False, "weight_pct": 0.0},
        "budget_context": {"budget_eur": 5000.0},
        "timestamp": "2026-03-10T10:00:00+01:00",
    }


def _run_bridge(cfg: dict, monkeypatch) -> tuple[dict, list[dict]]:
    sent: list[dict] = []
    monkeypatch.setenv("TG_BOT_TOKEN", "token")
    monkeypatch.setenv("TG_CHAT_ID", "123")
    monkeypatch.setattr(
        vb_main,
        "send_message_result",
        lambda token, chat_id, text, cfg, keyboard_rows=None: sent.append({"text": text, "rows": keyboard_rows}) or {"ok": True, "message_id": 1, "reason": "ok"},
    )
    return vb_main.run(cfg), sent


def _load_ticket(path: str) -> dict:
    return read_json(Path(path))


def _buy(ticket_id: str, cfg: dict, price: str = "100", size_eur: str = "1000") -> None:
    text, _ = handle_ticket_action(f"BOUGHT:{ticket_id}", "123", cfg) or ("", {})
    assert "Zu welchem Kurs gekauft?" in text
    text, _ = handle_pending_ticket_input(price, "123", cfg) or ("", {})
    assert "Wie viel investiert?" in text
    text, _ = handle_pending_ticket_input(size_eur, "123", cfg) or ("", {})
    assert "Ausfuehrung gespeichert:" in text


def _partial_exit(ticket_id: str, cfg: dict, price: str = "110", size_eur: str = "400", reason: str = "1", note: str = "-") -> None:
    text, _ = handle_ticket_action(f"PARTIAL_EXIT:{ticket_id}", "123", cfg) or ("", {})
    assert "TEILVERKAUF:" in text
    text, _ = handle_pending_ticket_input(price, "123", cfg) or ("", {})
    assert "Exit-Menge:" in text
    text, _ = handle_pending_ticket_input(size_eur, "123", cfg) or ("", {})
    assert "Exit-Grund:" in text
    text, _ = handle_pending_ticket_input(reason, "123", cfg) or ("", {})
    assert "Bemerkung optional:" in text
    text, _ = handle_pending_ticket_input(note, "123", cfg) or ("", {})
    assert "Teilverkauf gespeichert:" in text


def _full_exit(ticket_id: str, cfg: dict, price: str = "115", reason: str = "3", note: str = "-") -> None:
    text, _ = handle_ticket_action(f"FULL_EXIT:{ticket_id}", "123", cfg) or ("", {})
    assert "VOLLVERKAUF:" in text
    text, _ = handle_pending_ticket_input(price, "123", cfg) or ("", {})
    assert "Exit-Grund:" in text
    text, _ = handle_pending_ticket_input(reason, "123", cfg) or ("", {})
    assert "Bemerkung optional:" in text
    text, _ = handle_pending_ticket_input(note, "123", cfg) or ("", {})
    assert "Vollverkauf gespeichert:" in text


def _stop_hit(ticket_id: str, cfg: dict, price: str = "97", note: str = "Stop sauber ausgefuehrt") -> None:
    text, _ = handle_ticket_action(f"STOP_HIT:{ticket_id}", "123", cfg) or ("", {})
    assert "STOP-LOSS:" in text
    text, _ = handle_pending_ticket_input(price, "123", cfg) or ("", {})
    assert "Exit-Grund: Stop-Loss" in text
    text, _ = handle_pending_ticket_input(note, "123", cfg) or ("", {})
    assert "Vollverkauf gespeichert:" in text


def test_dry_run_complete_buy_becomes_operational_ticket(tmp_path: Path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    _write_universe(tmp_path)
    _write_proposal(tmp_path, _complete_proposal())

    result, sent = _run_bridge(cfg, monkeypatch)
    ticket = _load_ticket(result["written_paths"][0])
    lifecycle = load_lifecycle(ticket["ticket_id"], cfg)
    report = build_execution_report(cfg)
    cost_status = build_cost_status(cfg, "2026-03")
    organism_text = render_organism_text(cfg, "2026-03")

    assert result["summary"]["approved"] == 1
    assert sent and "KAUFEN PRUEFEN: Advanced Micro Devices" in sent[0]["text"]
    assert "Stop-Methode: fallback" in sent[0]["text"]
    assert sent[0]["rows"] is not None
    assert lifecycle is not None
    assert lifecycle["current_status"] == "SENT"
    assert [row["event_type"] for row in lifecycle["events"]] == ["TRADE_CANDIDATE_CREATED", "TRADE_TICKET_SENT"]
    assert report["open_positions_count"] == 0
    assert report["closed_positions_count"] == 0
    assert cost_status["cost_coverage_status"] == "NOCH_NICHT_BEWERTBAR"
    assert "Echte Ausfuehrungen: 0" in organism_text
    assert "Warnlage:" in organism_text
    assert "NOCH NICHT BEWERTBAR: Es liegen noch keine echten Ausfuehrungen vor." in organism_text


def test_dry_run_incomplete_buy_stays_review_only(tmp_path: Path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    _write_universe(tmp_path)
    _write_proposal(tmp_path, _incomplete_proposal())

    result, sent = _run_bridge(cfg, monkeypatch)
    ticket = _load_ticket(result["written_paths"][0])
    lifecycle = load_lifecycle(ticket["ticket_id"], cfg)
    report = build_execution_report(cfg)
    cost_status = build_cost_status(cfg, "2026-03")

    assert result["summary"]["reduced"] == 1
    assert sent and "KAUFIDEE UEBERPRUEFEN: Bayer AG" in sent[0]["text"]
    assert "Operative Luecken:" in sent[0]["text"]
    assert sent[0]["rows"] is None
    assert ticket["operational_is_actionable"] is False
    assert "Stop-Kurs" in ticket["operational_missing_labels"]
    assert lifecycle is not None
    assert lifecycle["current_status"] == "CREATED"
    assert [row["event_type"] for row in lifecycle["events"]] == ["TRADE_CANDIDATE_CREATED"]
    assert report["open_positions_count"] == 0
    assert report["closed_positions_count"] == 0
    assert cost_status["cost_coverage_status"] == "NOCH_NICHT_BEWERTBAR"


def test_dry_run_buy_to_partial_exit_to_close_updates_all_views(tmp_path: Path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    _write_universe(tmp_path)
    _write_proposal(tmp_path, _complete_proposal())

    result, sent = _run_bridge(cfg, monkeypatch)
    ticket = _load_ticket(result["written_paths"][0])
    ticket_id = ticket["ticket_id"]

    _buy(ticket_id, cfg)
    _partial_exit(ticket_id, cfg)
    _full_exit(ticket_id, cfg)

    lifecycle = load_lifecycle(ticket_id, cfg)
    exits = load_exit_records(cfg, ticket_id=ticket_id)
    report = build_execution_report(cfg)
    execution_text = render_execution_summary(cfg)
    organism_text = render_organism_text(cfg, "2026-03")
    cost_status = build_cost_status(cfg, "2026-03")

    assert sent and "KAUFEN PRUEFEN: Advanced Micro Devices" in sent[0]["text"]
    assert lifecycle is not None
    assert lifecycle["current_status"] == "CLOSED"
    assert [row["event_type"] for row in lifecycle["events"]] == [
        "TRADE_CANDIDATE_CREATED",
        "TRADE_TICKET_SENT",
        "TRADE_EXECUTED_MANUAL",
        "TRADE_PARTIAL_EXIT",
        "TRADE_CLOSED_MANUAL",
    ]
    assert len(exits) == 2
    assert report["open_positions_count"] == 0
    assert report["closed_positions_count"] == 1
    assert report["partial_exit_count"] == 1
    assert report["realized_pnl_eur"] == 130.0
    assert cost_status["realized_pnl_before_costs"] == 130.0
    assert cost_status["realized_pnl_after_costs"] == 102.4
    assert cost_status["cost_coverage_status"] == "KOSTEN_GEDECKT"
    assert "Geschlossene Trades:\n1" in execution_text
    assert "Teilverkaeufe:\n1" in execution_text
    assert "KOSTENSTATUS:\nKOSTEN_GEDECKT" in execution_text
    assert "Bewertung:\nWEITER_FUEHREN" in organism_text
    assert "Geschlossen: 1" in organism_text
    assert "Bewertbare Exits: 2" in organism_text
    assert "Kostenstatus: KOSTEN_GEDECKT" in organism_text


def test_dry_run_buy_to_stop_loss_close_stays_defensive(tmp_path: Path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    _write_universe(tmp_path)
    _write_proposal(tmp_path, _complete_proposal())

    result, sent = _run_bridge(cfg, monkeypatch)
    ticket = _load_ticket(result["written_paths"][0])
    ticket_id = ticket["ticket_id"]

    _buy(ticket_id, cfg)
    _stop_hit(ticket_id, cfg)

    lifecycle = load_lifecycle(ticket_id, cfg)
    exits = load_exit_records(cfg, ticket_id=ticket_id)
    report = build_execution_report(cfg)
    execution_text = render_execution_summary(cfg)
    organism_text = render_organism_text(cfg, "2026-03")
    cost_status = build_cost_status(cfg, "2026-03")

    assert sent and "KAUFEN PRUEFEN: Advanced Micro Devices" in sent[0]["text"]
    assert lifecycle is not None
    assert lifecycle["current_status"] == "CLOSED"
    assert [row["event_type"] for row in lifecycle["events"]] == [
        "TRADE_CANDIDATE_CREATED",
        "TRADE_TICKET_SENT",
        "TRADE_EXECUTED_MANUAL",
        "TRADE_CLOSED_STOP_LOSS",
    ]
    assert len(exits) == 1
    assert exits[0]["exit_reason"] == "STOP_LOSS"
    assert report["closed_positions_count"] == 1
    assert report["realized_pnl_eur"] == -30.0
    assert cost_status["realized_pnl_before_costs"] == -30.0
    assert cost_status["realized_pnl_after_costs"] == -57.6
    assert cost_status["cost_coverage_status"] == "NICHT_GEDECKT"
    assert "Grund Stop-Loss" in execution_text
    assert "KOSTENSTATUS:\nNICHT_GEDECKT" in execution_text
    assert "Bewertung:\nGEDROSSELT_FUEHREN" in organism_text
    assert "Kostenstatus: NICHT_GEDECKT" in organism_text


def test_dry_run_month_with_activity_but_without_real_trade_stays_non_evaluable(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _write_recommendations(
        tmp_path,
        [
            {"symbol": "AMD", "name": "Advanced Micro Devices", "classification": "KAUFIDEE_PRUEFEN", "reasons": ["momentum"]},
            {"symbol": "BAYN.DE", "name": "Bayer AG", "classification": "VERKAUFEN_PRUEFEN", "reasons": ["negative_news"]},
        ],
    )

    execution_text = render_execution_summary(cfg)
    organism_text = render_organism_text(cfg, "2026-03")
    cost_status = build_cost_status(cfg, "2026-03")
    report = build_execution_report(cfg)
    lifecycle_root = tmp_path / "data" / "virus_bridge" / "ticket_lifecycle"

    assert report["source_details"]["executions_count"] == 0
    assert cost_status["manual_activity_count"] == 0
    assert cost_status["cost_coverage_status"] == "NOCH_NICHT_BEWERTBAR"
    assert "Es liegen noch keine manuell erfassten Ausfuehrungen vor." in execution_text
    assert "Kaufideen: 1" in organism_text
    assert "Verkaufssignale: 1" in organism_text
    assert "Echte Ausfuehrungen: 0" in organism_text
    assert "Bewertung:\nUEBERPRUEFEN" in organism_text
    assert not lifecycle_root.exists() or not any(lifecycle_root.iterdir())
