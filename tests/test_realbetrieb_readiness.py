from __future__ import annotations

from pathlib import Path

from modules.common.runtime_dirs import runtime_directories
from modules.common.utils import read_json, write_json
from modules.integration.virus_inbox import load_pending_signal_proposals
from modules.organism.report_render import render_organism_text
from modules.portfolio_status.status import render_portfolio_status
from modules.virus_bridge.execution_report import build_execution_report, render_execution_summary
from modules.virus_bridge.execution_workflow import handle_pending_ticket_input, handle_ticket_action, render_tickets_text
from modules.virus_bridge.exit_flow import load_exit_records
from modules.virus_bridge.lifecycle import load_lifecycle


def _cfg(tmp_path: Path) -> dict:
    return {
        "app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"},
        "hedgefund": {"budget_eur": 5000},
        "v2": {"data_dir": "data/v2"},
        "data_quality": {"max_quote_age_minutes": 30},
        "organism_evaluation": {"monthly_cost_usd": 30, "eurusd_rate_assumption": 0.92},
        "integration": {"bridge": {"proposal_dir": "data/integration/signal_proposals", "consumed_dir": "data/integration/consumed"}},
    }


def _write_ticket(tmp_path: Path, ticket_id: str = "VF-20260310-2200-001") -> str:
    write_json(
        tmp_path / "data" / "virus_bridge" / "trade_candidates" / "20260310" / f"ticket_{ticket_id}.json",
        {
            "ticket_id": ticket_id,
            "source_proposal_id": f"PWV2-{ticket_id}",
            "asset": {"symbol": "AMD", "isin": "US0079031078", "name": "Advanced Micro Devices"},
            "direction": "long",
            "last_price": 100.0,
            "currency": "USD",
            "decision": "APPROVED",
            "signal_strength": "hoch",
            "market_regime": "positiv",
            "score": 7.2,
            "reasons": ["Momentum"],
            "risk_flags": [],
            "size_min_eur": 1000,
            "size_max_eur": 1500,
            "suggested_eur": 1000,
            "entry_hint": "Einstieg beobachten",
            "stop_loss_hint": "Stop-Loss beobachten",
            "stop_loss_price": 97.0,
            "stop_distance_pct": 3.0,
            "risk_eur": 30.0,
            "quote_age_minutes": 0.0,
            "data_fresh": True,
            "next_step": "Trade-Ticket manuell pruefen",
            "timestamp": "2026-03-10T22:00:00+01:00",
        },
    )
    return ticket_id


def _write_quote(tmp_path: Path, price: float = 100.0, ts: str = "2026-03-10T22:15:00+01:00") -> None:
    write_json(
        tmp_path / "data" / "v2" / "candidates_20260310_2215.json",
        {
            "generated_at": ts,
            "candidates": [
                {
                    "symbol": "AMD",
                    "isin": "US0079031078",
                    "quote": {"price": price, "currency": "USD", "timestamp": ts},
                }
            ],
        },
    )


def _execute_first_trade(ticket_id: str, cfg: dict) -> None:
    text, _ = handle_ticket_action(f"BOUGHT:{ticket_id}", "123", cfg) or ("", {})
    assert "Zu welchem Kurs gekauft?" in text
    text, _ = handle_pending_ticket_input("100", "123", cfg) or ("", {})
    assert "Wie viel investiert?" in text
    text, _ = handle_pending_ticket_input("1000", "123", cfg) or ("", {})
    assert "Ausfuehrung gespeichert:" in text


def _partial_exit(ticket_id: str, cfg: dict) -> None:
    text, _ = handle_ticket_action(f"PARTIAL_EXIT:{ticket_id}", "123", cfg) or ("", {})
    assert "Exit-Kurs:" in text
    text, _ = handle_pending_ticket_input("110", "123", cfg) or ("", {})
    assert "Exit-Menge:" in text
    text, _ = handle_pending_ticket_input("400", "123", cfg) or ("", {})
    assert "Exit-Grund:" in text
    text, _ = handle_pending_ticket_input("1", "123", cfg) or ("", {})
    assert "Bemerkung optional:" in text
    text, _ = handle_pending_ticket_input("-", "123", cfg) or ("", {})
    assert "Teilverkauf gespeichert:" in text


def _full_exit(ticket_id: str, cfg: dict) -> None:
    text, _ = handle_ticket_action(f"FULL_EXIT:{ticket_id}", "123", cfg) or ("", {})
    assert "Exit-Kurs:" in text
    text, _ = handle_pending_ticket_input("115", "123", cfg) or ("", {})
    assert "Exit-Grund:" in text
    text, _ = handle_pending_ticket_input("3", "123", cfg) or ("", {})
    assert "Bemerkung optional:" in text
    text, _ = handle_pending_ticket_input("-", "123", cfg) or ("", {})
    assert "Vollverkauf gespeichert:" in text


def test_empty_runtime_bootstraps_required_directories_and_renders_cleanly(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)

    pending = load_pending_signal_proposals(cfg)
    tickets_text = render_tickets_text(cfg)
    execution_text = render_execution_summary(cfg)
    portfolio_text = render_portfolio_status(cfg)
    organism_text = render_organism_text(cfg, "2026-03")

    assert pending == []
    assert tickets_text == "Keine Trade-Tickets vorhanden."
    assert "Es liegen noch keine manuell erfassten Ausfuehrungen vor." in execution_text
    assert "Warnlage:" in organism_text
    assert "NOCH NICHT BEWERTBAR: Es liegen noch keine echten Ausfuehrungen vor." in organism_text
    assert "Es liegt noch kein belastbarer Portfolio-Stand vor." in portfolio_text

    directories = runtime_directories(cfg)
    assert Path(directories["executions"]).exists()
    assert Path(directories["exits"]).exists()
    assert Path(directories["ticket_lifecycle"]).exists()
    assert Path(directories["performance"]).exists()
    assert Path(directories["proposal_queue"]).exists()
    assert Path(directories["consumed_queue"]).exists()


def test_first_manual_execution_record_creates_runtime_files(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    ticket_id = _write_ticket(tmp_path)
    _write_quote(tmp_path, 105.0)

    _execute_first_trade(ticket_id, cfg)

    execution_path = next((tmp_path / "data" / "virus_bridge" / "executions").rglob(f"execution_{ticket_id}.json"))
    state = read_json(tmp_path / "data" / "virus_bridge" / "ticket_state.json")
    lifecycle = load_lifecycle(ticket_id, cfg)
    report = build_execution_report(cfg)

    assert execution_path.exists()
    assert state["tickets"][ticket_id]["status"] == "EXECUTED"
    assert lifecycle is not None
    assert lifecycle["current_status"] == "EXECUTED"
    assert report["source_details"]["executions_count"] == 1
    assert report["open_positions_count"] == 1
    assert report["closed_positions_count"] == 0


def test_first_partial_exit_keeps_rest_open_and_creates_first_exit_record(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    ticket_id = _write_ticket(tmp_path)
    _write_quote(tmp_path, 105.0)
    _execute_first_trade(ticket_id, cfg)

    _partial_exit(ticket_id, cfg)
    report = build_execution_report(cfg)
    exit_rows = load_exit_records(cfg, ticket_id=ticket_id)
    state = read_json(tmp_path / "data" / "virus_bridge" / "ticket_state.json")

    assert len(exit_rows) == 1
    assert exit_rows[0]["exit_type"] == "PARTIAL"
    assert state["tickets"][ticket_id]["status"] == "PARTIALLY_CLOSED"
    assert state["tickets"][ticket_id]["remaining_size_eur"] == 600.0
    assert report["partial_exit_count"] == 1
    assert report["open_positions_count"] == 1
    assert report["closed_positions_count"] == 0
    assert report["realized_pnl_eur"] == 40.0


def test_first_complete_close_is_reflected_in_execution_and_organism(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    ticket_id = _write_ticket(tmp_path)
    _write_quote(tmp_path, 105.0)
    _execute_first_trade(ticket_id, cfg)
    _partial_exit(ticket_id, cfg)
    _full_exit(ticket_id, cfg)

    report = build_execution_report(cfg)
    execution_text = render_execution_summary(cfg)
    organism_text = render_organism_text(cfg, "2026-03")
    lifecycle = load_lifecycle(ticket_id, cfg)
    exit_rows = load_exit_records(cfg, ticket_id=ticket_id)

    assert len(exit_rows) == 2
    assert lifecycle is not None
    assert lifecycle["current_status"] == "CLOSED"
    assert report["open_positions_count"] == 0
    assert report["closed_positions_count"] == 1
    assert report["partial_exit_count"] == 1
    assert report["realized_pnl_eur"] == 130.0
    assert "Geschlossene Trades:\n1" in execution_text
    assert "Teilverkaeufe:\n1" in execution_text
    assert "Echte Ausfuehrungen: 1" in organism_text
    assert "Geschlossen: 1" in organism_text
    assert "Bewertbare Exits: 2" in organism_text
