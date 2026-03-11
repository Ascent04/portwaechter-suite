from __future__ import annotations

from modules.virus_bridge.ticket_render import render_ticket_text


def test_approved_ticket_renders_stop_and_risk_fields() -> None:
    text = render_ticket_text(
        {
            "asset": {"name": "Advanced Micro Devices"},
            "direction": "long",
            "last_price": 197.69,
            "currency": "USD",
            "decision": "APPROVED",
            "signal_strength": "hoch",
            "market_regime": "positiv",
            "reasons": ["Momentum", "Relative Staerke"],
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
        }
    )

    assert "Stop-Loss:\nStop-Loss pruefen" in text
    assert "Stop-Kurs: 191.76" in text
    assert "Stop-Methode: fallback" in text
    assert "Stop-Abstand: 3.00 %" in text
    assert "Maximales Risiko:\n37,50 EUR" in text
    assert "None" not in text


def test_reduced_ticket_uses_restricted_template() -> None:
    text = render_ticket_text(
        {
            "asset": {"name": "Bayer AG"},
            "decision": "REDUCED",
            "signal_strength": "mittel",
            "market_regime": "neutral",
            "reasons": ["Kursdaten nicht frisch", "Stop-Loss unklar"],
            "risk_flags": ["quote_stale", "stop_loss_missing"],
            "market_status": {"is_open": True, "market": "XETRA", "next_open_hint": "09:00 Uhr"},
            "data_fresh": False,
            "entry_hint": "Einstieg nur bei bestaetigter Staerke beobachten",
        }
    )

    assert text.startswith("KAUFIDEE UEBERPRUEFEN: Bayer AG")
    assert "Status:\nUNVOLLSTAENDIG" in text
    assert "Warnlage:" in text
    assert "UNVOLLSTAENDIG: Operative Pflichtfelder fehlen." in text
    assert "VERALTET: Kursdaten sind nicht frisch." in text
    assert "NOCH NICHT BEWERTBAR: Ticket ist noch nicht operativ freigegeben." in text
    assert "Operative Luecken:" in text
    assert "Noch kein handlungsfaehiges Ticket." in text
