from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from modules.common.utils import now_iso_tz, read_json


def _runtime_path(cfg: dict) -> Path:
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    return root / "data" / "runtime_overrides.json"


def _deep_merge(target: dict, incoming: dict) -> dict:
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            target[key] = _deep_merge(target[key], value)
        else:
            target[key] = value
    return target


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    tmp.replace(path)


def load_runtime_overrides(cfg: dict) -> dict:
    path = _runtime_path(cfg)
    if not path.exists():
        return {}
    try:
        data = read_json(path)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def save_runtime_overrides(cfg: dict, overrides: dict) -> None:
    _atomic_write_json(_runtime_path(cfg), overrides if isinstance(overrides, dict) else {})


def apply_profile_overrides(cfg_dict: dict, profile_dict: dict) -> dict:
    merged = deepcopy(cfg_dict)
    if isinstance(profile_dict, dict):
        _deep_merge(merged, profile_dict)
    return merged


def get_current_profile(cfg: dict) -> str:
    overrides = load_runtime_overrides(cfg)
    current = (overrides.get("alert_profile") or {}).get("current")
    if current:
        return str(current)
    return str(cfg.get("alert_profiles", {}).get("current", "normal"))


def set_profile(profile_name: str, cfg: dict) -> dict:
    profile = str(profile_name).strip().lower()
    if profile == "balanced":
        profile = "normal"

    profiles = cfg.get("alert_profiles", {}).get("profiles", {})
    if profile not in profiles:
        raise ValueError(f"unknown_profile:{profile}")

    overrides = load_runtime_overrides(cfg)
    overrides["alert_profile"] = {
        "current": profile,
        "updated_at": now_iso_tz(cfg.get("app", {}).get("timezone", "Europe/Berlin")),
    }
    save_runtime_overrides(cfg, overrides)
    return overrides


def set_market_thresholds(cfg: dict, threshold_pct: float | None, min_delta_pct: float | None, off: bool = False) -> dict:
    overrides = load_runtime_overrides(cfg)
    patch = overrides.setdefault("overrides", {}).setdefault("marketdata_alerts", {})

    if off:
        patch["enabled"] = False
        save_runtime_overrides(cfg, overrides)
        return overrides

    if threshold_pct is None or min_delta_pct is None:
        raise ValueError("thresholds_required")

    patch["enabled"] = True
    patch["threshold_pct"] = float(threshold_pct)
    patch["min_delta_pct"] = float(min_delta_pct)

    group_defaults = patch.setdefault("group_defaults", {})
    for group in ("holdings", "radar"):
        row = group_defaults.setdefault(group, {})
        row["threshold_pct"] = float(threshold_pct)
        row["min_delta_pct"] = float(min_delta_pct)

    save_runtime_overrides(cfg, overrides)
    return overrides


def apply_runtime_overrides(cfg: dict) -> dict:
    merged = deepcopy(cfg)
    overrides = load_runtime_overrides(cfg)

    current = str((overrides.get("alert_profile") or {}).get("current") or merged.get("alert_profiles", {}).get("current", "normal"))
    if current == "balanced":
        current = "normal"

    profiles = merged.get("alert_profiles", {}).get("profiles", {})
    if current in profiles:
        merged = apply_profile_overrides(merged, profiles[current])
        merged.setdefault("alert_profiles", {})["current"] = current

    # Backward compatibility for legacy payloads containing inline profile values
    legacy_values = (overrides.get("alert_profile") or {}).get("values")
    if isinstance(legacy_values, dict):
        merged = apply_profile_overrides(merged, legacy_values)

    runtime_patch = overrides.get("overrides")
    if isinstance(runtime_patch, dict):
        _deep_merge(merged, runtime_patch)

    return merged
