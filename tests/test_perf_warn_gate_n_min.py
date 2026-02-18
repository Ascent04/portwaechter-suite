from __future__ import annotations

from modules.performance.warnings import should_warn


def test_perf_warn_gate_n_min() -> None:
    cfg = {
        "app": {"timezone": "Europe/Berlin"},
        "alert_profiles": {"current": "normal"},
        "tactical_warnings": {"min_n": 30, "warn_if_expectancy_below": 0.0, "cooldown_hours": 24},
    }

    assert should_warn(-0.2, 20, cfg, {}, "weekly_2026W08") is False
    assert should_warn(-0.2, 31, cfg, {}, "weekly_2026W08") is True
