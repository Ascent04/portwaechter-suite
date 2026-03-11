from __future__ import annotations

import json
from pathlib import Path

from modules.common.utils import read_json, write_json
from modules.telegram_commands import poller
from modules.virus_bridge.execution_workflow import render_tickets_text


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
            "keyboard": {"enabled": True, "persistent": True, "resize": True},
        },
        "alert_profiles": {"current": "balanced", "profiles": {"balanced": {"watch_alerts": {}, "marketdata_alerts": {}}}},
    }


def _write_ticket(tmp_path: Path, ticket_id: str, name: str) -> None:
    write_json(
        tmp_path / "data" / "virus_bridge" / "trade_candidates" / "20260309" / f"ticket_{ticket_id}.json",
        {"ticket_id": ticket_id, "asset": {"name": name}, "direction": "long", "decision": "APPROVED", "timestamp": "2026-03-09T22:00:00+01:00"},
    )


def _write_executed_state(tmp_path: Path, ticket_id: str, name: str, status: str = "EXECUTED", remaining: float = 1000.0) -> None:
    write_json(
        tmp_path / "data" / "virus_bridge" / "ticket_state.json",
        {
            "tickets": {
                ticket_id: {
                    "status": status,
                    "asset_name": name,
                    "entry_price": 100.0,
                    "entry_size_eur": 1000.0,
                    "remaining_size_eur": remaining,
                    "awaiting_input": None,
                }
            },
            "active_by_chat": {},
        },
    )


def test_partial_sell_dialog_persists_exit(tmp_path: Path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    ticket_id = "VF-20260309-2300-010"
    _write_ticket(tmp_path, ticket_id, "Advanced Micro Devices")
    _write_executed_state(tmp_path, ticket_id, "Advanced Micro Devices")
    monkeypatch.setenv("TG_BOT_TOKEN", "token")
    monkeypatch.setenv("TG_CHAT_ID", "123")

    sent: list[str] = []
    updates = [
        {"update_id": 1, "message": {"chat": {"id": 123}, "text": f"/ticket {ticket_id}"}},
        {"update_id": 2, "message": {"chat": {"id": 123}, "text": "💸 Teilverkauft"}},
        {"update_id": 3, "message": {"chat": {"id": 123}, "text": "110"}},
        {"update_id": 4, "message": {"chat": {"id": 123}, "text": "400"}},
        {"update_id": 5, "message": {"chat": {"id": 123}, "text": "1"}},
        {"update_id": 6, "message": {"chat": {"id": 123}, "text": "-"}},
    ]

    monkeypatch.setattr(poller, "fetch_updates", lambda token, offset: updates)
    monkeypatch.setattr(poller, "send_message", lambda token, chat, text, cfg, keyboard_rows=None: sent.append(text) or True)

    poller.run(cfg)

    assert "OFFENE POSITION: Advanced Micro Devices" in sent[0]
    assert "TEILVERKAUF: Advanced Micro Devices" in sent[1]
    assert "Exit-Kurs:" in sent[1]
    assert "Exit-Menge:" in sent[2]
    assert "Exit-Grund:" in sent[3]
    assert "Bemerkung optional:" in sent[4]
    assert "Teilverkauf gespeichert:" in sent[5]

    state = read_json(tmp_path / "data" / "virus_bridge" / "ticket_state.json")
    assert state["tickets"][ticket_id]["status"] == "PARTIALLY_CLOSED"
    assert state["tickets"][ticket_id]["remaining_size_eur"] == 600.0

    exit_path = next((tmp_path / "data" / "virus_bridge" / "exits").rglob(f"exit_{ticket_id}_*.json"))
    payload = read_json(exit_path)
    assert payload["exit_reason"] == "PARTIAL_TAKE_PROFIT"
    assert payload["exit_note"] is None


def test_full_sell_dialog_closes_position_and_groups_tickets(tmp_path: Path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    open_ticket = "VF-20260309-2300-011"
    partial_ticket = "VF-20260309-2300-012"
    closed_ticket = "VF-20260309-2300-013"
    rejected_ticket = "VF-20260309-2300-014"
    for ticket_id, name in (
        (open_ticket, "Bayer AG"),
        (partial_ticket, "Arista Networks"),
        (closed_ticket, "Alphabet"),
        (rejected_ticket, "Rheinmetall"),
    ):
        _write_ticket(tmp_path, ticket_id, name)
    write_json(
        tmp_path / "data" / "virus_bridge" / "ticket_state.json",
        {
            "tickets": {
                open_ticket: {"status": "EXECUTED", "asset_name": "Bayer AG", "entry_price": 100.0, "entry_size_eur": 1000.0, "remaining_size_eur": 1000.0},
                partial_ticket: {"status": "PARTIALLY_CLOSED", "asset_name": "Arista Networks", "entry_price": 100.0, "entry_size_eur": 1000.0, "remaining_size_eur": 400.0},
                closed_ticket: {"status": "EXECUTED", "asset_name": "Alphabet", "entry_price": 100.0, "entry_size_eur": 1000.0, "remaining_size_eur": 1000.0},
                rejected_ticket: {"status": "REJECTED", "asset_name": "Rheinmetall"},
            },
            "active_by_chat": {},
        },
    )
    monkeypatch.setenv("TG_BOT_TOKEN", "token")
    monkeypatch.setenv("TG_CHAT_ID", "123")

    sent: list[str] = []
    updates = [
        {"update_id": 1, "message": {"chat": {"id": 123}, "text": f"/ticket {closed_ticket}"}},
        {"update_id": 2, "message": {"chat": {"id": 123}, "text": "🛑 Komplett verkauft"}},
        {"update_id": 3, "message": {"chat": {"id": 123}, "text": "95"}},
        {"update_id": 4, "message": {"chat": {"id": 123}, "text": "2"}},
        {"update_id": 5, "message": {"chat": {"id": 123}, "text": "-"}},
    ]
    monkeypatch.setattr(poller, "fetch_updates", lambda token, offset: updates)
    monkeypatch.setattr(poller, "send_message", lambda token, chat, text, cfg, keyboard_rows=None: sent.append(text) or True)

    poller.run(cfg)

    assert "OFFENE POSITION: Alphabet" in sent[0]
    assert "VOLLVERKAUF: Alphabet" in sent[1]
    assert "Exit-Kurs:" in sent[1]
    assert "Exit-Grund:" in sent[2]
    assert "Bemerkung optional:" in sent[3]
    assert "Vollverkauf gespeichert:" in sent[4]

    tickets_text = render_tickets_text(cfg)
    assert "Offene Positionen:" in tickets_text
    assert "Teilweise verkauft:" in tickets_text
    assert "Geschlossen:" in tickets_text
    assert "Abgelehnt:" in tickets_text
    assert "Bayer AG | offen | Einsatz 1000.00 EUR" in tickets_text
    assert "Arista Networks | Rest 400.00 EUR" in tickets_text
    assert "Alphabet | Ergebnis -50.00 EUR / -5.00 %" in tickets_text
    assert "Rheinmetall" in tickets_text

    actions = sorted((tmp_path / "data" / "telegram").glob("actions_*.jsonl"))[-1]
    rows = [json.loads(line) for line in actions.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(row.get("action", {}).get("action") == "ticket_full_exit" for row in rows)


def test_exit_validation_and_special_exit_reasons(tmp_path: Path) -> None:
    from modules.virus_bridge.execution_workflow import handle_pending_ticket_input, handle_ticket_action, load_ticket_state

    cfg = _cfg(tmp_path)
    ticket_id = "VF-20260309-2300-015"
    _write_ticket(tmp_path, ticket_id, "NVIDIA Corp.")
    _write_executed_state(tmp_path, ticket_id, "NVIDIA Corp.", remaining=600.0)

    text, _ = handle_ticket_action(f"PARTIAL_EXIT:{ticket_id}", "123", cfg) or ("", {})
    assert "Exit-Kurs:" in text
    text, _ = handle_pending_ticket_input("abc", "123", cfg) or ("", {})
    assert "gueltigen positiven Verkaufskurs" in text

    text, _ = handle_pending_ticket_input("110", "123", cfg) or ("", {})
    assert "Exit-Menge:" in text
    text, _ = handle_pending_ticket_input("700", "123", cfg) or ("", {})
    assert "Restgroesse nicht uebersteigen" in text
    assert load_ticket_state(cfg)["tickets"][ticket_id]["awaiting_input"] == "EXIT_SIZE_EUR"

    text, _ = handle_ticket_action(f"STOP_HIT:{ticket_id}", "123", cfg) or ("", {})
    assert "STOP-LOSS: NVIDIA Corp." in text
    text, _ = handle_pending_ticket_input("98", "123", cfg) or ("", {})
    assert "Exit-Grund: Stop-Loss" in text
    text, _ = handle_pending_ticket_input("News-Bruch bestaetigt", "123", cfg) or ("", {})
    assert "Vollverkauf gespeichert:" in text
    exit_path = next((tmp_path / "data" / "virus_bridge" / "exits").rglob(f"exit_{ticket_id}_*.json"))
    payload = read_json(exit_path)
    assert payload["exit_reason"] == "STOP_LOSS"
    assert payload["exit_note"] == "News-Bruch bestaetigt"


def test_target_reached_flow_uses_prefilled_reason(tmp_path: Path) -> None:
    from modules.virus_bridge.execution_workflow import handle_pending_ticket_input, handle_ticket_action

    cfg = _cfg(tmp_path)
    ticket_id = "VF-20260309-2300-016"
    _write_ticket(tmp_path, ticket_id, "Meta Platforms")
    _write_executed_state(tmp_path, ticket_id, "Meta Platforms", remaining=1000.0)

    text, _ = handle_ticket_action(f"TARGET_HIT:{ticket_id}", "123", cfg) or ("", {})
    assert "ZIEL ERREICHT: Meta Platforms" in text
    text, _ = handle_pending_ticket_input("120", "123", cfg) or ("", {})
    assert "Exit-Grund: Ziel erreicht" in text
    text, _ = handle_pending_ticket_input("-", "123", cfg) or ("", {})
    assert "Vollverkauf gespeichert:" in text
    assert "Exit-Grund: Ziel erreicht" in text
