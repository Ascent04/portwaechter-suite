from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

from modules.common.utils import append_jsonl, ensure_dir, now_iso_tz, read_json, write_json
from modules.radar.universe import build_universe


def _item_hash(source: str, title: str, link: str) -> str:
    payload = f"{source}|{title}|{link}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def pull_radar_feeds(cfg: dict, out_dir: str | Path) -> str:
    import feedparser

    out_path = Path(out_dir)
    ensure_dir(out_path)

    dedup_path = out_path / "dedup_set.json"
    dedup_set = set(read_json(dedup_path)) if dedup_path.exists() else set()

    date_tag = datetime.now().strftime("%Y%m%d")
    items_path = out_path / f"radar_items_{date_tag}.jsonl"

    universe = build_universe(cfg)
    for entity in universe:
        if entity.get("type") != "feed":
            continue

        source_name = entity.get("name") or entity.get("url")
        source_url = entity.get("url")
        parsed = feedparser.parse(source_url)

        for entry in parsed.entries:
            title = (entry.get("title") or "").strip()
            link = (entry.get("link") or "").strip()
            summary = (entry.get("summary") or "").strip()
            item_id = _item_hash(source_name, title, link)
            if item_id in dedup_set:
                continue

            dedup_set.add(item_id)
            append_jsonl(
                items_path,
                {
                    "id": item_id,
                    "source": source_name,
                    "source_url": source_url,
                    "title": title,
                    "summary": summary,
                    "link": link,
                    "published": entry.get("published") or entry.get("updated"),
                    "pulled_at": now_iso_tz(),
                },
            )

    write_json(dedup_path, sorted(dedup_set))
    if not items_path.exists():
        items_path.write_text("", encoding="utf-8")
    return str(items_path)
