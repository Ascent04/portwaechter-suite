from __future__ import annotations

from datetime import datetime, timedelta

from modules.watch_alerts.engine import build_watch_message, should_send


def _cfg() -> dict:
    return {
        "watch_alerts": {
            "enabled": True,
            "max_per_day": 2,
            "cooldown_minutes_per_isin": 360,
            "min_score": 3,
            "include_holdings": True,
            "include_radar": True,
        }
    }


def _state(day: str = "2026-02-18") -> dict:
    return {
        "day": day,
        "sent_today_count": 0,
        "per_isin_last_sent_ts": {},
        "dedupe_keys": [],
        "last_volume_lights": {},
        "last_regime": None,
        "last_regime_sent_day": "",
    }


def test_dedupe_prevents_duplicates() -> None:
    cfg = _cfg()
    now = datetime.fromisoformat("2026-02-18T10:00:00+01:00")
    state = _state()
    state["dedupe_keys"] = ["WATCH:signal:DE000BASF111:2026-02-18"]
    assert should_send("DE000BASF111", "signal", now, cfg, state) is False


def test_cooldown_enforced() -> None:
    cfg = _cfg()
    now = datetime.fromisoformat("2026-02-18T10:00:00+01:00")
    state = _state()
    state["per_isin_last_sent_ts"] = {"DE000BASF111": (now - timedelta(minutes=30)).isoformat()}
    assert should_send("DE000BASF111", "signal", now, cfg, state) is False


def test_max_per_day_enforced() -> None:
    cfg = _cfg()
    now = datetime.fromisoformat("2026-02-18T10:00:00+01:00")
    state = _state()
    state["sent_today_count"] = 2
    assert should_send("DE000BASF111", "signal", now, cfg, state) is False


def test_message_contains_disclaimer() -> None:
    msg = build_watch_message(
        {
            "name": "BASF SE",
            "isin": "DE000BASF111",
            "reasons": ["multi_factor", "news"],
            "score": 4,
            "confidence": "medium",
            "regime": "neutral",
            "news_source": "IR",
            "news_title": "Guidance update",
        }
    )
    assert "Beobachten, keine Handlungsempfehlung." in msg
    assert len(msg) < 1200
