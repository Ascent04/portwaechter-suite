from __future__ import annotations

from modules.v2.recommendations.render import render_recommendation


def _candidate() -> dict:
    return {
        "name": "Advanced Micro Devices",
        "symbol": "AMD",
        "isin": "US0079031078",
        "group": "scanner",
        "provider": "twelvedata",
        "quote": {"symbol": "AMD", "price": 257.1, "currency": "USD"},
        "market_status": {"is_open": True},
        "entry_hint": "Einstieg nur bei weiter bestaetigter Staerke beobachten",
        "stop_loss_hint": "Stop-Loss unterhalb des letzten Ruecksetzers pruefen",
        "stop_method": "fallback",
        "stop_loss_price": 249.39,
        "stop_distance_pct": 3.0,
        "risk_eur": 26.25,
        "size_min_eur": 750,
        "size_max_eur": 1000,
        "suggested_eur": 875,
    }


def test_buy_message_contains_operational_fields() -> None:
    message = render_recommendation(
        _candidate(),
        "ACTION",
        {"opportunity": {"total_score": 6.8, "confidence": "mittel", "reasons": ["momentum", "volume", "relative_strength"]}, "defense": {"defense_score": 1}, "regime": "neutral"},
    )["telegram_text"]

    assert message.startswith("KAUFEN PRUEFEN: Advanced Micro Devices")
    assert "Signalstaerke:\nmittel" in message
    assert "Marktlage:\nneutral" in message
    assert "Marktstatus:\noffen" in message
    assert "Warum jetzt interessant:\n- Momentum\n- Ungewoehnlich hohes Volumen\n- Relative Staerke" in message
    assert "Letzter Kurs:\n257.10 USD" in message
    assert "Einstieg:\nEinstieg nur bei weiter bestaetigter Staerke beobachten" in message
    assert "Stop-Loss:\nStop-Loss unterhalb des letzten Ruecksetzers pruefen" in message
    assert "Stop-Kurs: 249.39" in message
    assert "Stop-Methode: fallback" in message
    assert "Stop-Abstand: 3.00 %" in message
    assert "Maximales Risiko:\n26,25 EUR" in message
    assert "Positionsgroesse:\nKleine bis mittlere Positionsgroesse pruefen. Vorschlag: 750 bis 1.000 EUR." in message
    assert "Naechster Schritt:\nNur handeln, wenn Einstieg, Stop-Loss und Risiko fuer dich sauber passen." in message
    assert "KAUFIDEE UEBERPRUEFEN" not in message


def test_buy_message_without_stop_loss_is_marked_incomplete() -> None:
    message = render_recommendation(
        {
            "name": "AMD",
            "symbol": "AMD",
            "group": "scanner",
            "quote": {"symbol": "AMD", "price": 257.1, "currency": "USD"},
            "market_status": {"is_open": True},
            "entry_hint": "Einstieg nur bei bestaetigter Staerke beobachten",
            "risk_eur": 26.25,
            "size_min_eur": 750,
            "size_max_eur": 1000,
            "suggested_eur": 875,
        },
        "ACTION",
        {"opportunity": {"total_score": 5.9, "confidence": "spekulativ", "reasons": ["momentum"]}, "defense": {"defense_score": 0}, "regime": "risk_on"},
    )["telegram_text"]

    assert message.startswith("KAUFIDEE UEBERPRUEFEN: AMD")
    assert "Status:\nUNVOLLSTAENDIG" in message
    assert "Operative Luecken:\n- Stop-Hinweis\n- Stop-Methode\n- Stop-Kurs\n- Stop-Abstand" in message
    assert "Noch kein handlungsfaehiges Signal." in message


def test_buy_message_can_render_structure_stop_cleanly() -> None:
    message = render_recommendation(
        {
            **_candidate(),
            "stop_loss_hint": "Stop-Loss unter letztem Swing-Tief pruefen",
            "stop_method": "structure",
            "stop_loss_price": 248.1,
            "stop_distance_pct": 3.5,
            "risk_eur": 30.62,
        },
        "ACTION",
        {"opportunity": {"total_score": 6.8, "confidence": "mittel", "reasons": ["momentum", "volume", "relative_strength"]}, "defense": {"defense_score": 1}, "regime": "neutral"},
    )["telegram_text"]

    assert "Stop-Loss:\nStop-Loss unter letztem Swing-Tief pruefen" in message
    assert "Stop-Kurs: 248.10" in message
    assert "Stop-Methode: structure" in message
    assert "Stop-Abstand: 3.50 %" in message
    assert "Maximales Risiko:\n30,62 EUR" in message
    assert "Positionsgroesse:\nKleine bis mittlere Positionsgroesse pruefen. Vorschlag: 750 bis 1.000 EUR." in message


def test_buy_message_without_risk_and_position_size_is_marked_incomplete() -> None:
    message = render_recommendation(
        {
            "name": "AMD",
            "symbol": "AMD",
            "group": "scanner",
            "quote": {"symbol": "AMD", "price": 257.1, "currency": "USD"},
            "market_status": {"is_open": True},
            "entry_hint": "Einstieg nur bei bestaetigter Staerke beobachten",
            "stop_loss_hint": "Stop-Loss unterhalb des letzten Ruecksetzers pruefen",
            "stop_method": "fallback",
            "stop_loss_price": 249.39,
            "stop_distance_pct": 3.0,
        },
        "ACTION",
        {"opportunity": {"total_score": 6.1, "confidence": "mittel", "reasons": ["momentum"]}, "defense": {"defense_score": 0}, "regime": "neutral"},
    )["telegram_text"]

    assert message.startswith("KAUFIDEE UEBERPRUEFEN: AMD")
    assert "Operative Luecken:\n- Maximales Risiko\n- Positionsgroesse" in message
