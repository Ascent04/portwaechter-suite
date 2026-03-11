from __future__ import annotations

from pathlib import Path

from modules.common.utils import read_json, write_json
from modules.virus_bridge.execution_workflow import (
    handle_pending_ticket_input,
    handle_ticket_action,
    load_ticket_state,
    render_tickets_text,
)


def _cfg(tmp_path: Path) -> dict:
    return {"app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"}}


def _write_ticket(tmp_path: Path, ticket_id: str = "VF-20260309-2200-001") -> Path:
    path = tmp_path / "data" / "virus_bridge" / "trade_candidates" / "20260309" / f"ticket_{ticket_id}.json"
    write_json(
        path,
        {
            "ticket_id": ticket_id,
            "asset": {"symbol": "AMD", "isin": "US0079031078", "name": "Advanced Micro Devices"},
            "direction": "long",
            "last_price": 197.69,
            "currency": "USD",
            "decision": "APPROVED",
            "signal_strength": "hoch",
            "market_regime": "positiv",
            "score": 7.2,
            "reasons": ["Momentum", "Ungewoehnlich hohes Volumen", "Relative Staerke"],
            "risk_flags": [],
            "size_min_eur": 1000,
            "size_max_eur": 1500,
            "suggested_eur": 1250,
            "entry_hint": "Einstieg nur bei weiter bestaetigter Staerke beobachten",
            "stop_loss_hint": "Stop-Loss unterhalb des letzten Ruecksetzers pruefen",
            "stop_loss_price": 191.76,
            "stop_distance_pct": 3.0,
            "risk_eur": 37.5,
            "quote_age_minutes": 0.0,
            "data_fresh": True,
            "next_step": "Trade-Ticket manuell pruefen",
            "timestamp": "2026-03-09T22:00:00+01:00",
        },
    )
    return path


def test_bought_flow_persists_execution_record(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    ticket_id = _write_ticket(tmp_path).stem.removeprefix("ticket_")

    text, _action = handle_ticket_action(f"BOUGHT:{ticket_id}", "123", cfg)
    assert "Zu welchem Kurs gekauft?" in text

    state = load_ticket_state(cfg)
    assert state["tickets"][ticket_id]["awaiting_input"] == "BUY_PRICE"

    text, _action = handle_pending_ticket_input("257.10", "123", cfg) or ("", {})
    assert "Wie viel investiert?" in text

    state = load_ticket_state(cfg)
    assert state["tickets"][ticket_id]["buy_price"] == 257.1
    assert state["tickets"][ticket_id]["awaiting_input"] == "BUY_SIZE_EUR"

    text, _action = handle_pending_ticket_input("875", "123", cfg) or ("", {})
    assert text == "Ausfuehrung gespeichert:\nAdvanced Micro Devices\nKaufkurs: 257.1\nEinsatz: 875.0 EUR"

    state = load_ticket_state(cfg)
    assert state["tickets"][ticket_id]["status"] == "EXECUTED"
    assert state["tickets"][ticket_id]["awaiting_input"] is None
    assert state["tickets"][ticket_id]["size_eur"] == 875.0
    assert state["tickets"][ticket_id]["asset_name"] == "Advanced Micro Devices"
    assert state["tickets"][ticket_id]["entry_price"] == 257.1
    assert state["tickets"][ticket_id]["entry_size_eur"] == 875.0
    assert state["tickets"][ticket_id]["remaining_size_eur"] == 875.0

    execution_path = next((tmp_path / "data" / "virus_bridge" / "executions").rglob(f"execution_{ticket_id}.json"))
    execution = read_json(execution_path)
    assert execution["status"] == "EXECUTED"
    assert execution["buy_price"] == 257.1
    assert execution["size_eur"] == 875.0
    assert execution["source"] == "telegram_manual"
    tickets_text = render_tickets_text(cfg)
    assert "Offene Positionen:" in tickets_text
    assert "Advanced Micro Devices | offen | Einsatz 875.00 EUR" in tickets_text


def test_invalid_numeric_input_is_handled_cleanly(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    ticket_id = _write_ticket(tmp_path, "VF-20260309-2200-002").stem.removeprefix("ticket_")

    handle_ticket_action(f"BOUGHT:{ticket_id}", "123", cfg)

    text, _action = handle_pending_ticket_input("abc", "123", cfg) or ("", {})
    assert "gueltigen positiven Kurs" in text
    assert load_ticket_state(cfg)["tickets"][ticket_id]["awaiting_input"] == "BUY_PRICE"

    text, _action = handle_pending_ticket_input("257,10", "123", cfg) or ("", {})
    assert "Wie viel investiert?" in text

    text, _action = handle_pending_ticket_input("-1", "123", cfg) or ("", {})
    assert "gueltigen positiven EUR-Betrag" in text
    assert load_ticket_state(cfg)["tickets"][ticket_id]["awaiting_input"] == "BUY_SIZE_EUR"


def test_open_tickets_use_operator_labels_instead_of_internal_decisions(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _write_ticket(tmp_path, "VF-20260309-2200-003")
    text = render_tickets_text(cfg)

    assert "Offene Tickets:" in text
    assert "Advanced Micro Devices | offen | operativ" in text
    assert "APPROVED" not in text
