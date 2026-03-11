from __future__ import annotations

from modules.v2.marketdata.api_governor import current_mode
from modules.v2.universe.scheduling import select_assets_for_run


def _cfg() -> dict:
    return {
        "api_governor": {
            "enabled": True,
            "minute_limit_soft": 4,
            "minute_limit_hard": 5,
            "per_run_budget": 3,
            "max_universe_per_run": 5,
            "rotate_universe_chunks": True,
            "degrade_mode": {
                "enabled": True,
                "skip_non_holdings_first": True,
                "skip_low_priority_scanner_assets": True,
                "holdings_always_first": True,
            },
        }
    }


def test_soft_limit_switches_to_degraded_mode() -> None:
    state = {"current_minute": "2026-03-10T10:00", "used_in_current_minute": 4, "last_chunk_index": 0}

    assert current_mode(state, _cfg()) == "degraded"


def test_degrade_mode_keeps_holdings_and_drops_scanners() -> None:
    cfg = _cfg()
    state = {"current_minute": "2026-03-10T10:00", "used_in_current_minute": 4, "last_chunk_index": 0}
    universe = [
        {"symbol": "H1", "group": "holding", "weight_pct": 12.0},
        {"symbol": "H2", "group": "holding", "weight_pct": 3.0},
        {"symbol": "S1", "group": "scanner", "priority": "high"},
        {"symbol": "S2", "group": "scanner", "priority": "high"},
    ]

    selected = select_assets_for_run(universe, state, cfg)

    assert [row["symbol"] for row in selected] == ["H1", "H2"]
