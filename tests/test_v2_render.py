from __future__ import annotations

from modules.v2.recommendations.render import render_recommendation


def _candidate() -> dict:
    return {
        "name": "BASF SE",
        "isin": "DE000BASF111",
        "symbol": "BAS.DE",
        "group": "holding",
        "provider": "twelvedata",
        "quote": {"symbol": "BAS.DE", "price": 48.12, "currency": "EUR"},
        "market_status": {"is_open": True},
        "entry_hint": "Einstieg nur bei bestaetigter Staerke pruefen",
        "stop_loss_hint": "Stop-Loss unterhalb des letzten Ruecksetzers pruefen",
        "stop_method": "fallback",
        "stop_loss_price": 46.68,
        "stop_distance_pct": 3.0,
        "risk_eur": 30.0,
        "size_min_eur": 1000,
        "size_max_eur": 1500,
        "suggested_eur": 1250,
    }


def test_render_outputs_are_reasonable() -> None:
    action = render_recommendation(
        _candidate(),
        "ACTION",
        {"opportunity": {"total_score": 7.5, "confidence": "hoch", "reasons": ["momentum", "news"]}, "defense": {"defense_score": 1}, "regime": "risk_on"},
    )
    watch = render_recommendation(
        _candidate(),
        "WATCH",
        {"opportunity": {"total_score": 4.0, "confidence": "mittel", "reasons": ["news"]}, "defense": {"defense_score": 0}, "regime": "neutral"},
    )
    defense = render_recommendation(
        _candidate(),
        "DEFENSE",
        {
            "opportunity": {"total_score": 2.0, "confidence": "spekulativ", "reasons": []},
            "defense": {
                "defense_score": 6,
                "sell_score": 4,
                "risk_reduce_score": 6,
                "reasons": ["news_burden", "high_weight"],
                "risk_reduce_reasons": ["news_burden", "high_weight"],
            },
            "regime": "risk_off",
        },
    )
    sell = render_recommendation(
        _candidate(),
        "DEFENSE",
        {
            "opportunity": {"total_score": 1.0, "confidence": "spekulativ", "reasons": []},
            "defense": {
                "defense_score": 8,
                "sell_score": 8,
                "risk_reduce_score": 6,
                "reasons": ["negative_momentum_strong", "news_burden", "high_weight"],
                "sell_reasons": ["negative_momentum_strong", "news_burden", "high_weight"],
            },
            "regime": "risk_off",
        },
    )

    assert action["telegram_text"].startswith("KAUFEN PRUEFEN: BASF SE")
    assert "Signalstaerke:\nhoch" in action["telegram_text"]
    assert "Marktlage:\npositiv" in action["telegram_text"]
    assert "Marktstatus:\noffen" in action["telegram_text"]
    assert "Warum jetzt interessant:\n- Momentum\n- Nachrichtenlage" in action["telegram_text"]
    assert "Letzter Kurs:\n48.12 EUR" in action["telegram_text"]
    assert "Einstieg:\nEinstieg nur bei bestaetigter Staerke pruefen" in action["telegram_text"]
    assert "Stop-Loss:\nStop-Loss unterhalb des letzten Ruecksetzers pruefen" in action["telegram_text"]
    assert "Stop-Kurs: 46.68" in action["telegram_text"]
    assert "Stop-Methode: fallback" in action["telegram_text"]
    assert "Stop-Abstand: 3.00 %" in action["telegram_text"]
    assert "Maximales Risiko:\n30 EUR" in action["telegram_text"] or "Maximales Risiko:\n30,00 EUR" in action["telegram_text"]
    assert "Positionsgroesse:\nMittlere bis groessere Positionsgroesse pruefen. Vorschlag: 1.000 bis 1.500 EUR." in action["telegram_text"]
    assert "Nur handeln, wenn Einstieg, Stop-Loss und Risiko fuer dich sauber passen." in action["telegram_text"]
    assert watch["telegram_text"].startswith("HALTEN: BASF SE")
    assert "Signalstaerke:\nmittel" in watch["telegram_text"]
    assert "Warum:\n- Nachrichtenlage" in watch["telegram_text"]
    assert "Position halten. Kein neuer Eingriff noetig." in watch["telegram_text"]
    assert defense["telegram_text"].startswith("RISIKO REDUZIEREN: BASF SE")
    assert "Signalstaerke:\nmittel" in defense["telegram_text"]
    assert "Marktlage:\ndefensiv" in defense["telegram_text"]
    assert "Warum:\n- Nachrichtenlage belastend\n- Grosses Positionsgewicht" in defense["telegram_text"]
    assert "Exit-Hinweis:\nSchwaeche bestaetigen und Reduktionsniveau manuell festlegen." in defense["telegram_text"]
    assert "Positionshinweis:\nPositionsgroesse reduzieren pruefen." in defense["telegram_text"]
    assert sell["telegram_text"].startswith("VERKAUFEN PRUEFEN: BASF SE")
    assert "Signalstaerke:\nhoch" in sell["telegram_text"]
    assert "Marktstatus:\noffen" in sell["telegram_text"]
    assert "Warum:\n- Starker Abverkauf\n- Nachrichtenlage belastend\n- Grosses Positionsgewicht" in sell["telegram_text"]
    assert "Letzter Kurs:\n48.12 EUR" in sell["telegram_text"]
    assert "Exit-Hinweis:\nSchwaeche bestaetigen und Exit-Level manuell festlegen." in sell["telegram_text"]
    assert "Positionshinweis:\nTeilverkauf oder Vollverkauf pruefen." in sell["telegram_text"]
    assert "Verkauf oder Teilverkauf nur dann umsetzen, wenn Schwaeche und Depotkontext fuer dich sauber passen." in sell["telegram_text"]
    assert "portfolio priority" not in action["telegram_text"].lower()
    assert "relative strength" not in action["telegram_text"].lower()
    assert "None" not in action["telegram_text"]
    assert "Confidence" not in action["telegram_text"]
    assert "Regime" not in action["telegram_text"]
    assert "WATCH" not in watch["telegram_text"]
    assert "ACTION" not in action["telegram_text"]
    assert "DEFENSE" not in defense["telegram_text"]
    assert len(sell["telegram_text"]) < 900
    assert "Keine Handlungsempfehlung" not in action["telegram_text"]
    assert "innerhalb eines Budgets von" not in action["telegram_text"]
    assert len(action["telegram_text"]) < 900
    assert len(watch["telegram_text"]) < 900
    assert len(defense["telegram_text"]) < 900
