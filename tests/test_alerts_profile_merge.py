from __future__ import annotations

from modules.config.runtime import apply_runtime_overrides, save_runtime_overrides


def test_alerts_profile_merge_defaults_and_overrides(tmp_path) -> None:
    cfg = {
        "app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"},
        "watch_alerts": {"enabled": True, "min_score": 3},
        "marketdata_alerts": {
            "enabled": True,
            "group_defaults": {
                "holdings": {"threshold_pct": 3.0, "min_delta_pct": 0.7},
                "radar": {"threshold_pct": 4.0, "min_delta_pct": 1.2},
            },
        },
        "alert_profiles": {
            "current": "normal",
            "profiles": {
                "quiet": {
                    "watch_alerts": {"min_score": 5},
                    "marketdata_alerts": {"group_defaults": {"holdings": {"threshold_pct": 4.2}}},
                }
            },
        },
    }

    save_runtime_overrides(
        cfg,
        {
            "alert_profile": {"current": "quiet"},
            "overrides": {"marketdata_alerts": {"group_defaults": {"radar": {"min_delta_pct": 2.0}}}},
        },
    )

    merged = apply_runtime_overrides(cfg)

    assert merged["watch_alerts"]["min_score"] == 5
    assert merged["marketdata_alerts"]["group_defaults"]["holdings"]["threshold_pct"] == 4.2
    assert merged["marketdata_alerts"]["group_defaults"]["radar"]["min_delta_pct"] == 2.0
