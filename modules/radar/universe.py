from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


def _normalize_feed(entry: object) -> dict | None:
    if isinstance(entry, dict):
        url = entry.get("url")
        if not url:
            return None
        return {
            "type": "feed",
            "name": entry.get("name") or url,
            "url": url,
        }

    if isinstance(entry, str) and entry.strip():
        return {"type": "feed", "name": entry.strip(), "url": entry.strip()}

    return None


def _top_publishers(root_dir: Path, limit: int = 5) -> list[dict]:
    news_dir = root_dir / "data" / "news"
    items_files = sorted(news_dir.glob("items_*.jsonl"))
    if not items_files:
        return []

    latest = items_files[-1]
    counts: Counter[str] = Counter()
    with latest.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            source = str(item.get("source", "")).strip()
            if source:
                counts[source] += 1

    return [{"type": "publisher", "name": source} for source, _ in counts.most_common(limit)]


def build_universe(cfg: dict) -> list[dict]:
    root_dir = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    radar_cfg = cfg.get("radar", {}).get("sources", {})
    feeds = radar_cfg.get("rss_feeds", [])

    universe: list[dict] = []
    seen_urls: set[str] = set()

    for entry in feeds:
        normalized = _normalize_feed(entry)
        if not normalized:
            continue
        url = normalized["url"]
        if url in seen_urls:
            continue
        seen_urls.add(url)
        universe.append(normalized)

    universe.extend(_top_publishers(root_dir))
    return universe
