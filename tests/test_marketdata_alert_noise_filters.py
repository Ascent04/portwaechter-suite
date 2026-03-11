from __future__ import annotations

import json
from pathlib import Path

from modules.alerts.state import load_alert_state, save_alert_state
from modules.common.utils import write_json
from modules.marketdata_watcher.alert_engine import detect_intraday_moves


def _write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def _q(isin: str, close_: float, ts: str) -> dict:
    return {
        "status": "ok",
        "isin": isin,
        "name": "Demo",
        "symbol": "demo.de",
        "open": 100.0,
        "close": close_,
        "fetched_at": ts,
    }


def _cfg(tmp_path: Path) -> dict:
    return {
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


def test_holdings_group_blocks_micro_move(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    write_json(tmp_path / "data" / "snapshots" / "portfolio_20260218.json", {"positions": [{"isin": "DE000BASF111"}]})

    state = load_alert_state(cfg["alerts"]["state_file"])
    state["marketdata"] = {"DE000BASF111": {"last_sent_ts": "2026-02-18T08:00:00+01:00", "last_pct": 0.0, "last_dir": "flat"}}
    save_alert_state(cfg["alerts"]["state_file"], state)

    quotes = tmp_path / "quotes.jsonl"
    _write(quotes, [_q("DE000BASF111", 100.21, "2026-02-18T10:00:00+01:00")])

    out = detect_intraday_moves(quotes, tmp_path / "alerts.jsonl", cfg)
    assert out == []


def test_radar_group_blocks_below_min_delta(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    state = load_alert_state(cfg["alerts"]["state_file"])
    state["marketdata"] = {"US0000000001": {"last_sent_ts": "2026-02-18T08:00:00+01:00", "last_pct": 0.0, "last_dir": "flat"}}
    save_alert_state(cfg["alerts"]["state_file"], state)

    quotes = tmp_path / "quotes.jsonl"
    _write(quotes, [_q("US0000000001", 100.79, "2026-02-18T10:00:00+01:00")])

    out = detect_intraday_moves(quotes, tmp_path / "alerts.jsonl", cfg)
    assert out == []


def test_direction_change_requires_min_direction(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    cfg["marketdata_alerts"]["group_defaults"]["holdings"]["min_delta_pct"] = 1.0
    write_json(tmp_path / "data" / "snapshots" / "portfolio_20260218.json", {"positions": [{"isin": "DE000BAY0017"}]})

    state = load_alert_state(cfg["alerts"]["state_file"])
    state["marketdata"] = {"DE000BAY0017": {"last_sent_ts": "2026-02-18T08:00:00+01:00", "last_pct": 0.2, "last_dir": "up"}}
    save_alert_state(cfg["alerts"]["state_file"], state)

    quotes = tmp_path / "quotes.jsonl"
    _write(quotes, [_q("DE000BAY0017", 99.4, "2026-02-18T10:00:00+01:00")])  # -0.6%

    out = detect_intraday_moves(quotes, tmp_path / "alerts.jsonl", cfg)
    assert out == []


def test_threshold_cross_only_on_real_cross(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    write_json(tmp_path / "data" / "snapshots" / "portfolio_20260218.json", {"positions": [{"isin": "DE000ENER6Y0"}]})

    state = load_alert_state(cfg["alerts"]["state_file"])
    state["marketdata"] = {"DE000ENER6Y0": {"last_sent_ts": "2026-02-18T08:00:00+01:00", "last_pct": 3.4, "last_dir": "up"}}
    save_alert_state(cfg["alerts"]["state_file"], state)

    quotes = tmp_path / "quotes.jsonl"
    _write(quotes, [_q("DE000ENER6Y0", 103.6, "2026-02-18T10:00:00+01:00")])
    no_cross = detect_intraday_moves(quotes, tmp_path / "alerts.jsonl", cfg)
    assert no_cross == []

    state = load_alert_state(cfg["alerts"]["state_file"])
    state["marketdata"] = {"DE000ENER6Y0": {"last_sent_ts": "2026-02-18T08:00:00+01:00", "last_pct": 2.5, "last_dir": "up"}}
    save_alert_state(cfg["alerts"]["state_file"], state)
    _write(quotes, [_q("DE000ENER6Y0", 103.2, "2026-02-18T10:05:00+01:00")])

    crossed = detect_intraday_moves(quotes, tmp_path / "alerts.jsonl", cfg)
    assert len(crossed) == 1
    assert "threshold_cross" in crossed[0]["trigger"]
