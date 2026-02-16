from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_config(path: str = "config/config.yaml") -> dict[str, Any]:
    """Load YAML config with fallback to .yml when default .yaml is absent."""
    cfg_path = Path(path)
    if not cfg_path.is_absolute():
        cfg_path = Path.cwd() / cfg_path

    if not cfg_path.exists() and cfg_path.suffix == ".yaml":
        alt_path = cfg_path.with_suffix(".yml")
        if alt_path.exists():
            cfg_path = alt_path

    if not cfg_path.exists():
        raise FileNotFoundError(f"Config file not found: {cfg_path}")

    with cfg_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    if not isinstance(data, dict):
        raise ValueError("Config root must be a mapping")

    return data
