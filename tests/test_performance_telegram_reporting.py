from __future__ import annotations

from modules.performance import telegram_reporting as tr


def _cfg() -> dict:
    return {
        "performance": {
            "telegram_enabled": True,
            "telegram_min_n": 30,
            "telegram_min_n_regime": 20,
            "telegram_min_n_bucket": 15,
        }
    }


def _report(n: int, exp: float | None = 0.2) -> dict:
    return {
        "week": "2026-W08",
        "by_horizon": {
            "1d": {"n": n, "win_rate": 0.57, "avg_win": 1.21, "avg_loss": 0.83, "expectancy": exp},
            "3d": {"n": 10, "win_rate": 0.52, "avg_win": 1.01, "avg_loss": 0.9, "expectancy": 0.1},
            "5d": {"n": 8, "win_rate": 0.51, "avg_win": 1.11, "avg_loss": 1.0, "expectancy": 0.05},
        },
        "by_regime": {
            "neutral": {"3d": {"n": 25, "expectancy": 0.12}},
            "risk_off": {"3d": {"n": 10, "expectancy": -0.05}},
        },
        "by_bucket": {
            "factor_score>=3": {"n": 18, "expectancy": 0.2},
            "factor_score>=4": {"n": 12, "expectancy": 0.05},
        },
    }


def test_relevant_false_when_n_below_threshold() -> None:
    assert tr.is_statistically_relevant(_report(10), _cfg()) is False


def test_relevant_true_when_n_and_expectancy_valid() -> None:
    assert tr.is_statistically_relevant(_report(30), _cfg()) is True


def test_relevant_false_when_expectancy_none() -> None:
    assert tr.is_statistically_relevant(_report(30, None), _cfg()) is False


def test_summary_contains_expectancy_and_length() -> None:
    text = tr.build_telegram_summary(_report(30), _cfg())
    assert "Expectancy" in text
    assert len(text) < 2500


def test_send_if_relevant_uses_sender(monkeypatch) -> None:
    called = {"sent": False}

    def fake_send(text: str, cfg: dict) -> bool:
        called["sent"] = True
        return True

    monkeypatch.setattr(tr, "send_performance_text", fake_send)
    tr.send_if_relevant(_report(30), _cfg())
    assert called["sent"] is True
