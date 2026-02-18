from __future__ import annotations

from pathlib import Path

from modules.common.utils import write_json
from modules.performance import warnings


def _cfg(tmp_path: Path) -> dict:
    return {
        "app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"},
        "tactical_warnings": {
            "enabled": True,
            "min_n": 30,
            "horizons": ["3d"],
            "warn_if_expectancy_below": 0.0,
            "cooldown_hours": 24,
            "state_file": "data/performance/warn_state.json",
        },
        "alert_profiles": {"current": "balanced", "profiles": {}},
        "notify": {"telegram": {"enabled": True}},
    }


def test_warn_once_and_cooldown_blocks_second(tmp_path: Path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    report = {
        "by_horizon": {
            "3d": {"n": 35, "expectancy": -0.2},
        }
    }
    write_json(tmp_path / "data" / "performance" / "reports" / "weekly_2026W08.json", report)

    sent: list[str] = []
    monkeypatch.setattr(warnings, "send_warning", lambda _cfg, text: sent.append(text) or True)

    warnings.run(cfg)
    warnings.run(cfg)

    assert len(sent) == 1
    assert "PERF WARN" in sent[0]
