from __future__ import annotations

from modules.v2.recommendations.render import render_recommendation


def _candidate() -> dict:
    return {
        "name": "Bayer AG",
        "symbol": "BAYN.DE",
        "isin": "DE000BAY0017",
        "group": "holding",
        "weight_pct": 18.5,
        "provider": "twelvedata",
        "quote": {"symbol": "BAYN.DE", "price": 25.44, "currency": "EUR"},
        "market_status": {"is_open": False},
    }


def test_sell_message_contains_operational_fields() -> None:
    message = render_recommendation(
        _candidate(),
        "DEFENSE",
        {
            "opportunity": {"total_score": 1.0, "confidence": "spekulativ", "reasons": []},
            "defense": {
                "defense_score": 8.0,
                "sell_score": 8.0,
                "risk_reduce_score": 6.0,
                "reasons": ["negative_momentum_strong", "news_burden", "high_weight"],
                "sell_reasons": ["negative_momentum_strong", "news_burden", "high_weight"],
            },
            "regime": "risk_off",
        },
    )["telegram_text"]

    assert message.startswith("VERKAUFEN PRUEFEN: Bayer AG")
    assert "Signalstaerke:\nhoch" in message
    assert "Marktlage:\ndefensiv" in message
    assert "Marktstatus:\ngeschlossen" in message
    assert "Warum:\n- Starker Abverkauf\n- Nachrichtenlage belastend\n- Grosses Positionsgewicht" in message
    assert "Letzter Kurs:\n25.44 EUR" in message
    assert "Exit-Hinweis:\nSchwaeche bestaetigen und Exit-Level manuell festlegen." in message
    assert "Positionshinweis:\nTeilverkauf oder Vollverkauf pruefen." in message
    assert "Naechster Schritt:\nVerkauf oder Teilverkauf nur dann umsetzen, wenn Schwaeche und Depotkontext fuer dich sauber passen." in message
    assert "None" not in message
    assert "WATCH" not in message
    assert "ACTION" not in message
    assert "DEFENSE" not in message
    assert "Empfehlung:" not in message


def test_sell_message_prefers_risk_reduction_hint_in_defensive_market() -> None:
    message = render_recommendation(
        _candidate(),
        "DEFENSE",
        {
            "opportunity": {"total_score": 1.0, "confidence": "spekulativ", "reasons": []},
            "defense": {
                "defense_score": 6.0,
                "sell_score": 6.0,
                "risk_reduce_score": 6.0,
                "reasons": ["news_burden", "high_weight"],
                "sell_reasons": ["news_burden", "high_weight"],
            },
            "regime": "risk_off",
        },
    )["telegram_text"]

    assert "Positionshinweis:\nRisikoabbau bevorzugen." in message
