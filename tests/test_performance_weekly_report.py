from __future__ import annotations

from modules.performance.report_weekly import build_weekly_report


def test_weekly_report_stats() -> None:
    outcomes = [
        {
            "event_type": "signal",
            "isin": "A",
            "factor_score": 3,
            "regime": "neutral",
            "volume_light": {"light": "green"},
            "horizons": {
                "1d": {"status": "ok", "r_pct": 1.0},
                "3d": {"status": "ok", "r_pct": 2.0},
                "5d": {"status": "ok", "r_pct": -1.0},
            },
        },
        {
            "event_type": "signal",
            "isin": "B",
            "factor_score": 2,
            "regime": "risk_off",
            "volume_light": {"light": "red"},
            "horizons": {
                "1d": {"status": "ok", "r_pct": -1.0},
                "3d": {"status": "ok", "r_pct": 0.0},
                "5d": {"status": "unavailable", "r_pct": None},
            },
        },
    ]
    cfg = {"app": {"timezone": "Europe/Berlin"}, "performance": {"buckets": {"factor_score_min": [2, 3], "regimes": ["neutral", "risk_off"], "volume_lights": ["green", "red"]}}}
    report = build_weekly_report(outcomes, cfg)
    assert report["summary"]["events_total"] == 2
    assert report["by_horizon"]["1d"]["n"] == 2
    assert report["by_horizon"]["1d"]["is_reliable"] is False
    assert report["by_horizon"]["1d"]["win_rate"] == 0.5
    assert report["by_horizon"]["1d"]["avg_win"] == 1.0
    assert report["by_horizon"]["1d"]["avg_loss"] == 1.0
    assert report["by_horizon"]["1d"]["expectancy"] == 0.0
    assert report["by_horizon"]["1d"]["expectancy_confidence"] == "low"
    assert report["by_horizon"]["3d"]["avg_r_pct"] == 1.0
    assert "neutral" in report["by_regime"]
    assert "factor_score>=3" in report["score_calibration"]
