from __future__ import annotations

import re

SOURCE_BOOST = ("ir", "ad-hoc", "regulatory")
POSITIVE_TERMS = ("earnings", "guidance", "acquisition", "outlook", "contract", "approval", "partnership")
NEGATIVE_TERMS = (
    "warning",
    "profit warning",
    "gewinnwarnung",
    "downgrade",
    "analyst downgrade",
    "guidance cut",
    "prognose gesenkt",
    "capital raise",
    "capital increase",
    "kapitalerhoehung",
    "share offering",
    "regulatory risk",
    "regulatorisches risiko",
    "probe",
    "investigation",
    "lawsuit",
    "negative ad-hoc",
    "ad-hoc",
    "recall",
    "cut",
)
STOPWORDS = {"ag", "inc", "corp", "corporation", "registered", "shares", "namens-aktien", "o", "n"}


def _aliases(instrument: dict) -> list[str]:
    aliases = {
        str(instrument.get("symbol") or "").split(".", 1)[0].lower(),
        str(instrument.get("isin") or "").lower(),
    }
    tokens = re.findall(r"[a-z0-9]+", str(instrument.get("name") or "").lower())
    core = [token for token in tokens if len(token) > 2 and token not in STOPWORDS]
    aliases.update(core[:3])
    if len(core) >= 2:
        aliases.add(" ".join(core[:2]))
    return [alias for alias in aliases if alias]


def _match(item: dict, aliases: list[str]) -> bool:
    text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
    return any(alias in text for alias in aliases)


def score_news(news_items: list[dict], instrument: dict) -> dict:
    aliases = _aliases(instrument)
    matched = [item for item in news_items if _match(item, aliases)]
    if not matched:
        return {"score": 0, "status": "ok", "matched_count": 0, "negative_hits": 0, "drivers": []}

    source_hits = 0
    positive_hits = 0
    negative_hits = 0
    for item in matched[:8]:
        source_text = str(item.get("source") or "").lower()
        merged = f"{item.get('title', '')} {item.get('summary', '')}".lower()
        source_hits += 1 if any(marker in source_text for marker in SOURCE_BOOST) else 0
        positive_hits += sum(1 for term in POSITIVE_TERMS if term in merged)
        negative_hits += sum(1 for term in NEGATIVE_TERMS if term in merged)

    raw_score = min(3, source_hits + min(2, positive_hits))
    drivers: list[str] = []
    if source_hits:
        drivers.append("regulatory_source")
    if positive_hits:
        drivers.append("event_news")
    if negative_hits:
        drivers.append("negative_news")
        drivers.append("news_burden")

    return {
        "score": raw_score,
        "status": "ok",
        "matched_count": len(matched),
        "negative_hits": negative_hits,
        "drivers": drivers,
    }
