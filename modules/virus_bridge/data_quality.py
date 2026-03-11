from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


def _timezone(cfg: dict) -> ZoneInfo:
    return ZoneInfo(str(cfg.get("app", {}).get("timezone", "Europe/Berlin")) or "Europe/Berlin")


def _coerce_now(now_dt: datetime | None, cfg: dict) -> datetime:
    tz = _timezone(cfg)
    if now_dt is None:
        return datetime.now(tz)
    if now_dt.tzinfo is None:
        return now_dt.replace(tzinfo=tz)
    return now_dt.astimezone(tz)


def _quote_timestamp(quote: dict | None, cfg: dict) -> datetime | None:
    if not isinstance(quote, dict):
        return None
    raw = str(quote.get("timestamp") or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=_timezone(cfg))
    return parsed.astimezone(_timezone(cfg))


def _max_quote_age_minutes(cfg: dict) -> float:
    try:
        return float(cfg.get("data_quality", {}).get("max_quote_age_minutes", 15) or 15)
    except (TypeError, ValueError):
        return 15.0


def compute_quote_age_minutes(quote: dict | None, now_dt, cfg: dict) -> float | None:
    quote_ts = _quote_timestamp(quote, cfg)
    if quote_ts is None:
        return None
    now = _coerce_now(now_dt, cfg)
    return round(max(0.0, (now - quote_ts).total_seconds() / 60.0), 2)


def is_quote_fresh(quote: dict | None, now_dt, cfg: dict) -> bool:
    age = compute_quote_age_minutes(quote, now_dt, cfg)
    return age is not None and age <= _max_quote_age_minutes(cfg)
