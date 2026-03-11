from __future__ import annotations

from datetime import datetime

from modules.common.utils import read_json
from modules.v2.marketdata.api_governor import (
    can_spend,
    load_governor_state,
    log_usage,
    remaining_budget,
    reserve_budget,
    reset_minute_if_needed,
    save_governor_state,
)


def _cfg(tmp_path) -> dict:
    return {
        "app": {"root_dir": str(tmp_path)},
        "api_governor": {
            "enabled": True,
            "minute_limit_soft": 4,
            "minute_limit_hard": 5,
            "per_run_budget": 2,
            "state_file": "data/api_governor/state.json",
            "metrics_file": "data/api_governor/usage_YYYYMMDD.jsonl",
        },
    }


def test_minute_reset_and_budget_reservation(tmp_path) -> None:
    cfg = _cfg(tmp_path)
    state = load_governor_state(cfg)
    state["used_in_current_minute"] = 3
    state["current_minute"] = "2026-03-10T09:00"
    reset = reset_minute_if_needed(state, datetime(2026, 3, 10, 9, 1))

    assert reset["used_in_current_minute"] == 0
    assert reset["current_minute"] == "2026-03-10T09:01"

    reserved = reserve_budget(reset, 2, cfg)
    save_governor_state(reserved, cfg)

    assert reserved["used_in_current_minute"] == 2
    assert remaining_budget(reserved, cfg) == 3
    assert read_json(tmp_path / "data" / "api_governor" / "state.json")["used_in_current_minute"] == 2


def test_hard_limit_blocks_requests_and_logs_usage(tmp_path) -> None:
    cfg = _cfg(tmp_path)
    state = {"current_minute": "2026-03-10T09:01", "used_in_current_minute": 5, "last_chunk_index": 0}

    assert not can_spend(state, 1, cfg)
    log_usage({"kind": "quote_batch", "symbols_count": 8, "cost": 0, "used_in_minute_after": 5, "mode": "blocked"}, cfg)

    usage_file = next((tmp_path / "data" / "api_governor").glob("usage_*.jsonl"))
    content = usage_file.read_text(encoding="utf-8")

    assert '"mode": "blocked"' in content
    assert '"symbols_count": 8' in content
