from __future__ import annotations

from modules.v2.telegram.help import render_help_text, render_meaning_text, render_top_text


def _rows() -> list[dict]:
    return [
        {
            "name": "Advanced Micro Devices",
            "symbol": "AMD",
            "classification": "ACTION",
            "regime": "risk_on",
            "opportunity_score": {"total_score": 7.2, "confidence": "hoch", "reasons": ["momentum", "volume", "positive_setup_expectancy"]},
            "defense_score": {"defense_score": 1.0, "reasons": []},
        },
        {
            "name": "Bayer AG",
            "symbol": "BAYN.DE",
            "isin": "DE000BAY0017",
            "classification": "WATCH",
            "regime": "neutral",
            "opportunity_score": {"total_score": 5.5, "confidence": "mittel", "reasons": ["momentum", "relative_strength", "portfolio_priority"]},
            "defense_score": {"defense_score": 1.0, "reasons": []},
        },
        {
            "name": "DEUTZ AG",
            "symbol": "DEZ.DE",
            "isin": "DE0006305006",
            "classification": "DEFENSE",
            "regime": "neutral",
            "opportunity_score": {"total_score": 0.1, "confidence": "spekulativ", "reasons": []},
            "defense_score": {"defense_score": 6.0, "sell_score": 6.5, "risk_reduce_score": 4.0, "sell_reasons": ["negative_momentum_strong"]},
        },
    ]


def test_help_and_meaning_texts_match_final_copy() -> None:
    help_text = render_help_text(_rows())
    meaning_text = render_meaning_text(_rows())

    assert "CB Fund Desk Hilfe" in help_text
    assert "Wichtige Befehle:" in help_text
    assert "/status - Systemlage und Warnungen" in help_text
    assert "/portfolio - letzter belastbarer Depotstand" in help_text
    assert "/execution - echte Trades, Teilverkaeufe und PnL" in help_text
    assert "/top - wichtigste Signale" in help_text and "/meaning - Bedeutung der Meldungen" in help_text and "/why AMD - Begruendung zu einem Titel" in help_text and "/proposals" in help_text
    assert "/tickets" in help_text and "/ticket <ticket_id>" in help_text
    assert "None" not in help_text and "n/a" not in help_text.lower()
    assert "KAUFEN PRUEFEN" in help_text
    assert "HALTEN" in help_text
    assert "VERKAUFEN PRUEFEN" in help_text
    assert "RISIKO REDUZIEREN" in help_text
    assert "BEOBACHTEN" not in help_text
    assert "KAUFIDEE PRUEFEN" not in help_text
    assert "RISIKO PRUEFEN" not in help_text

    assert "Bedeutung der Meldungen" in meaning_text
    assert "Mehrere Faktoren sprechen fuer einen moeglichen Einstieg." in meaning_text
    assert "Die Lage bleibt stabil genug" in meaning_text
    assert "Ein Ausstieg sollte geprueft werden." in meaning_text
    assert "defensiv = vorsichtiges Umfeld" in meaning_text
    assert "portfolio priority" not in meaning_text.lower()
    assert "WATCH" not in help_text
    assert len(help_text) < 1800
    assert len(meaning_text) < 1800


def test_top_text_uses_final_grouping() -> None:
    text = render_top_text(_rows())

    assert text.startswith("CB Fund Desk Top Signale")
    assert "Verkaufen Pruefen:" in text and "Risiko Reduzieren:" in text and "Kaufen Pruefen:" in text and "Halten:" in text
    assert "- Advanced Micro Devices (7.2)" in text
    assert "- Bayer AG (5.5)" in text
    assert "- DEUTZ AG (6.5)" in text
    assert "Marktlage: positiv" in text or "Marktlage: neutral" in text
    assert len(text) < 1800
