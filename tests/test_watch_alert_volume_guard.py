from __future__ import annotations

from datetime import datetime
from pathlib import Path

from modules.watch_alerts.engine import build_watch_message, run


def _cfg(tmp_path: Path) -> dict:
    return {
        "app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"},
        "alerts": {"state_file": str(tmp_path / "data" / "alerts" / "state.json")},
        "watch_alerts": {
            "enabled": True,
            "max_per_day": 5,
            "cooldown_minutes_per_isin": 360,
            "min_score": 3,
            "min_intraday_move_for_volume": 1.5,
            "include_holdings": True,
            "include_radar": True,
        },
        "notify": {"telegram": {"enabled": True}},
    }


def test_volume_red_suppressed_without_score_news_move(tmp_path: Path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    sent: list[str] = []

    monkeypatch.setattr("modules.watch_alerts.engine.send_performance_text", lambda text, _cfg: sent.append(text) or True)
    monkeypatch.setattr(
        "modules.watch_alerts.engine._load_inputs",
        lambda _cfg: ({"DE000BASF111"}, [], [], {"DE000BASF111": "red"}, "neutral"),
    )
    monkeypatch.setattr("modules.watch_alerts.engine.now_berlin", lambda _tz: datetime.fromisoformat("2026-02-18T12:00:00+01:00"))

    run(cfg)
    assert sent == []


def test_volume_red_allowed_with_intraday_move(tmp_path: Path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    sent: list[str] = []

    signal = {
        "id": "MULTI_FACTOR_SIGNAL",
        "isin": "DE000BASF111",
        "name": "BASF SE",
        "factor_score": 3,
        "reasons": ["price_intraday=2.1%"],
    }
    monkeypatch.setattr("modules.watch_alerts.engine.send_performance_text", lambda text, _cfg: sent.append(text) or True)
    monkeypatch.setattr(
        "modules.watch_alerts.engine._load_inputs",
        lambda _cfg: ({"DE000BASF111"}, [signal], [], {"DE000BASF111": "red"}, "risk_on"),
    )
    monkeypatch.setattr("modules.watch_alerts.engine.now_berlin", lambda _tz: datetime.fromisoformat("2026-02-18T12:01:00+01:00"))

    run(cfg)
    assert sent


def test_message_translation_and_score_omission() -> None:
    msg = build_watch_message(
        {
            "name": "BASF SE",
            "isin": "DE000BASF111",
            "reasons": ["volume_red", "news"],
            "score": None,
            "regime": "neutral",
            "news_source": "IR",
            "news_title": "Q4 Update",
        }
    )
    assert "Ungewöhnlich hohes Volumen" in msg
    assert "News-Impuls" in msg
    assert "Score:" not in msg
    assert "Beobachten, keine Handlungsempfehlung." in msg
    assert len(msg) < 1200


def test_quiet_hours_block(tmp_path: Path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    sent: list[str] = []
    monkeypatch.setattr("modules.watch_alerts.engine.send_performance_text", lambda text, _cfg: sent.append(text) or True)
    monkeypatch.setattr(
        "modules.watch_alerts.engine._load_inputs",
        lambda _cfg: ({"DE000BASF111"}, [], [{"isin": "DE000BASF111", "title": "News", "score": 4}], {}, "neutral"),
    )
    monkeypatch.setattr("modules.watch_alerts.engine.now_berlin", lambda _tz: datetime.fromisoformat("2026-02-18T22:30:00+01:00"))

    run(cfg)
    assert sent == []
