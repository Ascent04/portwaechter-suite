from __future__ import annotations

from pathlib import Path

from modules.common.utils import read_json
from modules.v2.config import scanner_universe_path, watchlist_path
from modules.v2.symbols import resolve_isin


def _normalize_item(item: dict) -> dict | None:
    symbol = str(item.get("symbol") or "").strip().upper()
    isin = item.get("isin")
    if not symbol and not isin:
        return None
    return {
        "symbol": symbol or None,
        "isin": isin,
        "name": item.get("name") or symbol or isin,
        "country": item.get("country"),
        "sector": item.get("sector"),
        "theme": item.get("theme"),
        "group": item.get("group", "scanner"),
    }


def _watchlist_items(cfg: dict) -> list[dict]:
    path = watchlist_path(cfg)
    if not path.exists():
        return []
    data = read_json(path)
    raw_items = data.get("items", []) if isinstance(data, dict) else []
    items: list[dict] = []
    for item in raw_items:
        mapping = resolve_isin(str(item.get("isin") or ""), cfg=cfg)
        normalized = _normalize_item(
            {
                "symbol": item.get("symbol") or (mapping.get("symbol") if mapping else None),
                "isin": item.get("isin"),
                "name": item.get("name"),
                "country": item.get("country") or (mapping.get("country") if mapping else None),
                "sector": item.get("sector") or (mapping.get("sector") if mapping else None),
                "theme": item.get("theme") or (mapping.get("theme") if mapping else None),
                "group": "scanner",
            }
        )
        if normalized:
            items.append(normalized)
    return items


def load_scanner_universe(cfg: dict) -> list[dict]:
    path = scanner_universe_path(cfg)
    data = read_json(path) if Path(path).exists() else {"items": []}
    raw_items = data if isinstance(data, list) else data.get("items", [])
    universe = [item for item in (_normalize_item(row) for row in raw_items) if item]
    universe.extend(_watchlist_items(cfg))
    return universe


def merge_universes(holdings: list[dict], scanner: list[dict]) -> list[dict]:
    merged: list[dict] = []
    lookup: dict[str, dict] = {}
    for item in [*scanner, *holdings]:
        keys = [str(item.get("isin") or "").strip(), str(item.get("symbol") or "").strip().upper()]
        row = next((lookup[key] for key in keys if key and key in lookup), None)
        if row is None:
            row = {}
            merged.append(row)
        for field in ("symbol", "isin", "name", "country", "sector", "theme", "market_value_eur", "weight_pct"):
            if row.get(field) in (None, "", 0, 0.0):
                row[field] = item.get(field)
        row["group"] = "holding" if item.get("group") == "holding" or row.get("group") == "holding" else "scanner"
        for key in keys:
            if key:
                lookup[key] = row
    return merged
