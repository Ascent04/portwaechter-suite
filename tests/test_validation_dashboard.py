from __future__ import annotations

import json

from modules.validation.telegram_dashboard import build_kpi_dashboard, send_dashboard_if_enabled


def _snapshot(week: str = "2026-W09") -> dict:
    return {
        "week": week,
        "kpis": {
            "n_total": 123,
            "exp_3d": 0.31,
            "score3_exp_3d": 0.44,
            "risk_on_exp_3d": 0.48,
            "max_tactical_drawdown_pct": 3.4,
        },
        "status": {
            "exp_positive": True,
            "score_gradient_ok": True,
            "regime_effect_ok": True,
            "drawdown_ok": True,
        },
    }


def test_text_contains_kpis_and_limit() -> None:
    text = build_kpi_dashboard(_snapshot())
    assert "3d Exp" in text
    assert "Score≥3" in text
    assert "Drawdown" in text
    assert len(text) < 1500


def test_no_send_when_less_than_4_weeks(tmp_path, monkeypatch) -> None:
    cfg = {"app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"}, "validation": {"telegram_enabled": True}}
    (tmp_path / "data" / "validation").mkdir(parents=True, exist_ok=True)
    with (tmp_path / "data" / "validation" / "snapshots_2026W09.json").open("w", encoding="utf-8") as fh:
        json.dump({"items": [_snapshot()]}, fh)

    called = {"sent": False}

    def fake_send(text: str, cfg: dict) -> bool:
        called["sent"] = True
        return True

    monkeypatch.setattr("modules.validation.telegram_dashboard.send_performance_text", fake_send)
    send_dashboard_if_enabled(_snapshot(), cfg)
    assert called["sent"] is False


def test_send_when_4_weeks(monkeypatch, tmp_path) -> None:
    cfg = {"app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"}, "validation": {"telegram_enabled": True}}
    base = tmp_path / "data" / "validation"
    base.mkdir(parents=True, exist_ok=True)
    for w in ("2026W06", "2026W07", "2026W08", "2026W09"):
        with (base / f"snapshots_{w}.json").open("w", encoding="utf-8") as fh:
            json.dump({"items": [_snapshot(week=w.replace('W', '-W'))]}, fh)

    called = {"sent": False}

    def fake_send(text: str, cfg: dict) -> bool:
        called["sent"] = True
        return True

    monkeypatch.setattr("modules.validation.telegram_dashboard.send_performance_text", fake_send)
    send_dashboard_if_enabled(_snapshot(), cfg)
    assert called["sent"] is True
