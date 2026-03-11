from __future__ import annotations

from datetime import datetime

from modules.v2.telegram import notifier


def _cfg(tmp_path) -> dict:
    return {
        "app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"},
        "v2": {"data_dir": "data/v2", "telegram": {"watch_max_per_day": 10, "action_max_per_day": 3, "defense_max_per_day": 5, "cooldown_minutes": 1}},
    }


def _watch(name: str, symbol: str, score: float, confidence: str) -> dict:
    return {
        "name": name,
        "symbol": symbol,
        "classification": "WATCH",
        "regime": "neutral",
        "opportunity_score": {"total_score": score, "confidence": confidence},
    }


def test_watchs_are_bundled_and_sorted(tmp_path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    sent: list[str] = []
    watches = [
        _watch("Bayer AG", "BAYN.DE", 5.5, "mittel"),
        _watch("AMD", "AMD", 5.0, "mittel"),
        _watch("Spark", "SPRK:NEO", 5.0, "mittel"),
        _watch("FMC", "FME.DE", 3.0, "spekulativ"),
        _watch("FRE", "FRE.DE", 3.0, "spekulativ"),
        _watch("ABT", "ABT", 5.0, "mittel"),
        _watch("CAT", "CAT", 4.0, "spekulativ"),
        _watch("MU", "MU", 5.0, "mittel"),
        _watch("LLY", "LLY", 4.0, "spekulativ"),
        _watch("ANET", "ANET", 3.0, "spekulativ"),
        _watch("EXTRA", "EXTRA", 2.0, "spekulativ"),
    ]

    monkeypatch.setattr(notifier, "now_berlin", lambda tz: datetime.fromisoformat("2026-03-09T12:00:00+01:00"))
    monkeypatch.setattr(notifier, "send_performance_text", lambda text, cfg: sent.append(text) or True)

    text = notifier.render_watch_bundle(watches)
    ok = notifier.send_watch_bundle(watches, cfg)

    assert ok is True
    assert sent and sent[0] == text
    assert text.startswith("HALTEN")
    assert "Mittel:" in text
    assert "Spekulativ:" in text
    assert text.count("\n- ") <= 10
    assert text.index("Bayer AG") < text.index("AMD")
    assert "Hinweis:" in text
    assert "Halten bedeutet: aktuell keine neue Transaktion priorisieren." in text
    assert "/top" in text and "/meaning" in text and "/why BAYN.DE" in text and "/status" in text and "/proposals" in text
    assert "Marktlage: neutral" in text
    assert "None" not in text and "n/a" not in text.lower()
    assert "WATCH" not in text
    assert "BEOBACHTEN" not in text
    assert len(text) < 1800
