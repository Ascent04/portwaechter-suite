from __future__ import annotations

import json
import logging
from urllib import parse, request
from urllib.error import HTTPError, URLError

from modules.v2.config import api_governor as api_governor_cfg
from modules.v2.marketdata.api_governor import log_usage

API_URL = "https://api.twelvedata.com/quote"
SEARCH_URL = "https://api.twelvedata.com/symbol_search"
REQUEST_HEADERS = {
    "User-Agent": "PortwaechterV2/1.0 (+https://local.portwaechter)",
    "Accept": "application/json",
}
log = logging.getLogger(__name__)


def _to_float(value: object) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: object) -> int | None:
    parsed = _to_float(value)
    if parsed is None:
        return None
    return int(parsed)


def _api_symbol(symbol: str) -> str:
    text = str(symbol or "").strip().upper()
    if text.endswith(".DE"):
        return f"{text[:-3]}:XETR"
    if text.endswith(".US"):
        return text[:-3]
    return text


def _error_quote(symbol: str, message: str) -> dict:
    return {
        "symbol": str(symbol or "").strip().upper(),
        "price": None,
        "percent_change": None,
        "volume": None,
        "timestamp": None,
        "status": "error",
        "error": message,
    }


def _request_quotes(symbols: list[str], api_key: str, timeout_sec: int = 10) -> object:
    query = parse.urlencode({"symbol": ",".join(symbols), "apikey": api_key})
    req = request.Request(f"{API_URL}?{query}", headers=REQUEST_HEADERS, method="GET")
    with request.urlopen(req, timeout=timeout_sec) as response:
        return json.loads(response.read().decode("utf-8"))


def _flatten_payload(payload: object) -> list[dict]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    if isinstance(payload.get("data"), list):
        return [row for row in payload["data"] if isinstance(row, dict)]
    if payload.get("status") == "error":
        return []
    if all(isinstance(value, dict) for value in payload.values()):
        rows = []
        for key, value in payload.items():
            if not isinstance(value, dict):
                continue
            item = dict(value)
            item["request_symbol"] = key
            item.setdefault("symbol", key)
            rows.append(item)
        return rows
    return [payload]


def _batch_only_blocked(symbols: list[str], cfg: dict | None, context: str) -> bool:
    if context != "scanner" or len(symbols) != 1 or not cfg:
        return False
    governor = api_governor_cfg(cfg)
    return bool(governor.get("enabled", True) and governor.get("batch_only", True))


def normalize_quote(raw: dict) -> dict:
    symbol = str(raw.get("meta_symbol") or raw.get("symbol") or "").strip().upper()
    if not raw or raw.get("status") == "error":
        return _error_quote(symbol, str(raw.get("message") or raw.get("error") or "provider_error"))

    price = _to_float(raw.get("close") or raw.get("price"))
    if price is None:
        return _error_quote(symbol, str(raw.get("message") or "missing_price"))

    return {
        "symbol": symbol,
        "price": round(price, 4),
        "percent_change": _to_float(raw.get("percent_change") or raw.get("change_percent")),
        "volume": _to_int(raw.get("volume")),
        "timestamp": raw.get("datetime") or raw.get("timestamp"),
        "status": "ok",
    }


def get_quote(symbol: str, api_key: str, *, cfg: dict | None = None, context: str = "manual") -> dict:
    rows = get_quotes_batch([symbol], api_key, cfg=cfg, context=context)
    return rows[0] if rows else _error_quote(symbol, "provider_error")


def get_quotes_batch(symbols: list[str], api_key: str, *, cfg: dict | None = None, context: str = "scanner") -> list[dict]:
    requested = [str(symbol or "").strip().upper() for symbol in symbols if str(symbol or "").strip()]
    if not requested:
        return []
    if not api_key:
        return [_error_quote(symbol, "missing_api_key") for symbol in requested]
    if _batch_only_blocked(requested, cfg, context):
        log.warning("twelvedata_batch_only_blocked: context=%s symbol=%s", context, requested[0])
        if cfg:
            log_usage({"kind": "quote_single_blocked", "symbols_count": 1, "cost": 0, "mode": "blocked"}, cfg)
        return [_error_quote(requested[0], "batch_only_blocked")]

    api_map = {_api_symbol(symbol): symbol for symbol in requested}
    try:
        payload = _request_quotes(list(api_map.keys()), api_key)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore") if exc.fp else ""
        return [_error_quote(symbol, f"http_{exc.code}:{detail[:80]}") for symbol in requested]
    except (URLError, TimeoutError, ValueError) as exc:
        return [_error_quote(symbol, str(exc)) for symbol in requested]
    except Exception as exc:
        return [_error_quote(symbol, str(exc)) for symbol in requested]

    rows = _flatten_payload(payload)
    by_symbol: dict[str, dict] = {}
    for row in rows:
        raw_symbol = str(row.get("request_symbol") or row.get("symbol") or "").strip().upper()
        exchange = str(row.get("exchange") or row.get("mic_code") or "").strip().upper()
        original = api_map.get(raw_symbol)
        if original is None and raw_symbol and exchange:
            original = api_map.get(f"{raw_symbol}:{exchange}")
        if original is None:
            original = raw_symbol
        row["meta_symbol"] = original
        by_symbol[original] = normalize_quote(row)

    return [by_symbol.get(symbol, _error_quote(symbol, "not_found")) for symbol in requested]


def search_symbol(query: str, api_key: str, *, cfg: dict | None = None, runtime: bool = True) -> list[dict]:
    governor = api_governor_cfg(cfg or {})
    if runtime and bool(governor.get("enabled", True)) and not bool(governor.get("allow_symbol_search_runtime", False)):
        log.warning("twelvedata_symbol_search_blocked: runtime=%s query=%s", runtime, str(query or "")[:40])
        if cfg:
            log_usage({"kind": "symbol_search", "symbols_count": 1, "cost": 0, "mode": "blocked"}, cfg)
        return []
    if not api_key or not str(query or "").strip():
        return []
    params = parse.urlencode({"symbol": str(query).strip(), "apikey": api_key})
    req = request.Request(f"{SEARCH_URL}?{params}", headers=REQUEST_HEADERS, method="GET")
    try:
        with request.urlopen(req, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return []
    rows = payload.get("data", []) if isinstance(payload, dict) else []
    return [row for row in rows if isinstance(row, dict)]
