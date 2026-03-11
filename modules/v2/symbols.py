from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

from modules.common.utils import now_iso_tz, read_json
from modules.v2.config import load_v2_config, symbol_map_path

log = logging.getLogger(__name__)


def load_symbol_map(cfg: dict | None = None, path: str | Path | None = None) -> dict[str, dict]:
    active_cfg = cfg or load_v2_config()
    map_path = Path(path) if path else symbol_map_path(active_cfg)
    if not map_path.exists():
        return {}

    try:
        data = read_json(map_path)
    except Exception as exc:
        log.warning("v2.symbol_map.read_failed path=%s error=%s", map_path, exc)
        return {}
    return data if isinstance(data, dict) else {}


def resolve_isin(isin: str, cfg: dict | None = None, path: str | Path | None = None) -> dict | None:
    if not isin:
        return None
    entry = load_symbol_map(cfg=cfg, path=path).get(str(isin))
    if not isinstance(entry, dict):
        return None
    symbol = entry.get("symbol")
    return {
        "symbol": str(symbol) if symbol else None,
        "provider": entry.get("provider", "twelvedata"),
        "name": entry.get("name"),
        "sector": entry.get("sector"),
        "theme": entry.get("theme"),
        "country": entry.get("country"),
        "status": entry.get("status", "ok"),
    }


def build_missing_mapping_report(
    items: Iterable[dict] | None = None,
    cfg: dict | None = None,
    path: str | Path | None = None,
) -> dict:
    missing: list[dict] = []
    for item in items or []:
        isin = str(item.get("isin") or "").strip()
        if not isin:
            continue
        if resolve_isin(isin, cfg=cfg, path=path):
            continue
        row = {"isin": isin, "name": item.get("name"), "group": item.get("group")}
        log.warning("v2.symbol_map.missing isin=%s name=%s", isin, item.get("name"))
        missing.append(row)

    return {
        "generated_at": now_iso_tz(),
        "missing_count": len(missing),
        "missing": missing,
    }
