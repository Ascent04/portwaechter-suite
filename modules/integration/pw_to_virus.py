from __future__ import annotations

from datetime import datetime
from pathlib import Path

from modules.common.utils import ensure_dir, write_json
from modules.v2.telegram.copy import human_reasons, normalize_confidence


def _root_dir(cfg: dict) -> Path:
    return Path(cfg.get("app", {}).get("root_dir", Path.cwd()))


def _bridge_cfg(cfg: dict) -> dict:
    return cfg.get("integration", {}).get("bridge", {})


def _proposal_root(cfg: dict) -> Path:
    rel = _bridge_cfg(cfg).get("proposal_dir", "data/integration/signal_proposals")
    path = Path(rel)
    return path if path.is_absolute() else _root_dir(cfg) / path


def _market_regime(value: object) -> str:
    mapping = {"risk_on": "positiv", "neutral": "neutral", "risk_off": "defensiv"}
    return mapping.get(str(value or "").strip(), "neutral")


def _infer_currency(rec: dict, price: float | None) -> str | None:
    if price is None:
        return None
    quote = rec.get("quote") or {}
    explicit = str(quote.get("currency") or rec.get("currency") or "").strip().upper()
    if explicit in {"EUR", "USD"}:
        return explicit

    isin = str(rec.get("isin") or "").strip().upper()
    symbol = str(rec.get("symbol") or "").strip().upper()
    if isin.startswith("US"):
        return "USD"
    if isin.startswith(("DE", "IE", "FR", "NL", "ES", "IT", "AT", "BE", "LU")):
        return "EUR"
    if symbol.endswith((".DE", ".PA", ".AS", ".MI", ".MC", ".BR")):
        return "EUR"
    if "." not in symbol and symbol:
        return "USD"
    return None


def _quote_snapshot(rec: dict) -> dict:
    quote = rec.get("quote") or {}
    price_raw = quote.get("price", quote.get("last_price"))
    try:
        price = round(float(price_raw), 4)
    except (TypeError, ValueError):
        price = None
    return {
        "last_price": price,
        "currency": _infer_currency(rec, price),
        "percent_change": quote.get("percent_change"),
        "timestamp": quote.get("timestamp"),
    }


def _budget_context(signal_strength: str, cfg: dict) -> dict:
    budget = float(_bridge_cfg(cfg).get("default_budget_eur", 5000) or 5000)
    ratios = {
        "hoch": (0.5, 1.0),
        "mittel": (0.3, 0.7),
        "spekulativ": (0.15, 0.4),
    }
    min_ratio, max_ratio = ratios.get(signal_strength, ratios["spekulativ"])
    return {
        "budget_eur": round(budget, 2),
        "suggested_size_min_eur": round(budget * min_ratio, 2),
        "suggested_size_max_eur": round(budget * max_ratio, 2),
    }


def _proposal_id(candidate: dict, cfg: dict) -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    seq = int(candidate.get("_proposal_seq", 0) or 0)
    if seq > 0:
        return f"PWV2-{stamp}-{seq:03d}"

    day_dir = _proposal_root(cfg) / datetime.now().strftime("%Y%m%d")
    existing = sorted(day_dir.glob(f"proposal_PWV2-{stamp}-*.json"))
    return f"PWV2-{stamp}-{len(existing) + 1:03d}"


def build_signal_proposal(candidate: dict, cfg: dict) -> dict:
    rec = candidate or {}
    reasons = human_reasons((rec.get("opportunity_score") or {}).get("reasons", []) or rec.get("reasons", []))
    signal_strength = normalize_confidence((rec.get("opportunity_score") or {}).get("confidence") or rec.get("signal_strength"))
    proposal_id = _proposal_id(rec, cfg)
    score = float((rec.get("opportunity_score") or {}).get("total_score", rec.get("score", 0)) or 0)

    return {
        "proposal_id": proposal_id,
        "source": "portwaechter_v2",
        "asset": {
            "symbol": rec.get("symbol"),
            "isin": rec.get("isin"),
            "name": rec.get("name"),
        },
        "classification": "KAUFIDEE_PRUEFEN",
        "direction": "short" if str(rec.get("direction") or "").strip().lower() == "short" else "long",
        "score": round(score, 2),
        "signal_strength": signal_strength,
        "market_regime": _market_regime(rec.get("regime")),
        "reasons": reasons[:3],
        "quote": _quote_snapshot(rec),
        "portfolio_context": {
            "is_holding": rec.get("group") == "holding",
            "weight_pct": round(float(rec.get("weight_pct", 0) or 0), 2),
        },
        "budget_context": _budget_context(signal_strength, cfg),
        "timestamp": datetime.now().isoformat(),
    }


def write_signal_proposal(proposal: dict, cfg: dict) -> str:
    proposal_id = str(proposal.get("proposal_id") or "PWV2-UNKNOWN-001")
    day = proposal_id.split("-", 2)[1] if "-" in proposal_id else datetime.now().strftime("%Y%m%d")
    day_dir = _proposal_root(cfg) / day
    ensure_dir(day_dir)

    path = day_dir / f"proposal_{proposal_id}.json"
    if path.exists():
        seq = int(proposal_id.rsplit("-", 1)[-1])
        prefix = proposal_id.rsplit("-", 1)[0]
        while path.exists():
            seq += 1
            proposal_id = f"{prefix}-{seq:03d}"
            proposal["proposal_id"] = proposal_id
            path = day_dir / f"proposal_{proposal_id}.json"

    write_json(path, proposal)
    return str(path)


def export_action_candidates_to_bridge(recommendations: list, cfg: dict) -> list[str]:
    written: list[str] = []
    action_rows = [
        row
        for row in recommendations or []
        if str((row or {}).get("classification") or "").strip().upper() in {"ACTION", "KAUFIDEE_PRUEFEN"}
    ]
    for idx, row in enumerate(action_rows, start=1):
        proposal = build_signal_proposal({**row, "_proposal_seq": idx}, cfg)
        written.append(write_signal_proposal(proposal, cfg))
    return written
