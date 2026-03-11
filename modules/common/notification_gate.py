from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo


CRITICAL_MARKERS = ("SAFE MODE", "SYSTEM KRITISCH", "AUDIT FEHLER", "DATA SOURCE FAILURE")


def quiet_hours_config(cfg: dict) -> dict:
    notifications = cfg.get("notifications", {}) if isinstance(cfg.get("notifications"), dict) else {}
    quiet = notifications.get("quiet_hours", {}) if isinstance(notifications.get("quiet_hours"), dict) else {}
    return {
        "enabled": bool(quiet.get("enabled", True)),
        "start": str(quiet.get("start", "22:00")),
        "end": str(quiet.get("end", "08:30")),
        "timezone": str(quiet.get("timezone", cfg.get("app", {}).get("timezone", "Europe/Berlin")) or "Europe/Berlin"),
        "allow_critical": bool(notifications.get("allow_critical_during_quiet_hours", True)),
    }


def _parse_clock(value: str, fallback: str) -> time:
    raw = str(value or fallback).strip()
    try:
        hour, minute = raw.split(":", 1)
        return time(int(hour), int(minute))
    except Exception:
        safe_hour, safe_minute = fallback.split(":", 1)
        return time(int(safe_hour), int(safe_minute))


def current_time(cfg: dict, now: datetime | None = None) -> datetime:
    tz = ZoneInfo(quiet_hours_config(cfg)["timezone"])
    if now is None:
        return datetime.now(tz)
    if now.tzinfo is None:
        return now.replace(tzinfo=tz)
    return now.astimezone(tz)


def quiet_hours_active(cfg: dict, now: datetime | None = None) -> bool:
    settings = quiet_hours_config(cfg)
    if not settings["enabled"]:
        return False
    current = current_time(cfg, now)
    start = _parse_clock(settings["start"], "22:00")
    end = _parse_clock(settings["end"], "08:30")
    if start == end:
        return False
    if start < end:
        return start <= current.time() < end
    return current.time() >= start or current.time() < end


def is_critical_text(text: str) -> bool:
    upper = str(text or "").upper()
    return any(marker in upper for marker in CRITICAL_MARKERS)


def allow_notification(text: str, cfg: dict, critical: bool = False, now: datetime | None = None) -> tuple[bool, str | None]:
    if not quiet_hours_active(cfg, now):
        return True, None
    if quiet_hours_config(cfg)["allow_critical"] and (critical or is_critical_text(text)):
        return True, None
    return False, "quiet_hours_active"
