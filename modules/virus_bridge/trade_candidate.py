from __future__ import annotations

from datetime import datetime
from pathlib import Path

from modules.common.operator_signals import validate_buy_signal
from modules.common.utils import ensure_dir, read_json, write_json


def _root_dir(cfg: dict) -> Path:
    return Path(cfg.get("app", {}).get("root_dir", Path.cwd()))


def _candidate_root(cfg: dict) -> Path:
    return _root_dir(cfg) / "data" / "virus_bridge" / "trade_candidates"


def _ticket_id(signal_proposal: dict, cfg: dict) -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    seq = int(signal_proposal.get("_ticket_seq", 0) or 0)
    if seq > 0:
        return f"VF-{stamp}-{seq:03d}"

    day_dir = _candidate_root(cfg) / datetime.now().strftime("%Y%m%d")
    existing = sorted(day_dir.glob(f"ticket_VF-{stamp}-*.json"))
    return f"VF-{stamp}-{len(existing) + 1:03d}"


def _next_step(decision: str) -> str:
    if decision == "APPROVED":
        return "Nur handeln, wenn Einstieg, Stop-Loss und Risiko fuer dich sauber passen."
    if decision == "REDUCED":
        return "Nur handeln, wenn Einstieg, Stop-Loss und Risiko fuer dich sauber passen."
    if decision == "PENDING_MARKET_OPEN":
        return "Kauf erst pruefen, wenn der Markt wieder offen ist."
    return "Nicht weiter verfolgen"


def _merged_reasons(signal_proposal: dict, risk_eval: dict, decision: str) -> list[str]:
    reasons: list[str] = []
    if decision == "APPROVED":
        source = (signal_proposal.get("reasons") or []) + (risk_eval.get("reasons") or [])
    else:
        source = (risk_eval.get("reasons") or []) + (signal_proposal.get("reasons") or [])
    for value in source:
        item = str(value or "").strip()
        if item and item not in reasons:
            reasons.append(item)
    return reasons


def _last_price(signal_proposal: dict) -> float | None:
    quote = signal_proposal.get("quote") or {}
    for key in ("last_price", "price"):
        try:
            return round(float(quote.get(key)), 4)
        except (TypeError, ValueError):
            continue
    return None


def _currency(signal_proposal: dict) -> str | None:
    quote = signal_proposal.get("quote") or {}
    value = str(quote.get("currency") or "").strip().upper()
    return value or None


def _market_status(risk_eval: dict, decision: str) -> dict:
    status = risk_eval.get("market_status")
    if isinstance(status, dict) and status:
        return dict(status)
    return {
        "is_open": decision in {"APPROVED", "REDUCED"},
        "market": None,
        "next_open_hint": "Marktzeit manuell pruefen",
    }


def build_trade_candidate(signal_proposal: dict, risk_eval: dict, cfg: dict) -> dict:
    decision = str(risk_eval.get("decision") or "REJECTED")
    stop_loss_hint = str(risk_eval.get("stop_loss_hint") or signal_proposal.get("stop_loss_hint") or signal_proposal.get("stop_hint") or "Stop-Loss manuell pruefen")
    ticket_id = _ticket_id(signal_proposal, cfg)
    candidate = {
        "ticket_id": ticket_id,
        "source_proposal_id": signal_proposal.get("proposal_id"),
        "asset": dict(signal_proposal.get("asset") or {}),
        "direction": signal_proposal.get("direction"),
        "last_price": _last_price(signal_proposal),
        "currency": _currency(signal_proposal),
        "decision": decision,
        "signal_strength": signal_proposal.get("signal_strength"),
        "market_regime": signal_proposal.get("market_regime"),
        "score": signal_proposal.get("score"),
        "reasons": _merged_reasons(signal_proposal, risk_eval, decision),
        "risk_flags": list(risk_eval.get("risk_flags") or []),
        "tr_verified": bool(risk_eval.get("tr_verified", True)),
        "market_status": _market_status(risk_eval, decision),
        "size_min_eur": float(risk_eval.get("size_min_eur", 0) or 0),
        "size_max_eur": float(risk_eval.get("size_max_eur", 0) or 0),
        "suggested_eur": float(risk_eval.get("suggested_eur", 0) or 0),
        "entry_hint": str(signal_proposal.get("entry_hint") or "Nur bei bestaetigter Staerke beobachten"),
        "stop_loss_hint": stop_loss_hint,
        "stop_hint": stop_loss_hint,
        "stop_method": risk_eval.get("stop_method") or signal_proposal.get("stop_method"),
        "stop_loss_price": risk_eval.get("stop_loss_price"),
        "stop_distance_pct": risk_eval.get("stop_distance_pct"),
        "risk_eur": risk_eval.get("risk_eur"),
        "quote_age_minutes": risk_eval.get("quote_age_minutes"),
        "data_fresh": bool(risk_eval.get("data_fresh", False)),
        "next_step": _next_step(decision),
        "timestamp": datetime.now().isoformat(),
    }
    validation = validate_buy_signal(candidate)
    candidate["operational_status"] = validation["status"]
    candidate["operational_is_actionable"] = validation["is_operational"]
    candidate["operational_missing_fields"] = validation["missing_fields"]
    candidate["operational_missing_labels"] = validation["missing_labels"]
    if not validation["is_operational"]:
        candidate["next_step"] = "Operative Pflichtfelder zuerst vervollstaendigen. Noch kein handlungsfaehiges Ticket."
    return candidate


def write_trade_candidate(trade_candidate: dict, cfg: dict) -> str:
    ticket_id = str(trade_candidate.get("ticket_id") or "VF-UNKNOWN-001")
    day = ticket_id.split("-", 2)[1] if "-" in ticket_id else datetime.now().strftime("%Y%m%d")
    day_dir = _candidate_root(cfg) / day
    ensure_dir(day_dir)

    path = day_dir / f"ticket_{ticket_id}.json"
    if path.exists():
        seq = int(ticket_id.rsplit("-", 1)[-1])
        prefix = ticket_id.rsplit("-", 1)[0]
        while path.exists():
            seq += 1
            ticket_id = f"{prefix}-{seq:03d}"
            trade_candidate["ticket_id"] = ticket_id
            path = day_dir / f"ticket_{ticket_id}.json"

    write_json(path, trade_candidate)
    return str(path)


def load_recent_trade_candidates(cfg: dict, limit: int = 5) -> list[dict]:
    root = _candidate_root(cfg)
    if not root.exists():
        return []

    items: list[dict] = []
    for path in sorted(root.rglob("ticket_*.json")):
        try:
            payload = read_json(path)
        except Exception:
            continue
        if isinstance(payload, dict):
            items.append(payload)
    items.sort(key=lambda row: str(row.get("timestamp") or ""), reverse=True)
    return items[:limit]


def load_trade_candidate(ticket_id: str, cfg: dict) -> dict | None:
    needle = str(ticket_id or "").strip()
    if not needle:
        return None

    root = _candidate_root(cfg)
    if not root.exists():
        return None

    direct = list(root.rglob(f"ticket_{needle}.json"))
    for path in direct:
        try:
            payload = read_json(path)
        except Exception:
            continue
        if isinstance(payload, dict):
            return payload
    return None
