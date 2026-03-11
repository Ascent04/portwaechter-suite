from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from modules.common.config import load_config

DEFAULTS: dict[str, Any] = {
    "bot_identity": {"display_name": "CB Fund Desk"},
    "notifications": {
        "quiet_hours": {
            "enabled": True,
            "start": "22:00",
            "end": "08:30",
            "timezone": "Europe/Berlin",
        },
        "allow_critical_during_quiet_hours": True,
    },
    "integration": {
        "bridge": {
            "proposal_dir": "data/integration/signal_proposals",
            "consumed_dir": "data/integration/consumed",
            "default_budget_eur": 5000,
        }
    },
    "hedgefund": {
        "budget_eur": 5000,
        "max_positions": 3,
        "max_risk_per_trade_pct": 1.0,
        "max_total_exposure_pct": 60,
        "sizing": {
            "high_conf_min_eur": 1000,
            "high_conf_max_eur": 1500,
            "medium_conf_min_eur": 750,
            "medium_conf_max_eur": 1000,
            "speculative_min_eur": 0,
            "speculative_max_eur": 500,
        },
    },
    "api_governor": {
        "enabled": True,
        "provider": "twelvedata",
        "minute_limit_soft": 45,
        "minute_limit_hard": 55,
        "per_run_budget": 20,
        "batch_only": True,
        "allow_symbol_search_runtime": False,
        "max_universe_per_run": 30,
        "rotate_universe_chunks": True,
        "preferred_scan_interval_minutes": 5,
        "degrade_mode": {
            "enabled": True,
            "skip_non_holdings_first": True,
            "skip_low_priority_scanner_assets": True,
            "holdings_always_first": True,
        },
        "state_file": "data/api_governor/state.json",
        "metrics_file": "data/api_governor/usage_YYYYMMDD.jsonl",
        "v2_primary_provider": True,
        "disable_v1_twelvedata_when_v2_active": True,
    },
    "v2": {
        "data_dir": "data/v2",
        "symbol_map_path": "config/symbol_map_v2.json",
        "scanner_universe_path": "config/scanner_universe_v2.json",
        "watchlist_path": "data/watchlist/watchlist.json",
        "env_file": "/etc/portwaechter/portwaechter.env",
        "quiet_hours": {"start": "22:00", "end": "08:30"},
        "marketdata": {"batch_size": 8, "timeout_sec": 10, "max_live_fallback_symbols": 8, "max_retry_symbols": 12},
        "telegram": {
            "watch_max_per_day": 10,
            "action_max_per_day": 3,
            "defense_max_per_day": 5,
            "cooldown_minutes": 90,
        },
    }
}


def _merge_defaults(target: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    for key, value in defaults.items():
        if isinstance(value, dict):
            current = target.get(key)
            if not isinstance(current, dict):
                target[key] = deepcopy(value)
                continue
            _merge_defaults(current, value)
            continue
        target.setdefault(key, value)
    return target


def load_v2_config(path: str = "config/config.yaml") -> dict[str, Any]:
    cfg = load_config(path)
    return _merge_defaults(cfg, deepcopy(DEFAULTS))


def root_dir(cfg: dict[str, Any]) -> Path:
    configured = cfg.get("app", {}).get("root_dir", Path.cwd())
    return Path(configured)


def data_dir(cfg: dict[str, Any]) -> Path:
    rel = cfg.get("v2", {}).get("data_dir", "data/v2")
    path = Path(rel)
    return path if path.is_absolute() else root_dir(cfg) / path


def symbol_map_path(cfg: dict[str, Any]) -> Path:
    rel = cfg.get("v2", {}).get("symbol_map_path", "config/symbol_map_v2.json")
    path = Path(rel)
    return path if path.is_absolute() else root_dir(cfg) / path


def scanner_universe_path(cfg: dict[str, Any]) -> Path:
    rel = cfg.get("v2", {}).get("scanner_universe_path", "config/scanner_universe_v2.json")
    path = Path(rel)
    return path if path.is_absolute() else root_dir(cfg) / path


def watchlist_path(cfg: dict[str, Any]) -> Path:
    rel = cfg.get("v2", {}).get("watchlist_path", "data/watchlist/watchlist.json")
    path = Path(rel)
    return path if path.is_absolute() else root_dir(cfg) / path


def env_file_path(cfg: dict[str, Any]) -> Path:
    rel = cfg.get("v2", {}).get("env_file", "/etc/portwaechter/portwaechter.env")
    path = Path(rel)
    return path if path.is_absolute() else root_dir(cfg) / path


def load_env_file(cfg: dict[str, Any]) -> dict[str, str]:
    path = env_file_path(cfg)
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        values[key.strip()] = value.strip().strip("'").strip('"')
    return values


def resolve_env_value(cfg: dict[str, Any], env_name: str) -> str | None:
    import os

    value = os.getenv(env_name)
    if value:
        return value
    return load_env_file(cfg).get(env_name) or None


def quiet_hours(cfg: dict[str, Any]) -> dict[str, str]:
    return cfg.get("v2", {}).get("quiet_hours", {"start": "22:00", "end": "08:30"})


def v2_marketdata(cfg: dict[str, Any]) -> dict[str, Any]:
    return cfg.get("v2", {}).get("marketdata", {})


def v2_telegram(cfg: dict[str, Any]) -> dict[str, Any]:
    return cfg.get("v2", {}).get("telegram", {})


def api_governor(cfg: dict[str, Any]) -> dict[str, Any]:
    return cfg.get("api_governor", {})
