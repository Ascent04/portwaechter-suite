from __future__ import annotations

import json
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from modules.common.utils import now_iso_tz


KEYWORDS = (
    "earnings",
    "guidance",
    "contract",
    "acquisition",
    "approval",
    "warning",
    "outlook",
)

SOURCE_BOOST = ("ir", "ad-hoc", "regulatory")


def _read_jsonl(path: str | Path) -> list[dict]:
    rows: list[dict] = []
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
    dt = _parse_date(published)
    if not dt:
        return 0.0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    age_hours = (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds() / 3600
    return round(max(0.0, 10.0 - (age_hours / 6.0)), 2)


def rank_radar(items_jsonl: str | Path) -> dict:
    items = _read_jsonl(items_jsonl)
    ranked: list[dict] = []

    for item in items:
        text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
        hits = [kw for kw in KEYWORDS if kw in text]

        score = _recency_score(item.get("published"))
        score += len(hits) * 2

        source = str(item.get("source", "")).lower()
        if any(flag in source for flag in SOURCE_BOOST):
            score += 3

        reasons = []
        if hits:
            reasons.append(f"keywords={','.join(hits)}")
        if score > 0:
            reasons.append(f"recency_score={round(_recency_score(item.get('published')), 2)}")
        if any(flag in source for flag in SOURCE_BOOST):
            reasons.append("source_boost")

        ranked.append({**item, "score": round(score, 2), "reasons": reasons})

    ranked.sort(key=lambda row: row.get("score", 0), reverse=True)
    return {"generated_at": now_iso_tz(), "top": ranked[:10]}
