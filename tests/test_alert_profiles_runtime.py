from __future__ import annotations

from pathlib import Path

from modules.config.runtime import apply_runtime_overrides, get_current_profile, set_profile


def test_set_profile_changes_thresholds(tmp_path: Path) -> None:
    cfg = {
        "app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"},
        "watch_alerts": {"min_score": 3},
        "marketdata_alerts": {"threshold_pct": 5.0},
        "alert_profiles": {
            "current": "balanced",
            "profiles": {
                "quiet": {
                    "watch_alerts": {"min_score": 4},
                    "marketdata_alerts": {"threshold_pct": 7.0},
                }
            },
        },
    }

    set_profile("quiet", cfg)
    merged = apply_runtime_overrides(cfg)

    assert get_current_profile(merged) == "quiet"
    assert merged["watch_alerts"]["min_score"] == 4
    assert merged["marketdata_alerts"]["threshold_pct"] == 7.0
