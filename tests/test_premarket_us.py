from __future__ import annotations

from pathlib import Path

from modules.common.utils import write_json
from modules.v2.premarket_us import build_premarket_summary_us, load_latest_recommendations, send_premarket_summary_us


def _cfg(tmp_path: Path) -> dict:
    return {
        "app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"},
        "v2": {"data_dir": "data/v2"},
        "bot_identity": {"display_name": "CB Fund Desk"},
        "notify": {"telegram": {"enabled": False}},
    }


def _rows() -> list[dict]:
    return [
        {
            "name": "Advanced Micro Devices",
            "symbol": "AMD",
            "isin": "US0079031078",
            "country": "US",
            "classification": "ACTION",
            "regime": "neutral",
            "opportunity_score": {"total_score": 7.2, "confidence": "hoch"},
            "defense_score": {"defense_score": 1.0},
            "quote": {"currency": "USD"},
        },
        {
            "name": "Alphabet",
            "symbol": "GOOGL",
            "isin": "US02079K3059",
            "country": "US",
            "classification": "HALTEN",
            "regime": "neutral",
            "opportunity_score": {"total_score": 5.4, "confidence": "mittel"},
            "defense_score": {"defense_score": 1.0},
            "quote": {"currency": "USD"},
        },
        {
            "name": "Arista Networks",
            "symbol": "ANET",
            "isin": "US0404131064",
            "country": "US",
            "classification": "ACTION",
            "regime": "neutral",
            "opportunity_score": {"total_score": 7.5, "confidence": "hoch"},
            "defense_score": {"defense_score": 1.0},
            "quote": {"currency": "USD"},
        },
        {
            "name": "Broadcom",
            "symbol": "AVGO",
            "isin": "US11135F1012",
            "country": "US",
            "classification": "DEFENSE",
            "regime": "neutral",
            "opportunity_score": {"total_score": 0.4, "confidence": "spekulativ"},
            "defense_score": {"defense_score": 6.1, "sell_score": 4.0, "risk_reduce_score": 6.1},
            "quote": {"currency": "USD"},
        },
        {
            "name": "Tesla",
            "symbol": "TSLA",
            "isin": "US88160R1014",
            "country": "US",
            "group": "scanner",
            "classification": "DEFENSE",
            "regime": "neutral",
            "opportunity_score": {"total_score": 0.5, "confidence": "spekulativ"},
            "defense_score": {"defense_score": 6.6, "sell_score": 6.6, "risk_reduce_score": 4.0},
            "quote": {"currency": "USD"},
        },
        {
            "name": "Palo Alto Networks",
            "symbol": "PANW",
            "isin": "US6974351057",
            "country": "US",
            "classification": "ACTION",
            "regime": "neutral",
            "opportunity_score": {"total_score": 7.0, "confidence": "hoch"},
            "defense_score": {"defense_score": 1.0},
            "quote": {"currency": "USD"},
        },
        {
            "name": "NVIDIA",
            "symbol": "NVDA",
            "isin": "US67066G1040",
            "country": "US",
            "classification": "ACTION",
            "regime": "neutral",
            "opportunity_score": {"total_score": 8.1, "confidence": "hoch"},
            "defense_score": {"defense_score": 1.0},
            "quote": {"currency": "USD"},
        },
        {
            "name": "Bayer AG",
            "symbol": "BAYN.DE",
            "isin": "DE000BAY0017",
            "country": "DE",
            "classification": "ACTION",
            "regime": "neutral",
            "opportunity_score": {"total_score": 7.8, "confidence": "hoch"},
            "defense_score": {"defense_score": 1.0},
        },
    ]


def test_build_premarket_summary_us_filters_and_sorts(tmp_path: Path) -> None:
    text = build_premarket_summary_us(_rows(), _cfg(tmp_path))

    assert text.startswith("CB Fund Desk – Voreröffnung USA")
    assert "Heute wichtig:" in text
    assert "Bayer AG" not in text
    assert text.count("\n- ") <= 5
    assert "Verkaufen prüfen:" in text
    assert "Risiko reduzieren:" in text
    assert "Kaufen prüfen:" in text
    assert text.index("Verkaufen prüfen:") < text.index("Risiko reduzieren:") < text.index("Kaufen prüfen:")
    assert "Tesla" in text
    assert "Alphabet" not in text
    assert "Marktlage: neutral" in text
    assert "Vor US-Start prüfen." in text
    for old_term in ("WATCH", "ACTION", "DEFENSE", "HALTEN", "Heute auffaellig"):
        assert old_term not in text
    assert len(text) < 1000


def test_build_premarket_summary_us_fallback_when_no_clear_focus(tmp_path: Path) -> None:
    rows = [
        {
            "name": "Alphabet",
            "symbol": "GOOGL",
            "isin": "US02079K3059",
            "country": "US",
            "classification": "HALTEN",
            "regime": "neutral",
            "opportunity_score": {"total_score": 5.4, "confidence": "mittel"},
            "defense_score": {"defense_score": 1.0},
            "quote": {"currency": "USD"},
        }
    ]

    text = build_premarket_summary_us(rows, _cfg(tmp_path))

    assert text == (
        "CB Fund Desk – Voreröffnung USA\n\n"
        "Heute kein klarer Schwerpunkt.\n\n"
        "Marktlage: neutral\n\n"
        "Nächster Schritt:\n"
        "Nur bestehende Positionen aufmerksam verfolgen."
    )


def test_send_premarket_summary_us_uses_latest_recommendations(tmp_path: Path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    sent: list[str] = []
    write_json(tmp_path / "data" / "v2" / "recommendations_20260310_1510.json", {"recommendations": _rows()})

    monkeypatch.setattr("modules.v2.premarket_us.send_performance_text", lambda text, cfg: sent.append(text) or True)

    latest = load_latest_recommendations(cfg)
    ok = send_premarket_summary_us(cfg)

    assert ok is True
    assert latest
    assert sent and sent[0].startswith("CB Fund Desk – Voreröffnung USA")
