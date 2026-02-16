from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from modules.common.utils import read_json, write_json


def load_state(path: str | Path) -> dict:
    state_path = Path(path)
    if not state_path.exists():
        return {}

    try:
        data = read_json(state_path)
    except Exception:
        return {}

    return data if isinstance(data, dict) else {}


def save_state(path: str | Path, state: dict) -> None:
    write_json(path, state)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None

    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def should_send(key: str, now_iso: str, cooldown_min: int, state: dict) -> bool:
    if cooldown_min <= 0:
        return True

    sent = state.get("sent", {}) if isinstance(state, dict) else {}
    last_sent_iso = sent.get(key)
    if not last_sent_iso:
        return True

    now_dt = _parse_iso(now_iso)
    last_dt = _parse_iso(last_sent_iso)
    if not now_dt or not last_dt:
        return True

    return (now_dt - last_dt) >= timedelta(minutes=cooldown_min)


def mark_sent(key: str, now_iso: str, state: dict) -> None:
    if "sent" not in state or not isinstance(state["sent"], dict):
        state["sent"] = {}
    state["sent"][key] = now_iso
