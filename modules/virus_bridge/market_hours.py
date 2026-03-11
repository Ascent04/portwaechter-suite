from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo


TZ_BERLIN = ZoneInfo("Europe/Berlin")


WINDOWS = {
    "XETRA": (time(9, 0), time(17, 30), "09:00 Uhr"),
    "NASDAQ": (time(15, 30), time(22, 0), "15:30 Uhr"),
    "NYSE": (time(15, 30), time(22, 0), "15:30 Uhr"),
    "L&S": (time(7, 30), time(23, 0), "07:30 Uhr"),
}


def _as_berlin(now_dt: datetime | None) -> datetime:
    if now_dt is None:
        return datetime.now(TZ_BERLIN)
    if now_dt.tzinfo is None:
        return now_dt.replace(tzinfo=TZ_BERLIN)
    return now_dt.astimezone(TZ_BERLIN)


def _is_weekday(dt: datetime) -> bool:
    return dt.weekday() < 5


def get_market_status(asset_meta: dict | None, now_dt: datetime | None, cfg: dict | None = None) -> dict:
    del cfg
    market = str((asset_meta or {}).get("market") or "UNKNOWN").strip().upper()
    current = _as_berlin(now_dt)
    base = {
        "is_open": False,
        "market": market,
        "local_time": current.strftime("%Y-%m-%d %H:%M"),
        "next_open_hint": "Marktzeit manuell pruefen",
    }
    window = WINDOWS.get(market)
    if window is None:
        return base

    start, end, next_open = window
    base["next_open_hint"] = next_open
    if not _is_weekday(current):
        return base

    start_dt = current.replace(hour=start.hour, minute=start.minute, second=0, microsecond=0)
    end_dt = current.replace(hour=end.hour, minute=end.minute, second=0, microsecond=0)
    if start_dt <= current <= end_dt:
        return {**base, "is_open": True}

    if current < start_dt:
        return base

    next_day = current + timedelta(days=1)
    if next_day.weekday() >= 5:
        return base
    return base
