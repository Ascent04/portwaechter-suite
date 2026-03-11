from __future__ import annotations

import json
import re
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

REASONS_DE = {
    "volume_red": "Ungewöhnlich hohes Volumen",
    "multi_factor": "Kombiniertes Signal (Preis/Volumen/News)",
    "news": "News-Impuls",
}
CONF_DE = {"high": "hoch", "medium": "mittel", "low": "niedrig", "speculative": "spekulativ"}


def latest(path: Path, pattern: str) -> Path | None:
    files = sorted(path.glob(pattern))
    return files[-1] if files else None


def read_jsonl(path: Path | None) -> list[dict]:
    if not path or not path.exists():
        return []
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def now_berlin(tz_name: str) -> datetime:
    return datetime.now(ZoneInfo(tz_name or "Europe/Berlin"))


def in_quiet_hours(now: datetime) -> bool:
    return now.time() >= time(22, 0) or now.time() < time(7, 0)


def human_reasons(raw_reasons: list[str]) -> str:
    if not raw_reasons:
        return "Signal-Auffälligkeit"
    out: list[str] = []
    for reason in raw_reasons:
        key = str(reason).split(":", 1)[0].split("=", 1)[0]
        out.append(REASONS_DE.get(key, str(reason)))
    return ", ".join(dict.fromkeys(out))


def build_watch_message(candidate: dict) -> str:
    lines = [
        f"WATCH: {candidate.get('name') or 'Unbekannt'} ({candidate.get('isin') or '-'})",
        f"Grund: {human_reasons(candidate.get('reasons', []))}",
    ]

    score = candidate.get("score")
    if score is not None:
        confidence = str(candidate.get("confidence") or "").strip().lower()
        conf_txt = CONF_DE.get(confidence, confidence or "mittel")
        lines.append(f"Score: {score} | Confidence: {conf_txt}")

    lines.append(f"Regime: {candidate.get('regime') or 'neutral'}")

    source = str(candidate.get("news_source") or "").strip()
    title = str(candidate.get("news_title") or "").strip()
    if source or title:
        news_short = f"{source}: {title}".strip(": ")
        if news_short:
            lines.append(f"News: {news_short[:220]}")

    lines.append("Beobachten, keine Handlungsempfehlung.")
    return "\n".join(lines)[:1190]


def extract_intraday_from_reasons(reasons: list[str]) -> float | None:
    for reason in reasons:
        match = re.search(r"price_intraday=([+-]?\d+(?:\.\d+)?)%", str(reason))
        if match:
            return float(match.group(1))
    return None


def is_volume_candidate_allowed(candidate: dict, min_score: float, min_move: float) -> bool:
    if candidate.get("alert_type") != "volume_red":
        return True

    score = candidate.get("score")
    matched_news = bool(candidate.get("matched_news"))
    pct_move = candidate.get("pct_move_intraday")

    return (isinstance(score, (int, float)) and float(score) >= min_score) or matched_news or (
        isinstance(pct_move, (int, float)) and abs(float(pct_move)) >= min_move
    )
