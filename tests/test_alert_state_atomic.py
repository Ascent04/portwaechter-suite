from __future__ import annotations

import json
from pathlib import Path

from modules.alerts.state import load_alert_state, save_alert_state


def test_state_roundtrip_atomic(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    state = {
        "date": "2026-02-18",
        "counters": {"watch": 2, "marketdata": 1},
        "watch": {"DE000BASF111": {"last_sent_ts": "2026-02-18T10:00:00+01:00", "dedupe": ["x"]}},
        "marketdata": {"DE000BASF111": {"last_pct": 7.4, "last_dir": "up", "last_threshold": True}},
    }
    save_alert_state(str(state_path), state)
    loaded = load_alert_state(str(state_path))

    assert loaded["counters"]["watch"] == 2
    assert loaded["marketdata"]["DE000BASF111"]["last_pct"] == 7.4


def test_daily_reset_keeps_marketdata_but_resets_counters(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    old_state = {
        "date": "1999-01-01",
        "counters": {"watch": 9, "marketdata": 9},
        "watch": {"DE000BASF111": {"last_sent_ts": "2026-02-18T10:00:00+01:00", "dedupe": ["k"]}},
        "marketdata": {"DE000BASF111": {"last_pct": 5.0, "last_dir": "up", "last_threshold": True}},
    }
    state_path.write_text(json.dumps(old_state), encoding="utf-8")

    loaded = load_alert_state(str(state_path))

    assert loaded["counters"]["watch"] == 0
    assert loaded["counters"]["marketdata"] == 0
    assert loaded["watch"]["DE000BASF111"]["dedupe"] == []
    assert loaded["marketdata"]["DE000BASF111"]["last_pct"] == 5.0
