from __future__ import annotations

from modules.common.utils import write_json
from modules.virus_bridge.execution_workflow import render_ticket_command_text
from modules.virus_bridge.ticket_render import render_ticket_text


def _cfg(tmp_path) -> dict:
    return {"app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"}}


def test_open_market_renders_trade_ticket_and_full_buttons(tmp_path) -> None:
    cfg = _cfg(tmp_path)
    ticket_id = "VF-20260309-2200-100"
    payload = {
        "ticket_id": ticket_id,
        "asset": {"symbol": "AMD", "isin": "US0079031078", "name": "Advanced Micro Devices"},
        "direction": "long",
        "last_price": 197.69,
        "currency": "USD",
        "decision": "APPROVED",
        "signal_strength": "hoch",
        "market_regime": "positiv",
        "score": 7.2,
        "reasons": ["Momentum", "Relative Staerke"],
        "tr_verified": True,
        "market_status": {"is_open": True, "market": "NASDAQ", "next_open_hint": "15:30 Uhr"},
        "size_min_eur": 1000,
        "size_max_eur": 1500,
        "suggested_eur": 1250,
        "entry_hint": "Einstieg beobachten",
        "stop_loss_hint": "Stop-Loss pruefen",
        "next_step": "Nur handeln, wenn Einstieg, Stop-Loss und Risiko fuer dich sauber passen.",
        "stop_method": "fallback",
        "stop_loss_price": 191.76,
        "stop_distance_pct": 3.0,
        "risk_eur": 37.5,
        "data_fresh": True,
        "timestamp": "2026-03-09T22:00:00+01:00",
    }
    write_json(tmp_path / "data" / "virus_bridge" / "trade_candidates" / "20260309" / f"ticket_{ticket_id}.json", payload)

    text = render_ticket_text(payload)
    detail_text, action = render_ticket_command_text(ticket_id, cfg)

    assert "KAUFEN PRUEFEN: Advanced Micro Devices" in text
    assert "Marktstatus:\noffen" in text
    assert "Letzter Kurs:\n197.69 USD" in text
    assert "Stop-Kurs: 191.76" in text
    assert "Stop-Methode: fallback" in text
    assert "Maximales Risiko:\n37,50 EUR" in text
    assert detail_text.endswith("Status: OFFEN")
    assert action["reply_keyboard"][0] == ["✅ Gekauft", "❌ Nicht gekauft"]


def test_closed_market_renders_review_text_and_limited_buttons(tmp_path) -> None:
    cfg = _cfg(tmp_path)
    ticket_id = "VF-20260309-2200-101"
    payload = {
        "ticket_id": ticket_id,
        "asset": {"symbol": "BAYN.DE", "isin": "DE000BAY0017", "name": "Bayer AG"},
        "direction": "long",
        "last_price": 28.5,
        "currency": "EUR",
        "decision": "PENDING_MARKET_OPEN",
        "signal_strength": "mittel",
        "market_regime": "neutral",
        "score": 6.4,
        "reasons": ["Momentum", "Markt aktuell geschlossen"],
        "tr_verified": True,
        "market_status": {"is_open": False, "market": "XETRA", "next_open_hint": "09:00 Uhr"},
        "size_min_eur": 750,
        "size_max_eur": 1000,
        "suggested_eur": 875,
        "entry_hint": "Einstieg beobachten",
        "stop_loss_hint": "Stop-Loss pruefen",
        "stop_method": "fallback",
        "stop_loss_price": 27.65,
        "stop_distance_pct": 3.0,
        "risk_eur": 26.25,
        "next_step": "Kauf erst pruefen, wenn der Markt wieder offen ist.",
        "data_fresh": False,
        "timestamp": "2026-03-09T20:00:00+01:00",
    }
    write_json(tmp_path / "data" / "virus_bridge" / "trade_candidates" / "20260309" / f"ticket_{ticket_id}.json", payload)

    text = render_ticket_text(payload)
    _detail_text, action = render_ticket_command_text(ticket_id, cfg)

    assert "KAUFIDEE UEBERPRUEFEN: Bayer AG" in text
    assert "Status:\nUNVOLLSTAENDIG" in text
    assert "Marktstatus:\ngeschlossen" in text
    assert "Naechste Handelsmoeglichkeit: 09:00 Uhr" in text
    assert "Warnlage:" in text
    assert "MARKT GESCHLOSSEN: Der Markt ist aktuell geschlossen." in text
    assert "VERALTET: Kursdaten sind nicht frisch." in text
    assert "NOCH NICHT BEWERTBAR: Ticket ist noch nicht operativ freigegeben." in text
    assert "Markt aktuell offen" in text
    assert "Frische Kursdaten" in text
    assert "Ticket-Reife" in text
    assert action["reply_keyboard"][0] == ["⏳ Später", "📄 Details"]


def test_unverified_asset_renders_rejected_text(tmp_path) -> None:
    payload = {
        "ticket_id": "VF-20260309-2200-102",
        "asset": {"symbol": "FOO", "isin": "DE0000000000", "name": "Foo AG"},
        "decision": "REJECTED",
        "tr_verified": False,
        "market_status": {"is_open": False, "market": "UNKNOWN", "next_open_hint": "Marktzeit manuell pruefen"},
        "reasons": ["Nicht bei Trade Republic verifiziert"],
    }

    text = render_ticket_text(payload)

    assert "TRADE-KANDIDAT ABGELEHNT: Foo AG" in text
    assert "Nicht bei Trade Republic verifiziert" in text
