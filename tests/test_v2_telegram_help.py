from __future__ import annotations

from modules.telegram_commands import poller
from modules.common.utils import write_json
from modules.v2.telegram.help import render_help_text, render_meaning_text, render_top_text


def _rows() -> list[dict]:
    return [
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
            "name": "AMD",
            "symbol": "AMD",
            "isin": None,
            "classification": "ACTION",
            "regime": "risk_on",
            "opportunity_score": {"total_score": 7.0, "confidence": "hoch", "reasons": ["momentum", "volume"]},
            "defense_score": {"defense_score": 1.0, "reasons": []},
        },
        {
            "name": "DEUTZ AG",
            "symbol": "DEZ.DE",
            "isin": "DE0006305006",
            "classification": "DEFENSE",
            "regime": "neutral",
            "opportunity_score": {"total_score": 0.5, "confidence": "spekulativ", "reasons": []},
            "defense_score": {"defense_score": 6.0, "reasons": ["starker_abverkauf"]},
        },
    ]


def test_help_and_meaning_texts_are_present() -> None:
    help_text = render_help_text(_rows())
    meaning_text = render_meaning_text(_rows())

    assert "CB Fund Desk Hilfe" in help_text
    assert "KAUFEN PRUEFEN" in help_text and "HALTEN" in help_text and "VERKAUFEN PRUEFEN" in help_text and "RISIKO REDUZIEREN" in help_text
    assert "/status - Systemlage und Warnungen" in help_text
    assert "/portfolio - letzter belastbarer Depotstand" in help_text
    assert "/execution - echte Trades, Teilverkaeufe und PnL" in help_text
    assert "/top - wichtigste Signale" in help_text and "/why BAYN.DE - Begruendung zu einem Titel" in help_text
    assert "/proposals" in help_text
    assert "/tickets" in help_text and "/ticket <ticket_id>" in help_text
    assert "Bedeutung der Meldungen" in meaning_text
    assert "Score" in meaning_text
    assert "Signalstaerke" in meaning_text
    assert "Marktlage" in meaning_text
    assert "positiv = Markt eher aufnahmebereit" in meaning_text
    assert "BEOBACHTEN" not in help_text
    assert "KAUFIDEE PRUEFEN" not in help_text
    assert "RISIKO PRUEFEN" not in help_text
    assert "Portfolio Priority" not in meaning_text
    assert len(help_text) < 1800
    assert len(meaning_text) < 1800


def test_top_command_uses_latest_v2_recommendations(tmp_path) -> None:
    cfg = {
        "app": {"root_dir": str(tmp_path)},
        "v2": {"data_dir": "data/v2"},
        "telegram_commands": {},
    }
    write_json(tmp_path / "data" / "v2" / "recommendations_20260309_1940.json", {"recommendations": _rows()})

    text = render_top_text(_rows())
    cmd_text, action = poller.handle_command({"normalized_text": "/top", "text": "/top"}, cfg)

    assert "CB Fund Desk Top Signale" in text
    assert "Bayer AG" in text and "AMD" in text and "DEUTZ AG" in text
    assert "Kaufen Pruefen:" in cmd_text and "Halten:" in cmd_text and "Risiko Reduzieren:" in cmd_text and "Verkaufen Pruefen:" in cmd_text
    assert action["action"] == "top"
