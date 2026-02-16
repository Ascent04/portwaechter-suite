from __future__ import annotations

from pathlib import Path

from modules.common.utils import now_iso_tz, read_json, write_json


def build_entities(latest_snapshot_path: str | Path, out_path: str | Path) -> dict:
    snapshot = read_json(latest_snapshot_path)

    entities = []
    for pos in snapshot.get("positions", []):
        name = pos.get("name")
        isin = pos.get("isin")
        if not name or not isin:
            continue
        entities.append({
            "isin": isin,
            "name": name,
            "keywords": [name, isin],
        })

    payload = {
        "generated_at": now_iso_tz(),
        "entities": entities,
    }
    write_json(out_path, payload)
    return payload
