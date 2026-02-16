from __future__ import annotations

from pathlib import Path

from modules.common.utils import now_iso_tz, read_json, write_json


def build_watchlist(latest_snapshot_path: str | Path, out_path: str | Path) -> dict:
    snapshot = read_json(latest_snapshot_path)
    positions = snapshot.get("positions", [])

    core_items = []
    for pos in positions:
        if pos.get("instrument_type") not in {"stock", "etf"}:
            continue
        if not pos.get("isin"):
            continue
        core_items.append({"isin": pos.get("isin"), "name": pos.get("name")})

    watchlist = {
        "generated_at": now_iso_tz(),
        "asof": snapshot.get("asof"),
        "items": core_items,
    }
    write_json(out_path, watchlist)
    return watchlist
