from __future__ import annotations

import math

from modules.v2.config import api_governor as api_governor_cfg
from modules.v2.marketdata.api_governor import current_mode


def _priority_value(item: dict) -> float:
    score = float(item.get("last_score", 0) or 0)
    priority = str(item.get("priority") or "").strip().lower()
    if priority == "high":
        score += 5
    elif priority == "low":
        score -= 5
    score += float(item.get("weight_pct", 0) or 0) / 10
    return score


def split_universe_by_priority(assets: list[dict], cfg) -> dict:
    holdings = [row for row in assets if row.get("group") == "holding"]
    scanners = [row for row in assets if row.get("group") != "holding"]
    holdings = sorted(
        holdings,
        key=lambda row: (-float(row.get("weight_pct", 0) or 0), str(row.get("symbol") or row.get("isin") or "")),
    )

    scanner_high: list[dict] = []
    scanner_low: list[dict] = []
    for row in scanners:
        priority = str(row.get("priority") or "").strip().lower()
        last_score = float(row.get("last_score", 0) or 0)
        if priority == "high":
            scanner_high.append(row)
        elif priority == "low" or last_score < 3:
            scanner_low.append(row)
        else:
            scanner_high.append(row)

    scanner_high.sort(key=lambda row: (-_priority_value(row), str(row.get("symbol") or row.get("isin") or "")))
    scanner_low.sort(key=lambda row: (-_priority_value(row), str(row.get("symbol") or row.get("isin") or "")))
    return {"holdings": holdings, "scanner_high": scanner_high, "scanner_low": scanner_low}


def _rotated_chunk(items: list[dict], chunk_size: int, state: dict, enabled: bool) -> list[dict]:
    if not items or chunk_size <= 0:
        state["last_chunk_index"] = 0
        return []
    if not enabled:
        return items[:chunk_size]
    chunk_count = max(1, math.ceil(len(items) / chunk_size))
    chunk_index = int(state.get("last_chunk_index", 0) or 0) % chunk_count
    start = chunk_index * chunk_size
    selected = items[start : start + chunk_size]
    if not selected:
        chunk_index = 0
        selected = items[:chunk_size]
    state["last_chunk_index"] = (chunk_index + 1) % chunk_count
    return selected


def select_assets_for_run(universe: list[dict], state: dict, cfg: dict) -> list[dict]:
    governor = api_governor_cfg(cfg)
    buckets = split_universe_by_priority(universe, cfg)
    holdings = buckets["holdings"]
    scanner_high = buckets["scanner_high"]
    scanner_low = buckets["scanner_low"]
    max_assets = int(governor.get("max_universe_per_run", 30) or 30)
    mode = current_mode(state, cfg)
    degrade_cfg = governor.get("degrade_mode", {}) if isinstance(governor.get("degrade_mode"), dict) else {}
    if mode == "degraded" and not bool(degrade_cfg.get("enabled", True)):
        mode = "normal"

    selected = holdings[:max_assets]
    remaining = max(max_assets - len(selected), 0)
    if remaining <= 0:
        return selected
    if mode == "blocked":
        return selected
    if mode == "degraded" and bool(degrade_cfg.get("skip_non_holdings_first", True)):
        return selected

    scanner_pool = list(scanner_high)
    if mode != "degraded" or not bool(degrade_cfg.get("skip_low_priority_scanner_assets", True)):
        scanner_pool.extend(scanner_low)

    scanners = _rotated_chunk(
        scanner_pool,
        remaining,
        state,
        bool(governor.get("rotate_universe_chunks", True)),
    )
    return [*selected, *scanners]
