from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from modules.common.config import load_config
from modules.common.utils import now_iso_tz, read_json

HOLDING_BOOST = 5.0
LARGECAP_SCORE = 2.0
US_TECH_SCORE = 3.0
SMALLCAP_SCORE = 2.0
SPAM_PENALTY = 4.0

LARGECAP_KEYWORDS = (
    "dax",
    "mdax",
    "sdax",
    "large cap",
    "largecap",
    "blue chip",
)

US_TECH_KEYWORDS = (
    "ai",
    "artificial intelligence",
    "nvidia",
    "microsoft",
    "apple",
    "alphabet",
    "google",
    "meta",
    "amazon",
    "semiconductor",
    "chip",
)

SMALLCAP_KEYWORDS = (
    "smallcap",
    "small cap",
    "microcap",
    "penny stock",
    "nebenwert",
)

SPAM_KEYWORDS = (
    "anzeige",
    "sponsored",
    "werbung",
    "gewinnspiel",
    "kursrakete",
    "1000%",
    "boersenbrief",
)


def _read_jsonl(path: str | Path) -> list[dict]:
    rows: list[dict] = []
    file_path = Path(path)
    if not file_path.exists():
        return rows

    with file_path.open("r", encoding="utf-8") as fh:
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
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(value)
        except ValueError:
            return None

    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", (title or "").strip().lower())


def _published_dt(item: dict) -> datetime | None:
    return _parse_date(item.get("published_at") or item.get("published") or item.get("pulled_at"))


def _freshness_points(published_dt: datetime | None) -> tuple[float, list[str]]:
    if not published_dt:
        return 0.0, []

    age_hours = (datetime.now(timezone.utc) - published_dt).total_seconds() / 3600
    if age_hours < 2:
        return 3.0, ["Fresh (<2h)"]
    if age_hours < 6:
        return 2.0, []
    if age_hours < 24:
        return 1.0, []
    return 0.0, []


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _load_holding_names(cfg: dict) -> list[str]:
    root_dir = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    snapshots = sorted((root_dir / "data" / "snapshots").glob("portfolio_*.json"))
    if not snapshots:
        return []

    snapshot = read_json(snapshots[-1])
    names: list[str] = []
    for pos in snapshot.get("positions", []):
        name = str(pos.get("name", "")).strip().lower()
        if len(name) >= 4:
            names.append(name)
    return names


def _dedupe_titles(items: list[dict], window_hours: int = 6) -> list[dict]:
    decorated = [(item, _published_dt(item)) for item in items]
    decorated.sort(key=lambda row: row[1] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    accepted: list[dict] = []
    last_seen: dict[str, datetime | None] = {}
    window = timedelta(hours=window_hours)

    for item, published_dt in decorated:
        key = _normalize_title(str(item.get("title", "")))
        if not key:
            continue

        if key in last_seen:
            previous_dt = last_seen[key]
            if previous_dt is None or published_dt is None:
                continue
            if previous_dt - published_dt <= window:
                continue

        accepted.append(item)
        last_seen[key] = published_dt

    return accepted


def rank_radar(items_jsonl: str | Path) -> dict:
    cfg = load_config()
    min_score = float(cfg.get("radar", {}).get("min_score", 4))

    items = _dedupe_titles(_read_jsonl(items_jsonl), window_hours=6)
    holding_names = _load_holding_names(cfg)

    ranked: list[dict] = []
    for item in items:
        title = str(item.get("title", "")).strip()
        source = str(item.get("source", "")).strip()
        text = f"{title} {item.get('summary', '')}".lower()

        score = 0.0
        reasons: list[str] = []

        if holding_names and any(name in text for name in holding_names):
            score += HOLDING_BOOST
            reasons.append("Holding Match")

        if _contains_any(text, LARGECAP_KEYWORDS):
            score += LARGECAP_SCORE
            reasons.append("DAX Keyword")

        if _contains_any(text, US_TECH_KEYWORDS):
            score += US_TECH_SCORE
            reasons.append("AI Keyword")

        if _contains_any(text, SMALLCAP_KEYWORDS):
            score += SMALLCAP_SCORE
            reasons.append("Smallcap Keyword")

        published_dt = _published_dt(item)
        fresh_points, fresh_reasons = _freshness_points(published_dt)
        score += fresh_points
        reasons.extend(fresh_reasons)

        if _contains_any(text, SPAM_KEYWORDS):
            score -= SPAM_PENALTY
            reasons.append("Spam Penalty")

        if score < min_score:
            continue

        ranked.append(
            {
                "title": title,
                "source": source,
                "published_at": published_dt.isoformat() if published_dt else None,
                "score": round(score, 2),
                "reasons": reasons,
            }
        )

    ranked.sort(key=lambda row: (row.get("score", 0), row.get("published_at") or ""), reverse=True)
    return {"generated_at": now_iso_tz(), "top": ranked[:10]}
