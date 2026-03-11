from __future__ import annotations

import json
from pathlib import Path

from modules.marketdata_watcher.adapter_http import fetch_stooq_latest
from modules.v2.config import load_v2_config, root_dir, v2_marketdata
from modules.v2.marketdata.provider_twelvedata import get_quote, get_quotes_batch


def _to_float(value: object) -> float | None:
    try:
        if value in (None, "", "N/D"):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _stooq_symbol(symbol: str) -> str:
    text = str(symbol or "").strip()
    upper = text.upper()
    if upper.endswith(".DE"):
        return f"{upper[:-3].lower()}.de"
    if upper.endswith(".US"):
        return f"{upper[:-3].lower()}.us"
    return text.lower().replace(":XETR", ".de")


def _empty_quote(symbol: str) -> dict:
    return {"symbol": str(symbol or "").strip().upper(), "price": None, "percent_change": None, "volume": None, "timestamp": None, "status": "error", "provider": "none"}


def _latest_marketdata_rows(cfg: dict) -> list[dict]:
    market_dir = root_dir(cfg) / "data" / "marketdata"
    latest = sorted(market_dir.glob("quotes_*.jsonl"))
    if not latest:
        return []
    rows: list[dict] = []
    with latest[-1].open("r", encoding="utf-8") as fh:
        for line in fh:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _normalize_stooq(symbol: str, raw: dict, provider: str) -> dict:
    if raw.get("status") != "ok":
        row = _empty_quote(symbol)
        row["provider"] = provider if provider == "fallback" else "none"
        row["error"] = raw.get("status")
        return row
    close = _to_float(raw.get("close"))
    opened = _to_float(raw.get("open"))
    pct = None
    if close is not None and opened not in (None, 0):
        pct = round(((close - opened) / opened) * 100, 4)
    return {
        "symbol": str(symbol or "").strip().upper(),
        "price": close,
        "percent_change": pct,
        "volume": raw.get("volume"),
        "timestamp": " ".join(part for part in [raw.get("date"), raw.get("time")] if part).strip() or raw.get("fetched_at"),
        "status": "ok" if close is not None else "error",
        "provider": provider,
    }


def _find_cached(symbol: str, rows: list[dict]) -> dict | None:
    want = _stooq_symbol(symbol)
    for row in reversed(rows):
        if str(row.get("symbol") or "").lower() != want:
            continue
        if row.get("status") != "ok":
            continue
        return _normalize_stooq(symbol, row, provider="fallback")
    return None


def get_quote_with_fallback(
    symbol: str,
    api_key: str | None = None,
    cfg: dict | None = None,
    allow_live_fallback: bool = True,
    context: str = "manual",
) -> dict:
    rows = get_quotes_with_fallback(
        [symbol],
        api_key=api_key,
        cfg=cfg,
        live_fallback_limit=1 if allow_live_fallback else 0,
        context=context,
    )
    return rows[0] if rows else _empty_quote(symbol)


def get_quotes_with_fallback(
    symbols: list[str],
    api_key: str | None = None,
    cfg: dict | None = None,
    live_fallback_limit: int | None = None,
    context: str = "scanner",
) -> list[dict]:
    active_cfg = cfg or load_v2_config()
    requested = [str(symbol or "").strip().upper() for symbol in symbols if str(symbol or "").strip()]
    if not requested:
        return []

    td_quotes = (
        {
            row["symbol"]: {**row, "provider": "twelvedata"}
            for row in get_quotes_batch(requested, api_key or "", cfg=active_cfg, context=context)
        }
        if api_key
        else {}
    )
    cached_rows = _latest_marketdata_rows(active_cfg)
    live_budget = live_fallback_limit
    if live_budget is None:
        live_budget = int(v2_marketdata(active_cfg).get("max_live_fallback_symbols", 20))

    resolved: list[dict] = []
    for symbol in requested:
        td_row = td_quotes.get(symbol)
        if td_row and td_row.get("status") == "ok":
            resolved.append(td_row)
            continue

        cached = _find_cached(symbol, cached_rows)
        if cached:
            resolved.append(cached)
            continue

        if live_budget <= 0:
            resolved.append(_empty_quote(symbol))
            continue

        live_budget -= 1
        live = _normalize_stooq(symbol, fetch_stooq_latest(_stooq_symbol(symbol)), provider="fallback")
        resolved.append(live if live.get("status") == "ok" else _empty_quote(symbol))
    return resolved
