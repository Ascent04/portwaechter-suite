from __future__ import annotations

import csv
from datetime import datetime
from io import StringIO
from pathlib import Path
from urllib import request

from modules.marketdata_watcher.volume_baseline import (
    load_volume_baseline,
    save_volume_baseline,
    update_volume_baseline,
)
from modules.common.utils import append_jsonl, ensure_dir, now_iso_tz, read_json


STOOQ_URL = "https://stooq.com/q/l/?s={symbol}&f=sd2t2ohlcv&h&e=csv"


def _to_float(value: str | None) -> float | None:
    if value in (None, "", "N/D"):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def fetch_stooq_latest(symbol: str) -> dict:
    url = STOOQ_URL.format(symbol=symbol)
    with request.urlopen(url, timeout=10) as response:
        body = response.read().decode("utf-8", errors="ignore")

    rows = list(csv.DictReader(StringIO(body)))
    if not rows:
        return {"symbol": symbol, "status": "provider_empty"}

    row = rows[0]
    return {
        "symbol": symbol,
        "status": "ok",
        "date": row.get("Date"),
        "time": row.get("Time"),
        "open": _to_float(row.get("Open")),
        "high": _to_float(row.get("High")),
        "low": _to_float(row.get("Low")),
        "close": _to_float(row.get("Close")),
        "volume": _to_float(row.get("Volume")),
    }


def run_quotes(watchlist_path: str | Path, isin_to_symbol_path: str | Path, out_dir: str | Path) -> dict:
    watchlist = read_json(watchlist_path)
    mapping = read_json(isin_to_symbol_path) if Path(isin_to_symbol_path).exists() else {}

    out_path = Path(out_dir)
    ensure_dir(out_path)
    date_str = datetime.now().strftime("%Y%m%d")
    quotes_path = out_path / f"quotes_{date_str}.jsonl"
    baseline_path = out_path / "volume_baseline.json"
    baseline = load_volume_baseline(baseline_path)

    count = 0
    for item in watchlist.get("items", []):
        isin = item.get("isin")
        symbol = mapping.get(isin)

        quote = {
            "fetched_at": now_iso_tz(),
            "isin": isin,
            "name": item.get("name"),
            "symbol": symbol,
        }

        if not symbol:
            quote["status"] = "missing_mapping"
            append_jsonl(quotes_path, quote)
            count += 1
            continue

        try:
            provider_data = fetch_stooq_latest(symbol)
            quote.update(provider_data)
        except Exception as exc:
            quote.update({"status": "provider_error", "error": str(exc)})

        if quote.get("status") == "ok":
            update_volume_baseline(baseline, str(isin), quote.get("volume"))
        append_jsonl(quotes_path, quote)
        count += 1

    save_volume_baseline(baseline_path, baseline)
    return {"quotes_path": str(quotes_path), "count": count}
