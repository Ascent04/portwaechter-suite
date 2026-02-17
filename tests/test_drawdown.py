from __future__ import annotations

from modules.risk.drawdown import compute_equity_curve, compute_max_drawdown, compute_rolling_drawdown


def test_compute_equity_curve_synthetic_returns() -> None:
    outcomes = [{"r_pct": 10.0}, {"r_pct": -5.0}, {"r_pct": 2.0}]
    curve = compute_equity_curve(outcomes)
    assert len(curve) == 4
    assert round(curve[-1], 6) == round(1.10 * 0.95 * 1.02, 6)


def test_compute_max_drawdown_correct() -> None:
    curve = [1.0, 1.2, 1.1, 0.9, 1.05]
    dd = compute_max_drawdown(curve)
    assert dd == 25.0


def test_no_division_by_zero() -> None:
    curve = [0.0, 0.0, 0.0]
    dd = compute_max_drawdown(curve)
    assert dd == 0.0


def test_compute_rolling_drawdown_from_outcomes() -> None:
    outcomes = [
        {"ts_eval": "2026-02-01T08:00:00+01:00", "r_pct": 1.0},
        {"ts_eval": "2026-02-10T08:00:00+01:00", "r_pct": -2.0},
        {"ts_eval": "2026-02-20T08:00:00+01:00", "r_pct": 0.5},
    ]
    rows = compute_rolling_drawdown(outcomes, window_days=30)
    assert len(rows) == 3
    assert "max_drawdown_pct" in rows[-1]
