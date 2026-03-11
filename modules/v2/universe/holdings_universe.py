from __future__ import annotations

from pathlib import Path

from modules.common.utils import read_json
from modules.v2.config import root_dir
from modules.v2.symbols import resolve_isin


def _latest_snapshot(cfg: dict) -> Path | None:
    snapshots = sorted((root_dir(cfg) / "data" / "snapshots").glob("portfolio_*.json"))
    return snapshots[-1] if snapshots else None


def enrich_with_weights(snapshot: dict, cfg: dict | None = None) -> list[dict]:
    positions = snapshot.get("positions", []) if isinstance(snapshot, dict) else []
    total = sum(float(pos.get("market_value_eur", 0) or 0) for pos in positions)
    items: list[dict] = []
    for pos in positions:
        value = float(pos.get("market_value_eur", 0) or 0)
        mapping = resolve_isin(str(pos.get("isin") or ""), cfg=cfg)
        items.append(
            {
                "isin": pos.get("isin"),
                "name": pos.get("name"),
                "market_value_eur": round(value, 2),
                "weight_pct": round((value / total) * 100, 2) if total else 0.0,
                "symbol": mapping.get("symbol") if mapping else None,
                "country": mapping.get("country") if mapping else None,
                "sector": mapping.get("sector") if mapping else None,
                "theme": mapping.get("theme") if mapping else None,
                "group": "holding",
            }
        )
    return items


def load_current_holdings(cfg: dict) -> list[dict]:
    latest = _latest_snapshot(cfg)
    if latest is None:
        return []
    snapshot = read_json(latest)
    return enrich_with_weights(snapshot, cfg=cfg)
