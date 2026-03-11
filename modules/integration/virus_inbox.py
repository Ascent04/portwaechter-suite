from __future__ import annotations

from pathlib import Path

from modules.common.runtime_dirs import ensure_runtime_directories
from modules.common.utils import ensure_dir, read_json


def _root_dir(cfg: dict) -> Path:
    return Path(cfg.get("app", {}).get("root_dir", Path.cwd()))


def _bridge_cfg(cfg: dict) -> dict:
    return cfg.get("integration", {}).get("bridge", {})


def _proposal_root(cfg: dict) -> Path:
    rel = _bridge_cfg(cfg).get("proposal_dir", "data/integration/signal_proposals")
    path = Path(rel)
    return path if path.is_absolute() else _root_dir(cfg) / path


def _consumed_root(cfg: dict) -> Path:
    rel = _bridge_cfg(cfg).get("consumed_dir", "data/integration/consumed")
    path = Path(rel)
    return path if path.is_absolute() else _root_dir(cfg) / path


def load_pending_signal_proposals(cfg: dict) -> list[dict]:
    ensure_runtime_directories(cfg)
    root = _proposal_root(cfg)
    if not root.exists():
        return []

    proposals: list[dict] = []
    for path in sorted(root.rglob("proposal_*.json")):
        try:
            data = read_json(path)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        proposals.append({**data, "_path": str(path)})
    proposals.sort(key=lambda row: (str(row.get("timestamp") or ""), str(row.get("proposal_id") or "")))
    return proposals


def mark_proposal_consumed(proposal_id: str, cfg: dict) -> bool:
    needle = str(proposal_id or "").strip()
    if not needle:
        return False

    source_path: Path | None = None
    for row in load_pending_signal_proposals(cfg):
        if str(row.get("proposal_id") or "") == needle:
            source_path = Path(str(row.get("_path")))
            break
    if source_path is None or not source_path.exists():
        return False

    day = needle.split("-", 2)[1] if "-" in needle else "unknown"
    target_dir = _consumed_root(cfg) / day
    ensure_dir(target_dir)
    source_path.rename(target_dir / source_path.name)
    return True


def build_trade_candidate_input(signal_proposal: dict) -> dict:
    asset = signal_proposal.get("asset") or {}
    budget = signal_proposal.get("budget_context") or {}
    portfolio = signal_proposal.get("portfolio_context") or {}
    quote = signal_proposal.get("quote") or {}
    return {
        "proposal_id": signal_proposal.get("proposal_id"),
        "source": signal_proposal.get("source"),
        "classification": signal_proposal.get("classification"),
        "symbol": asset.get("symbol"),
        "isin": asset.get("isin"),
        "name": asset.get("name"),
        "direction": signal_proposal.get("direction"),
        "score": signal_proposal.get("score"),
        "signal_strength": signal_proposal.get("signal_strength"),
        "market_regime": signal_proposal.get("market_regime"),
        "reasons": list(signal_proposal.get("reasons") or []),
        "is_holding": bool(portfolio.get("is_holding")),
        "weight_pct": portfolio.get("weight_pct"),
        "budget_eur": budget.get("budget_eur"),
        "suggested_size_min_eur": budget.get("suggested_size_min_eur"),
        "suggested_size_max_eur": budget.get("suggested_size_max_eur"),
        "last_price": quote.get("last_price"),
        "currency": quote.get("currency"),
        "quote_percent_change": quote.get("percent_change"),
        "timestamp": signal_proposal.get("timestamp"),
    }
