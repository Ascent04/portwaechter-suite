from __future__ import annotations

from pathlib import Path

from modules.common.utils import write_json
from modules.v2.premarket_de import build_premarket_summary_de, load_latest_recommendations, send_premarket_summary_de


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
            "name": "Bayer AG",
            "symbol": "BAYN.DE",
            "isin": "DE000BAY0017",
            "country": "DE",
            "classification": "HALTEN",
            "regime": "risk_on",
            "opportunity_score": {"total_score": 5.5, "confidence": "mittel"},
            "defense_score": {"defense_score": 1.0},
        },
        {
            "name": "SAP SE",
            "symbol": "SAP.DE",
            "isin": "DE0007164600",
            "country": "DE",
            "classification": "ACTION",
            "regime": "risk_on",
            "opportunity_score": {"total_score": 7.1, "confidence": "hoch"},
            "defense_score": {"defense_score": 1.0},
        },
        {
            "name": "Airbus SE",
            "symbol": "AIR.PA",
            "isin": "NL0000235190",
            "country": "NL",
            "classification": "ACTION",
            "regime": "risk_on",
            "opportunity_score": {"total_score": 6.9, "confidence": "hoch"},
            "defense_score": {"defense_score": 1.0},
        },
        {
            "name": "TotalEnergies",
            "symbol": "TTE.PA",
            "isin": "FR0000120271",
            "country": "FR",
            "classification": "DEFENSE",
            "regime": "risk_on",
            "opportunity_score": {"total_score": 1.0, "confidence": "spekulativ"},
            "defense_score": {"defense_score": 6.4, "sell_score": 4.2, "risk_reduce_score": 6.4},
        },
        {
            "name": "RWE AG",
            "symbol": "RWE.DE",
            "isin": "DE0007037129",
            "country": "DE",
            "group": "scanner",
            "classification": "DEFENSE",
            "regime": "risk_on",
            "opportunity_score": {"total_score": 0.8, "confidence": "spekulativ"},
            "defense_score": {"defense_score": 6.8, "sell_score": 6.8, "risk_reduce_score": 4.0},
        },
        {
            "name": "Adyen",
            "symbol": "ADYEN.AS",
            "isin": "NL0012969182",
            "country": "NL",
            "classification": "ACTION",
            "regime": "risk_on",
            "opportunity_score": {"total_score": 7.4, "confidence": "hoch"},
            "defense_score": {"defense_score": 1.0},
        },
        {
            "name": "Siemens Energy",
            "symbol": "ENR.DE",
            "isin": "DE000ENER6Y0",
            "country": "DE",
            "classification": "ACTION",
            "regime": "risk_on",
            "opportunity_score": {"total_score": 7.6, "confidence": "hoch"},
            "defense_score": {"defense_score": 1.0},
        },
        {
            "name": "AMD",
            "symbol": "AMD",
            "isin": "US0079031078",
            "country": "US",
            "classification": "ACTION",
            "regime": "risk_on",
            "opportunity_score": {"total_score": 7.8, "confidence": "hoch"},
            "defense_score": {"defense_score": 1.0},
            "quote": {"currency": "USD"},
        },
    ]


def test_build_premarket_summary_de_filters_and_sorts(tmp_path: Path) -> None:
    text = build_premarket_summary_de(_rows(), _cfg(tmp_path))

    assert text.startswith("CB Fund Desk – Voreröffnung Deutschland")
    assert "Heute wichtig:" in text
    assert "AMD" not in text
    assert text.count("\n- ") <= 5
    assert "Verkaufen prüfen:" in text
    assert "Risiko reduzieren:" in text
    assert "Kaufen prüfen:" in text
    assert text.index("Verkaufen prüfen:") < text.index("Risiko reduzieren:") < text.index("Kaufen prüfen:")
    assert "RWE AG" in text
    assert "Bayer AG" not in text
    assert "Marktlage: positiv" in text
    assert "Vor Xetra-Start prüfen." in text
    for old_term in ("WATCH", "ACTION", "DEFENSE", "HALTEN", "Heute auffaellig"):
        assert old_term not in text
    assert len(text) < 1000


def test_build_premarket_summary_de_fallback_when_no_clear_focus(tmp_path: Path) -> None:
    rows = [
        {
            "name": "Bayer AG",
            "symbol": "BAYN.DE",
            "isin": "DE000BAY0017",
            "country": "DE",
            "classification": "HALTEN",
            "regime": "neutral",
            "opportunity_score": {"total_score": 5.5, "confidence": "mittel"},
            "defense_score": {"defense_score": 1.0},
        }
    ]

    text = build_premarket_summary_de(rows, _cfg(tmp_path))

    assert text == (
        "CB Fund Desk – Voreröffnung Deutschland\n\n"
        "Heute kein klarer Schwerpunkt.\n\n"
        "Marktlage: neutral\n\n"
        "Nächster Schritt:\n"
        "Nur bestehende Positionen aufmerksam verfolgen."
    )


def test_send_premarket_summary_de_uses_latest_recommendations(tmp_path: Path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    sent: list[str] = []
    write_json(tmp_path / "data" / "v2" / "recommendations_20260310_0840.json", {"recommendations": _rows()})

    monkeypatch.setattr("modules.v2.premarket_de.send_performance_text", lambda text, cfg: sent.append(text) or True)

    latest = load_latest_recommendations(cfg)
    ok = send_premarket_summary_de(cfg)

    assert ok is True
    assert latest
    assert sent and sent[0].startswith("CB Fund Desk – Voreröffnung Deutschland")
