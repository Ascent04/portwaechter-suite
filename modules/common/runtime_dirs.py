from __future__ import annotations

from pathlib import Path

from modules.common.utils import ensure_dir


def _root_dir(cfg: dict) -> Path:
    return Path(cfg.get("app", {}).get("root_dir", Path.cwd()))


def _resolved_dir(cfg: dict, value: str) -> Path:
    path = Path(str(value or "").strip())
    return path if path.is_absolute() else _root_dir(cfg) / path


def runtime_directories(cfg: dict) -> dict[str, Path]:
    bridge_cfg = ((cfg.get("integration") or {}).get("bridge") or {})
    return {
        "proposal_queue": _resolved_dir(cfg, bridge_cfg.get("proposal_dir", "data/integration/signal_proposals")),
        "consumed_queue": _resolved_dir(cfg, bridge_cfg.get("consumed_dir", "data/integration/consumed")),
        "trade_candidates": _root_dir(cfg) / "data" / "virus_bridge" / "trade_candidates",
        "executions": _root_dir(cfg) / "data" / "virus_bridge" / "executions",
        "exits": _root_dir(cfg) / "data" / "virus_bridge" / "exits",
        "ticket_lifecycle": _root_dir(cfg) / "data" / "virus_bridge" / "ticket_lifecycle",
        "performance": _root_dir(cfg) / "data" / "virus_bridge" / "performance",
        "organism_monthly": _root_dir(cfg) / "data" / "organism" / "monthly",
    }


def ensure_runtime_directories(cfg: dict) -> dict[str, str]:
    directories = runtime_directories(cfg)
    for path in directories.values():
        ensure_dir(path)
    return {key: str(path) for key, path in directories.items()}
