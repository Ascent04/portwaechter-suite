from __future__ import annotations

from modules.telegram_commands import poller
from modules.common.utils import write_json
from modules.v2.telegram.help import explain_candidate


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
        }
    ]


def test_why_explains_candidate_in_simple_german() -> None:
    text = explain_candidate("DE000BAY0017", _rows())

    assert "Bayer AG (BAYN.DE)" in text
    assert "Typ: HALTEN" in text
    assert "Score: 5.5" in text
    assert "Signalstaerke: mittel" in text
    assert "Marktlage: neutral" in text
    assert "Warum jetzt relevant:" in text
    assert "Momentum" in text
    assert "Relative Staerke" in text
    assert "Depotrelevanz" in text
    assert "Einordnung:" in text
    assert "portfolio priority" not in text.lower()
    assert "Watch" not in text
    assert "BEOBACHTEN" not in text
    assert len(text) < 1800


def test_why_command_integration_and_unknown_symbol(tmp_path) -> None:
    cfg = {
        "app": {"root_dir": str(tmp_path)},
        "v2": {"data_dir": "data/v2"},
        "telegram_commands": {},
    }
    write_json(tmp_path / "data" / "v2" / "recommendations_20260309_1940.json", {"recommendations": _rows()})

    text, action = poller.handle_command({"normalized_text": "/why BAYN.DE", "text": "/why BAYN.DE"}, cfg)
    missing, _ = poller.handle_command({"normalized_text": "/why UNKNOWN", "text": "/why UNKNOWN"}, cfg)
    usage, _ = poller.handle_command({"normalized_text": "/why", "text": "/why"}, cfg)

    assert action["action"] == "why"
    assert "Bayer AG" in text
    assert "Kein Kandidat" in missing
    assert "Bitte: /why <symbol|isin>" == usage
