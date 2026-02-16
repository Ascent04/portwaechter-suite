from __future__ import annotations

import json
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from modules.common.utils import now_iso_tz, write_json


KEYWORDS = ("earnings", "guidance", "contract", "acquisition", "approval", "warning", "outlook")
SOURCE_BOOST = ("ir", "ad-hoc", "regulatory")


def _read_jsonl(path: str | Path) -> list[dict]:
    rows = []
    with Path(path).open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None


def _recency_score(published: str | None) -> float:
    published_dt = _parse_date(published)
    if not published_dt:
        return 0.0

    if published_dt.tzinfo is None:
        published_dt = published_dt.replace(tzinfo=timezone.utc)

    age_hours = (datetime.now(timezone.utc) - published_dt.astimezone(timezone.utc)).total_seconds() / 3600
    return round(max(0.0, 10.0 - (age_hours / 6.0)), 2)


def rank_opportunities(items_jsonl: str | Path, out_json: str | Path) -> dict:
    items = _read_jsonl(items_jsonl)
    ranked = []

    for item in items:
        text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
        hits = [keyword for keyword in KEYWORDS if keyword in text]

        score = _recency_score(item.get("published"))
        score += len(hits) * 2

        source_text = str(item.get("source", "")).lower()
        if any(marker in source_text for marker in SOURCE_BOOST):
            score += 3

        ranked.append({
            **item,
            "score": round(score, 2),
            "keyword_hits": hits,
        })

    ranked.sort(key=lambda row: row.get("score", 0), reverse=True)
    top = ranked[:10]

    output = {
        "generated_at": now_iso_tz(),
        "top": top,
    }
    write_json(out_json, output)
    return output
