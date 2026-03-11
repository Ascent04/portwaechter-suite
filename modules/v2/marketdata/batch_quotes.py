from __future__ import annotations

import logging
from datetime import datetime

from modules.v2.config import api_governor as api_governor_cfg
from modules.v2.config import v2_marketdata
from modules.v2.marketdata.fallback_router import get_quotes_with_fallback
from modules.v2.marketdata.api_governor import (
    can_spend,
    current_mode,
    load_governor_state,
    log_usage,
    reserve_budget,
    reset_minute_if_needed,
    save_governor_state,
)

log = logging.getLogger(__name__)


def _chunks(values: list[str], size: int) -> list[list[str]]:
    if size <= 0:
        size = len(values) or 1
    return [values[idx : idx + size] for idx in range(0, len(values), size)]


def _needs_retry(quote: dict | None) -> bool:
    if not isinstance(quote, dict):
        return True
    return quote.get("status") != "ok"


def _symbol_order(instruments: list[dict]) -> list[str]:
    ranked: dict[str, dict] = {}
    for item in instruments:
        symbol = str(item.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        row = ranked.setdefault(symbol, {"is_holding": False, "weight": 0.0})
        row["is_holding"] = row["is_holding"] or item.get("group") == "holding"
        row["weight"] = max(float(row["weight"]), float(item.get("weight_pct", 0) or 0))

    ordered = sorted(
        ranked.items(),
        key=lambda entry: (not entry[1]["is_holding"], -float(entry[1]["weight"]), entry[0]),
    )
    return [symbol for symbol, _ in ordered]


def _retry_candidates(instruments: list[dict], by_symbol: dict[str, dict], cfg: dict) -> list[str]:
    ranked: dict[str, dict] = {}
    for item in instruments:
        symbol = str(item.get("symbol") or "").strip().upper()
        if not symbol or not _needs_retry(by_symbol.get(symbol)):
            continue
        row = ranked.setdefault(symbol, {"is_holding": False, "weight": 0.0})
        row["is_holding"] = row["is_holding"] or item.get("group") == "holding"
        row["weight"] = max(float(row["weight"]), float(item.get("weight_pct", 0) or 0))

    max_retry = int(v2_marketdata(cfg).get("max_retry_symbols", 12) or 12)
    ordered = sorted(
        ranked.items(),
        key=lambda entry: (not entry[1]["is_holding"], -float(entry[1]["weight"]), entry[0]),
    )
    filtered = [symbol for symbol, meta in ordered if meta["is_holding"]]
    return filtered[:max_retry]


def _merge_mode(current: str, new: str) -> str:
    order = {"normal": 0, "degraded": 1, "blocked": 2}
    return new if order.get(new, 0) > order.get(current, 0) else current


def _runtime_bucket(cfg: dict) -> dict:
    bucket = {
        "api_cost": 0,
        "mode": "normal",
        "minute_used": 0,
        "holdings_count": 0,
        "scanner_count": 0,
        "selected_assets": 0,
        "blocked_by_budget": False,
    }
    if not isinstance(cfg.get("_api_governor_runtime"), dict):
        cfg["_api_governor_runtime"] = {}
    cfg["_api_governor_runtime"].update(bucket)
    return cfg["_api_governor_runtime"]


def fetch_quotes_for_instruments(instruments: list[dict], cfg: dict, api_key: str | None = None) -> list[dict]:
    unique_symbols = _symbol_order(instruments)
    runtime = _runtime_bucket(cfg)
    runtime["selected_assets"] = len(unique_symbols)
    runtime["holdings_count"] = sum(1 for item in instruments if item.get("group") == "holding")
    runtime["scanner_count"] = sum(1 for item in instruments if item.get("group") != "holding")

    governor = api_governor_cfg(cfg)
    state = reset_minute_if_needed(load_governor_state(cfg), datetime.now())
    per_run_budget = int(governor.get("per_run_budget", 20) or 20)
    batch_only = bool(governor.get("batch_only", True))
    run_cost = 0

    batch_size = int(v2_marketdata(cfg).get("batch_size", 8) or 8)
    quotes: list[dict] = []
    for batch in _chunks(unique_symbols, batch_size):
        mode = current_mode(state, cfg, run_cost_used=run_cost)
        use_twelvedata = bool(api_key)
        if bool(governor.get("enabled", True)) and (run_cost >= per_run_budget or not can_spend(state, 1, cfg)):
            use_twelvedata = False
            mode = _merge_mode(mode, "blocked" if not can_spend(state, 1, cfg) else "degraded")
        runtime["mode"] = _merge_mode(str(runtime.get("mode") or "normal"), mode)

        live_fallback_limit = None
        if not use_twelvedata and bool(governor.get("enabled", True)):
            runtime["blocked_by_budget"] = True
            live_fallback_limit = 0

        if use_twelvedata and bool(governor.get("enabled", True)):
            state = reserve_budget(state, 1, cfg)
            run_cost += 1
            runtime["api_cost"] = run_cost

        rows = get_quotes_with_fallback(
            batch,
            api_key=api_key if use_twelvedata else None,
            cfg=cfg,
            live_fallback_limit=live_fallback_limit,
        )
        quotes.extend(rows)
        runtime["minute_used"] = int(state.get("used_in_current_minute", 0) or 0)
        log_usage(
            {
                "kind": "quote_batch",
                "symbols_count": len(batch),
                "cost": 1 if use_twelvedata and bool(governor.get("enabled", True)) else 0,
                "used_in_minute_after": runtime["minute_used"],
                "mode": runtime["mode"],
            },
            cfg,
        )
    by_symbol = {row.get("symbol"): row for row in quotes}

    if not batch_only:
        retry_symbols = _retry_candidates(instruments, by_symbol, cfg)
        for symbol in retry_symbols:
            mode = current_mode(state, cfg, run_cost_used=run_cost)
            if bool(governor.get("enabled", True)) and (run_cost >= per_run_budget or not can_spend(state, 1, cfg)):
                runtime["mode"] = _merge_mode(str(runtime.get("mode") or "normal"), _merge_mode(mode, "degraded"))
                break
            retry_rows = get_quotes_with_fallback([symbol], api_key=api_key, cfg=cfg, live_fallback_limit=1)
            if bool(governor.get("enabled", True)):
                state = reserve_budget(state, 1, cfg)
                run_cost += 1
                runtime["api_cost"] = run_cost
                runtime["minute_used"] = int(state.get("used_in_current_minute", 0) or 0)
                log_usage(
                    {
                        "kind": "quote_retry",
                        "symbols_count": 1,
                        "cost": 1,
                        "used_in_minute_after": runtime["minute_used"],
                        "mode": runtime["mode"],
                    },
                    cfg,
                )
            if retry_rows:
                by_symbol[symbol] = retry_rows[0]

    runtime["minute_used"] = int(state.get("used_in_current_minute", 0) or 0)
    save_governor_state(state, cfg)
    log.warning(
        "v2_batch_governor: selected_assets=%s api_cost=%s minute_used=%s mode=%s",
        runtime["selected_assets"],
        runtime["api_cost"],
        runtime["minute_used"],
        runtime["mode"],
    )
    return [
        {
            "symbol": item.get("symbol"),
            "isin": item.get("isin"),
            "name": item.get("name"),
            "group": item.get("group"),
            "quote": by_symbol.get(str(item.get("symbol") or "").strip().upper()),
        }
        for item in instruments
    ]
