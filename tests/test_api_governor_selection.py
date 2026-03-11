from __future__ import annotations

from modules.v2.universe.scheduling import select_assets_for_run, split_universe_by_priority


def _cfg() -> dict:
    return {
        "api_governor": {
            "enabled": True,
            "minute_limit_soft": 45,
            "minute_limit_hard": 55,
            "per_run_budget": 20,
            "max_universe_per_run": 4,
            "rotate_universe_chunks": True,
            "degrade_mode": {
                "enabled": True,
                "skip_non_holdings_first": True,
                "skip_low_priority_scanner_assets": True,
                "holdings_always_first": True,
            },
        }
    }


def test_holdings_are_split_first() -> None:
    buckets = split_universe_by_priority(
        [
            {"symbol": "AAA", "group": "scanner", "priority": "low"},
            {"symbol": "BBB", "group": "holding", "weight_pct": 12.0},
            {"symbol": "CCC", "group": "holding", "weight_pct": 4.0},
            {"symbol": "DDD", "group": "scanner", "priority": "high"},
        ],
        _cfg(),
    )

    assert [row["symbol"] for row in buckets["holdings"]] == ["BBB", "CCC"]
    assert [row["symbol"] for row in buckets["scanner_high"]] == ["DDD"]
    assert [row["symbol"] for row in buckets["scanner_low"]] == ["AAA"]


def test_scanner_rotation_advances_chunks() -> None:
    cfg = _cfg()
    universe = [
        {"symbol": "H1", "group": "holding", "weight_pct": 10.0},
        {"symbol": "S1", "group": "scanner", "priority": "high"},
        {"symbol": "S2", "group": "scanner", "priority": "high"},
        {"symbol": "S3", "group": "scanner", "priority": "high"},
        {"symbol": "S4", "group": "scanner", "priority": "high"},
    ]
    state = {"current_minute": "2026-03-10T10:00", "used_in_current_minute": 0, "last_chunk_index": 0}

    first = select_assets_for_run(universe, state, cfg)
    second = select_assets_for_run(universe, state, cfg)

    assert [row["symbol"] for row in first] == ["H1", "S1", "S2", "S3"]
    assert [row["symbol"] for row in second] == ["H1", "S4"]
