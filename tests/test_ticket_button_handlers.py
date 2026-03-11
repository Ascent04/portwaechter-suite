from __future__ import annotations

import json
from pathlib import Path

from modules.common.utils import read_json, write_json
from modules.telegram_commands import poller


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
        {
            "ticket_id": ticket_id,
            "asset": {"symbol": name[:4].upper(), "isin": "", "name": name},
            "direction": "long",
            "last_price": 101.5,
            "currency": "USD",
            "decision": "APPROVED",
            "signal_strength": "hoch",
            "market_regime": "positiv",
            "score": 7.2,
            "reasons": ["Momentum", "Relative Staerke"],
            "risk_flags": [],
            "size_min_eur": 1000,
            "size_max_eur": 1500,
            "suggested_eur": 1250,
            "entry_hint": "Einstieg nur bei weiter bestaetigter Staerke beobachten",
            "stop_loss_hint": "Stop-Loss unterhalb des letzten Ruecksetzers pruefen",
            "stop_loss_price": 98.45,
            "stop_distance_pct": 3.0,
            "risk_eur": 37.5,
            "quote_age_minutes": 0.0,
            "data_fresh": True,
            "next_step": "Trade-Ticket manuell pruefen",
            "timestamp": "2026-03-09T22:00:00+01:00",
        },
    )


def test_ticket_buttons_drive_buy_execution_flow(tmp_path: Path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    ticket_id = "VF-20260309-2200-010"
    _write_ticket(tmp_path, ticket_id, "Alphabet Inc. Class A")
    monkeypatch.setenv("TG_BOT_TOKEN", "token")
    monkeypatch.setenv("TG_CHAT_ID", "123")

    sent: list[dict] = []
    updates = [
        {"update_id": 1, "message": {"chat": {"id": 123}, "text": f"/ticket {ticket_id}"}},
        {"update_id": 2, "message": {"chat": {"id": 123}, "text": "✅ Gekauft"}},
        {"update_id": 3, "message": {"chat": {"id": 123}, "text": "abc"}},
        {"update_id": 4, "message": {"chat": {"id": 123}, "text": "257.10"}},
        {"update_id": 5, "message": {"chat": {"id": 123}, "text": "875"}},
    ]

    monkeypatch.setattr(poller, "fetch_updates", lambda token, offset: updates)
    monkeypatch.setattr(
        poller,
        "send_message",
        lambda token, chat, text, cfg, keyboard_rows=None: sent.append({"text": text, "rows": keyboard_rows}) or True,
    )

    poller.run(cfg)

    assert "KAUFIDEE UEBERPRUEFEN: Alphabet Inc. Class A" in sent[0]["text"]
    assert sent[0]["rows"][0] == ["✅ Gekauft", "❌ Nicht gekauft"]
    assert "Zu welchem Kurs gekauft?" in sent[1]["text"]
    assert "gueltigen positiven Kurs" in sent[2]["text"]
    assert "Wie viel investiert?" in sent[3]["text"]
    assert "Ausfuehrung gespeichert:\nAlphabet Inc. Class A\nKaufkurs: 257.1\nEinsatz: 875.0 EUR" in sent[4]["text"]

    actions = sorted((tmp_path / "data" / "telegram").glob("actions_*.jsonl"))[-1]
    rows = [json.loads(line) for line in actions.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(row.get("action", {}).get("action") == "ticket_executed" for row in rows)


def test_not_bought_later_and_details_update_ticket_state(tmp_path: Path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    ticket_rejected = "VF-20260309-2200-011"
    ticket_deferred = "VF-20260309-2200-012"
    _write_ticket(tmp_path, ticket_rejected, "Bayer AG")
    _write_ticket(tmp_path, ticket_deferred, "Arista Networks Inc.")
    monkeypatch.setenv("TG_BOT_TOKEN", "token")
    monkeypatch.setenv("TG_CHAT_ID", "123")

    sent: list[str] = []
    updates = [
        {"update_id": 10, "message": {"chat": {"id": 123}, "text": f"/ticket {ticket_rejected}"}},
        {"update_id": 11, "message": {"chat": {"id": 123}, "text": "❌ Nicht gekauft"}},
        {"update_id": 12, "message": {"chat": {"id": 123}, "text": f"/ticket {ticket_deferred}"}},
        {"update_id": 13, "message": {"chat": {"id": 123}, "text": "⏳ Später"}},
        {"update_id": 14, "message": {"chat": {"id": 123}, "text": "📄 Details"}},
    ]

    monkeypatch.setattr(poller, "fetch_updates", lambda token, offset: updates)
    monkeypatch.setattr(poller, "send_message", lambda token, chat, text, cfg, keyboard_rows=None: sent.append(text) or True)

    poller.run(cfg)

    ticket_state = read_json(tmp_path / "data" / "virus_bridge" / "ticket_state.json")
    assert ticket_state["tickets"][ticket_rejected]["status"] == "REJECTED"
    assert ticket_state["tickets"][ticket_deferred]["status"] == "DEFERRED"
    assert "KAUFIDEE UEBERPRUEFEN: Bayer AG" in sent[0]
    assert "nicht gekauft markiert" in sent[1]
    assert "KAUFIDEE UEBERPRUEFEN: Arista Networks Inc." in sent[2]
    assert "auf spaeter gesetzt" in sent[3]
    assert "KAUFIDEE UEBERPRUEFEN: Arista Networks Inc." in sent[4]
