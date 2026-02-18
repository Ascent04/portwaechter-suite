from __future__ import annotations

import json
from pathlib import Path

from modules.marketdata_watcher.alert_engine import detect_intraday_moves


def _cfg(tmp_path: Path) -> dict:
    return {
        "app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"},
        "alerts": {"state_file": str(tmp_path / "data" / "alerts" / "state.json")},
        "marketdata_alerts": {
            "enabled": True,
            "max_per_day": 10,
            "cooldown_minutes_per_isin": 0,
            "min_delta_pct": 0.5,
            "threshold_pct": 5.0,
            "send_on_direction_change": True,
            "send_on_threshold_cross": True,
            "send_on_delta": True,
        },
    }


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


def test_same_pct_not_sent_twice(tmp_path: Path) -> None:
    quotes = tmp_path / "quotes.jsonl"
    alerts = tmp_path / "alerts.jsonl"
    cfg = _cfg(tmp_path)

    _write(quotes, [_q("DE000BASF111", 105.0, "2026-02-18T10:00:00+01:00")])
    first = detect_intraday_moves(quotes, alerts, cfg)
    second = detect_intraday_moves(quotes, alerts, cfg)

    assert len(first) == 1
    assert second == []


def test_delta_threshold_and_direction_change(tmp_path: Path) -> None:
    quotes = tmp_path / "quotes.jsonl"
    alerts = tmp_path / "alerts.jsonl"
    cfg = _cfg(tmp_path)

    _write(quotes, [_q("DE000BASF111", 105.0, "2026-02-18T10:00:00+01:00")])
    detect_intraday_moves(quotes, alerts, cfg)

    _write(quotes, [_q("DE000BASF111", 105.2, "2026-02-18T10:05:00+01:00")])
    assert detect_intraday_moves(quotes, alerts, cfg) == []

    _write(quotes, [_q("DE000BASF111", 105.8, "2026-02-18T10:10:00+01:00")])
    delta = detect_intraday_moves(quotes, alerts, cfg)
    assert len(delta) == 1
    assert "delta" in delta[0]["trigger"]

    _write(quotes, [_q("DE000BASF111", 95.8, "2026-02-18T10:15:00+01:00")])
    changed = detect_intraday_moves(quotes, alerts, cfg)
    assert len(changed) == 1
    assert "direction" in changed[0]["trigger"]


def test_threshold_crossing_and_limits(tmp_path: Path) -> None:
    quotes = tmp_path / "quotes.jsonl"
    alerts = tmp_path / "alerts.jsonl"
    cfg = _cfg(tmp_path)

    _write(quotes, [_q("DE000BAY0017", 104.0, "2026-02-18T10:00:00+01:00")])
    assert detect_intraday_moves(quotes, alerts, cfg) == []

    _write(quotes, [_q("DE000BAY0017", 105.5, "2026-02-18T10:02:00+01:00")])
    crossed = detect_intraday_moves(quotes, alerts, cfg)
    assert len(crossed) == 1
    assert crossed[0]["trigger"] in {"threshold_cross", "initial_threshold"}

    cfg["marketdata_alerts"]["cooldown_minutes_per_isin"] = 180
    _write(quotes, [_q("DE000BAY0017", 106.1, "2026-02-18T10:05:00+01:00")])
    blocked_cooldown = detect_intraday_moves(quotes, alerts, cfg)
    assert blocked_cooldown == []

    cfg["marketdata_alerts"]["cooldown_minutes_per_isin"] = 0
    cfg["marketdata_alerts"]["max_per_day"] = 1
    _write(quotes, [_q("DE000BAY0017", 106.9, "2026-02-18T10:08:00+01:00")])
    blocked_daily = detect_intraday_moves(quotes, alerts, cfg)
    assert blocked_daily == []
