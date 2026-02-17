from __future__ import annotations

from modules.validation.monitor import build_weekly_validation_snapshot, evaluate_90_day_status, write_snapshot


def _cfg(tmp_path) -> dict:
    return {"app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"}, "validation": {"monitor": {"max_tactical_drawdown_pct": 5.0}}}


def _report(week: str, n: int = 15, exp3: float = 0.3, score3: float = 0.4, risk_on: float = 0.5, neutral: float = 0.2) -> dict:
    return {
        "week": week,
        "summary": {"events_total": n},
        "by_horizon": {"3d": {"expectancy": exp3, "avg_loss": 1.5}},
        "by_bucket": {"factor_score>=3": {"expectancy": score3}},
        "by_regime": {"risk_on": {"3d": {"expectancy": risk_on}}, "neutral": {"3d": {"expectancy": neutral}}},
    }


def test_build_weekly_validation_snapshot_synthetic(tmp_path) -> None:
    cfg = _cfg(tmp_path)
    snap = build_weekly_validation_snapshot(_report("2026-W09"), cfg)
    assert snap["week"] == "2026-W09"
    assert snap["kpis"]["exp_3d"] == 0.3
    assert snap["status"]["exp_positive"] is True


def test_evaluate_90_day_status_recommendation_scale(tmp_path) -> None:
    cfg = _cfg(tmp_path)
    for i in range(1, 13):
        week = f"2026-W{i:02d}"
        snap = build_weekly_validation_snapshot(_report(week, n=15, exp3=0.3, score3=0.35, risk_on=0.4, neutral=0.2), cfg)
        write_snapshot(snap, cfg)

    status = evaluate_90_day_status(cfg)
    assert status["phase_complete"] is True
    assert status["recommendation"] == "scale"


def test_no_crash_missing_regime_data(tmp_path) -> None:
    cfg = _cfg(tmp_path)
    report = {"week": "2026-W10", "summary": {"events_total": 10}, "by_horizon": {"3d": {"expectancy": 0.2, "avg_loss": 1.0}}, "by_bucket": {"factor_score>=3": {"expectancy": 0.2}}}
    snap = build_weekly_validation_snapshot(report, cfg)
    assert "status" in snap
    path = write_snapshot(snap, cfg)
    assert path.exists()
    status = evaluate_90_day_status(cfg)
    assert status["recommendation"] in {"hold", "reduce", "scale"}
