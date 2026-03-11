from __future__ import annotations

import logging
from pathlib import Path

from modules.common.runtime_dirs import ensure_runtime_directories
from modules.common.utils import read_json

log = logging.getLogger(__name__)


def _root_dir(cfg: dict) -> Path:
    return Path(cfg.get("app", {}).get("root_dir", Path.cwd()))


def _proposal_root(cfg: dict) -> Path:
    rel = ((cfg.get("integration") or {}).get("bridge") or {}).get("proposal_dir", "data/integration/signal_proposals")
    path = Path(rel)
    return path if path.is_absolute() else _root_dir(cfg) / path


def load_pending_proposals(cfg) -> list[dict]:
    ensure_runtime_directories(cfg)
    root = _proposal_root(cfg)
    if not root.exists():
        return []

    proposals: list[dict] = []
    for path in sorted(root.rglob("proposal_*.json")):
        try:
            data = read_json(path)
        except Exception as exc:
            log.warning("virus_bridge_bad_proposal path=%s error=%s", path, exc)
            continue
        if not isinstance(data, dict):
            log.warning("virus_bridge_bad_proposal path=%s error=not_a_dict", path)
            continue
        proposals.append({**data, "_path": str(path)})
    proposals.sort(key=lambda row: (str(row.get("timestamp") or ""), str(row.get("proposal_id") or "")))
    return proposals


def dedupe_pending_proposals(proposals: list[dict]) -> list[dict]:
    best_by_key: dict[tuple[str, str, str, str], dict] = {}
    for proposal in proposals or []:
        asset = proposal.get("asset") or {}
        key = (
            str(asset.get("symbol") or asset.get("isin") or "").upper(),
            str(proposal.get("direction") or "").lower(),
            str(proposal.get("market_regime") or "").lower(),
            str(proposal.get("classification") or "").upper(),
        )
        current = best_by_key.get(key)
        if current is None:
            best_by_key[key] = proposal
            continue

        score = float(proposal.get("score", 0) or 0)
        current_score = float(current.get("score", 0) or 0)
        if score > current_score:
            best_by_key[key] = proposal
            continue
        if score == current_score and str(proposal.get("timestamp") or "") > str(current.get("timestamp") or ""):
            best_by_key[key] = proposal

    deduped = list(best_by_key.values())
    deduped.sort(key=lambda row: (str(row.get("timestamp") or ""), str(row.get("proposal_id") or "")))
    return deduped
