from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from modules.alerts.state import load_alert_state, save_alert_state
from modules.marketdata_watcher.adaptive import compute_adaptive_floor, load_recent_quotes
from modules.marketdata_watcher.alert_engine import detect_intraday_moves


def _write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def _row(isin: str, close_: float, ts: str) -> dict:
    return {
        "status": "ok",
        "isin": isin,
        "name": "Demo",
        "symbol": "demo.de",
        "open": 100.0,
        "close": close_,
        "fetched_at": ts,
    }


def test_compute_adaptive_floor_median_abs() -> None:
    floor = compute_adaptive_floor([0.5, -1.0, 2.0, -2.5, 1.5], k_multiplier=1.2, min_floor_pct=0.6, max_floor_pct=2.5)
    assert floor == 1.8


def test_load_recent_quotes_collects_points(tmp_path: Path) -> None:
    cfg = {"app": {"root_dir": str(tmp_path)}, "marketdata_alerts": {"adaptive": {"lookback_points": 4}}}
    _write(
        tmp_path / "data" / "marketdata" / "quotes_20260218.jsonl",
        [
            _row("DE000BASF111", 101.0, "2026-02-18T10:00:00+01:00"),
            _row("DE000BASF111", 102.0, "2026-02-18T10:01:00+01:00"),
        ],
    )
    _write(
        tmp_path / "data" / "marketdata" / "quotes_20260217.jsonl",
        [
            _row("DE000BASF111", 99.0, "2026-02-17T10:00:00+01:00"),
            _row("DE000BASF111", 100.5, "2026-02-17T10:01:00+01:00"),
        ],
    )

    pcts = load_recent_quotes(cfg, "DE000BASF111", date_today=date(2026, 2, 18))

    assert len(pcts) == 4


def test_adaptive_applied_and_insufficient_falls_back(tmp_path: Path) -> None:
    state_file = tmp_path / "data" / "alerts" / "state.json"

    cfg = {
        "app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"},
        "alerts": {"state_file": str(state_file)},
        "marketdata_alerts": {
            "enabled": True,
            "max_per_day": 10,
            "cooldown_minutes_per_isin": 0,
            "send_on_delta": True,
            "send_on_direction_change": True,
            "send_on_threshold_cross": True,
            "group_defaults": {"radar": {"min_delta_pct": 0.7, "min_direction_pct": 0.9, "threshold_pct": 4.0}},
            "adaptive": {
                "enabled": True,
                "lookback_points": 20,
                "k_multiplier": 1.2,
                "min_floor_pct": 0.6,
                "max_floor_pct": 2.5,
                "apply_to": ["min_delta_pct", "min_direction_pct"],
            },
        },
    }

    base_state = load_alert_state(str(state_file))
    base_state["marketdata"] = {"US0000000001": {"last_sent_ts": "2026-02-18T08:00:00+01:00", "last_pct": 0.0, "last_dir": "flat", "last_threshold": False}}
    save_alert_state(str(state_file), base_state)

    hist = [_row("US0000000001", 102.0, "2026-02-18T09:00:00+01:00") for _ in range(6)]
    _write(tmp_path / "data" / "marketdata" / "quotes_20260218.jsonl", hist)

    quotes = tmp_path / "quotes.jsonl"
    _write(quotes, [_row("US0000000001", 101.0, "2026-02-18T10:00:00+01:00")])

    blocked = detect_intraday_moves(quotes, tmp_path / "alerts.jsonl", cfg)
    assert blocked == []

    # now insufficient history, adaptive disabled for isin => static floor (0.7) should allow delta 1.0
    base_state = load_alert_state(str(state_file))
    base_state["marketdata"] = {"US0000000002": {"last_sent_ts": "2026-02-18T08:00:00+01:00", "last_pct": 0.0, "last_dir": "flat", "last_threshold": False}}
    save_alert_state(str(state_file), base_state)
    _write(tmp_path / "data" / "marketdata" / "quotes_20260218.jsonl", [_row("US0000000002", 101.0, "2026-02-18T10:00:00+01:00")])
    _write(quotes, [_row("US0000000002", 101.0, "2026-02-18T10:05:00+01:00")])

    sent = detect_intraday_moves(quotes, tmp_path / "alerts.jsonl", cfg)
    assert len(sent) == 1
