from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from modules.common.utils import append_jsonl, ensure_dir, read_json
from modules.v2.config import api_governor as api_governor_cfg
from modules.v2.config import root_dir


def _minute_key(now_dt: datetime) -> str:
    return now_dt.strftime("%Y-%m-%dT%H:%M")


def _state_path(cfg: dict) -> Path:
    rel = str(api_governor_cfg(cfg).get("state_file") or "data/api_governor/state.json")
    path = Path(rel)
    return path if path.is_absolute() else root_dir(cfg) / path


def _metrics_path(cfg: dict, now_dt: datetime | None = None) -> Path:
    stamp = (now_dt or datetime.now()).strftime("%Y%m%d")
    rel = str(api_governor_cfg(cfg).get("metrics_file") or "data/api_governor/usage_YYYYMMDD.jsonl").replace("YYYYMMDD", stamp)
    path = Path(rel)
    return path if path.is_absolute() else root_dir(cfg) / path


def _hard_limit(cfg: dict) -> int:
    return int(api_governor_cfg(cfg).get("minute_limit_hard", 55) or 55)


def _soft_limit(cfg: dict) -> int:
    return int(api_governor_cfg(cfg).get("minute_limit_soft", 45) or 45)


def _default_state(now_dt: datetime | None = None) -> dict[str, Any]:
    ref = now_dt or datetime.now()
    return {
        "current_minute": _minute_key(ref),
        "used_in_current_minute": 0,
        "last_chunk_index": 0,
    }


def _atomic_write_json(path: Path, payload: dict) -> None:
    ensure_dir(path.parent)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    tmp.replace(path)


def load_governor_state(cfg: dict) -> dict:
    path = _state_path(cfg)
    if not path.exists():
        return _default_state()
    try:
        state = read_json(path)
    except Exception:
        return _default_state()
    if not isinstance(state, dict):
        return _default_state()
    merged = _default_state()
    merged.update(state)
    merged["used_in_current_minute"] = int(merged.get("used_in_current_minute", 0) or 0)
    merged["last_chunk_index"] = int(merged.get("last_chunk_index", 0) or 0)
    return merged


def save_governor_state(state: dict, cfg: dict) -> None:
    payload = _default_state()
    if isinstance(state, dict):
        payload.update(state)
    payload["used_in_current_minute"] = int(payload.get("used_in_current_minute", 0) or 0)
    payload["last_chunk_index"] = int(payload.get("last_chunk_index", 0) or 0)
    _atomic_write_json(_state_path(cfg), payload)


def reset_minute_if_needed(state: dict, now_dt: datetime) -> dict:
    current = dict(state or {})
    minute = _minute_key(now_dt)
    if str(current.get("current_minute") or "") != minute:
        current["current_minute"] = minute
        current["used_in_current_minute"] = 0
    current.setdefault("last_chunk_index", 0)
    return current


def can_spend(state: dict, cost: int, cfg: dict) -> bool:
    if not bool(api_governor_cfg(cfg).get("enabled", True)):
        return True
    if cost <= 0:
        return True
    used = int((state or {}).get("used_in_current_minute", 0) or 0)
    return (used + int(cost)) <= _hard_limit(cfg)


def reserve_budget(state: dict, cost: int, cfg: dict) -> dict:
    current = dict(state or {})
    if not can_spend(current, cost, cfg):
        return current
    current["used_in_current_minute"] = int(current.get("used_in_current_minute", 0) or 0) + max(int(cost), 0)
    return current


def remaining_budget(state: dict, cfg: dict) -> int:
    used = int((state or {}).get("used_in_current_minute", 0) or 0)
    return max(_hard_limit(cfg) - used, 0)


def current_mode(state: dict, cfg: dict, run_cost_used: int = 0) -> str:
    governor = api_governor_cfg(cfg)
    if not bool(governor.get("enabled", True)):
        return "normal"
    if remaining_budget(state, cfg) <= 0:
        return "blocked"
    used = int((state or {}).get("used_in_current_minute", 0) or 0)
    run_budget = int(governor.get("per_run_budget", 20) or 20)
    if used >= _soft_limit(cfg) or int(run_cost_used) >= run_budget or remaining_budget(state, cfg) < run_budget:
        return "degraded"
    return "normal"


def log_usage(event: dict, cfg: dict) -> None:
    payload = {
        "timestamp": datetime.now().isoformat(),
        "provider": str(api_governor_cfg(cfg).get("provider") or "twelvedata"),
    }
    if isinstance(event, dict):
        payload.update({key: value for key, value in event.items() if key != "apikey"})
    append_jsonl(_metrics_path(cfg), payload)


def status_snapshot(cfg: dict) -> dict:
    state = reset_minute_if_needed(load_governor_state(cfg), datetime.now())
    return {
        "enabled": bool(api_governor_cfg(cfg).get("enabled", True)),
        "minute_used": int(state.get("used_in_current_minute", 0) or 0),
        "minute_limit_hard": _hard_limit(cfg),
        "mode": current_mode(state, cfg),
        "scanner_throttled": current_mode(state, cfg) != "normal",
        "v2_primary_provider": bool(api_governor_cfg(cfg).get("v2_primary_provider", True)),
        "disable_v1_twelvedata_when_v2_active": bool(
            api_governor_cfg(cfg).get("disable_v1_twelvedata_when_v2_active", True)
        ),
    }
