from __future__ import annotations

import json
import logging

from modules.marketdata_watcher.alert_engine import detect_intraday_moves


def test_market_suppression_summary_present(tmp_path, caplog) -> None:
    cfg = {
        "app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"},
        "alerts": {"state_file": str(tmp_path / "data" / "alerts" / "state.json")},
        "marketdata_alerts": {
            "enabled": True,
            "max_per_day": 10,
            "cooldown_minutes_per_isin": 0,
            "send_on_delta": True,
            "send_on_direction_change": True,
            "send_on_threshold_cross": True,
            "group_defaults": {
                "holdings": {"min_delta_pct": 0.7, "min_direction_pct": 0.9, "threshold_pct": 3.0},
                "radar": {"min_delta_pct": 1.2, "min_direction_pct": 1.5, "threshold_pct": 4.0},
            },
            "adaptive": {"enabled": False, "min_floor_pct": 0.6},
        },
    }

    quotes_path = tmp_path / "quotes.jsonl"
    quotes_path.parent.mkdir(parents=True, exist_ok=True)
    with quotes_path.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps({"status": "missing_mapping", "isin": "DE000BASF111", "name": "BASF"}) + "\n")

    with caplog.at_level(logging.WARNING):
        detect_intraday_moves(quotes_path, tmp_path / "alerts.jsonl", cfg)

    assert any("marketdata_alerts summary:" in rec.message for rec in caplog.records)
