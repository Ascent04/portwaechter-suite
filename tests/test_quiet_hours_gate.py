from __future__ import annotations

from datetime import datetime
from pathlib import Path

from modules.common.notification_gate import allow_notification
from modules.performance import notifier as perf_notifier
from modules.watch_alerts.engine import run as run_watch_alerts


def _cfg(tmp_path: Path) -> dict:
    return {
        "app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"},
        "notifications": {
            "quiet_hours": {"enabled": True, "start": "22:00", "end": "08:30", "timezone": "Europe/Berlin"},
            "allow_critical_during_quiet_hours": True,
        },
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
        "notify": {"telegram": {"enabled": True, "bot_token_env": "TG_BOT_TOKEN", "chat_id_env": "TG_CHAT_ID"}},
    }


def test_quiet_hours_block_normal_and_allow_critical(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    now = datetime.fromisoformat("2026-03-10T23:15:00+01:00")

    assert allow_notification("KAUFEN PRUEFEN: AMD", cfg, now=now) == (False, "quiet_hours_active")
    assert allow_notification("SYSTEM KRITISCH\nFeed down", cfg, now=now) == (True, None)


def test_watch_alerts_respect_configured_quiet_hours_until_0830(tmp_path: Path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    sent: list[str] = []

    monkeypatch.setattr(
        "modules.watch_alerts.engine._load_inputs",
        lambda _cfg: ({"DE000BASF111"}, [], [{"isin": "DE000BASF111", "title": "News", "score": 4}], {}, "neutral"),
    )
    monkeypatch.setattr("modules.watch_alerts.engine.now_berlin", lambda _tz: datetime.fromisoformat("2026-03-10T08:00:00+01:00"))
    monkeypatch.setattr("modules.watch_alerts.engine.send_performance_text", lambda text, _cfg: sent.append(text) or True)

    run_watch_alerts(cfg)

    assert sent == []


def test_performance_notifier_logs_suppressed_quiet_hours(tmp_path: Path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    monkeypatch.setenv("TG_BOT_TOKEN", "token")
    monkeypatch.setenv("TG_CHAT_ID", "123")
    monkeypatch.setattr(perf_notifier, "allow_notification", lambda text, cfg, critical=False: (False, "quiet_hours_active"))

    called = {"urlopen": False}

    def _unexpected(*args, **kwargs):
        called["urlopen"] = True
        raise AssertionError("urlopen should not be called when quiet hours suppress the message")

    monkeypatch.setattr(perf_notifier.request, "urlopen", _unexpected)

    assert perf_notifier.send_performance_text("HALTEN: Bayer AG", cfg) is False
    assert called["urlopen"] is False
