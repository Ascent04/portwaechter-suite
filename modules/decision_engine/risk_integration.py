from __future__ import annotations

import json
from pathlib import Path

from modules.risk.position_sizing import adjust_position_size, compute_volatility, recommended_position_multiplier
from modules.validation.monitor import evaluate_90_day_status


def _recent_outcomes(cfg: dict, limit_files: int = 30) -> list[dict]:
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    files = sorted((root / "data" / "performance").glob("outcomes_*.jsonl"))[-limit_files:]
    rows = []
    for p in files:
        try:
            with p.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def apply_position_sizing(candidates: list[dict], cfg: dict, regime: str) -> list[dict]:
    status = evaluate_90_day_status(cfg)
    if not status.get("phase_complete", False):
        return candidates

    outcomes = _recent_outcomes(cfg)
    volatility = compute_volatility(outcomes, horizon="3d")
    multiplier = recommended_position_multiplier(volatility, regime)
    base_size = float(cfg.get("decision", {}).get("base_position_size", 1.0) or 1.0)

    for c in candidates:
        c["position_multiplier"] = multiplier
        c["base_position_size"] = base_size
        c["recommended_position_size"] = adjust_position_size(base_size, multiplier)
    return candidates
