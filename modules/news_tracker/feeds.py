from __future__ import annotations

import hashlib
from pathlib import Path

from modules.common.utils import append_jsonl, ensure_dir, now_iso_tz, read_json, write_json


def _detect_lang(source: str, title: str, summary: str, entry_lang: str | None) -> str:
    if entry_lang:
        if entry_lang.startswith("de"):
            return "de"
        if entry_lang.startswith("en"):
            return "en"

    merged = f"{title} {summary}".lower()
    if any(token in merged for token in ("über", "für", "nicht", "aktie", "unternehmen")):
        return "de"

    if any(token in source.lower() for token in ("ad-hoc", "bundesanzeiger", "finanznachrichten")):
        return "de"

    return "en"


def _item_hash(title: str, link: str) -> str:
    payload = f"{title}|{link}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def pull_feeds(feed_sources: list, entities: dict, out_dir: str | Path) -> dict:
    import feedparser

    out_path = Path(out_dir)
    ensure_dir(out_path)

    dedup_path = out_path / "dedup_set.json"
    dedup_set = set(read_json(dedup_path)) if dedup_path.exists() else set()

    date_tag = now_iso_tz().split("T", 1)[0].replace("-", "")
    items_path = out_path / f"items_{date_tag}.jsonl"
    if not items_path.exists():
        items_path.write_text("", encoding="utf-8")

    terms = []
    for entity in entities.get("entities", []):
        terms.extend([kw.lower() for kw in entity.get("keywords", []) if kw])

    items = []
    for source in feed_sources:
        source_name = source["name"] if isinstance(source, dict) else str(source)
        source_url = source["url"] if isinstance(source, dict) else str(source)

        parsed = feedparser.parse(source_url)
        for entry in parsed.entries:
            title = (entry.get("title") or "").strip()
            summary = (entry.get("summary") or "").strip()
            link = (entry.get("link") or "").strip()

            merged = f"{title} {summary}".lower()
            if terms and not any(term in merged for term in terms):
                continue

            item_id = _item_hash(title, link)
            if item_id in dedup_set:
                continue

            dedup_set.add(item_id)
            item = {
                "id": item_id,
                "source": source_name,
                "source_url": source_url,
                "title": title,
                "summary": summary,
                "link": link,
                "published": entry.get("published") or entry.get("updated"),
                "lang": _detect_lang(source_name, title, summary, entry.get("language")),
                "pulled_at": now_iso_tz(),
            }
            append_jsonl(items_path, item)
            items.append(item)

    write_json(dedup_path, sorted(dedup_set))
    return {"items_path": str(items_path), "count": len(items), "items": items}
