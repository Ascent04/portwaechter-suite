from __future__ import annotations

from datetime import datetime
from pathlib import Path

from modules.common.runtime_dirs import ensure_runtime_directories
from modules.common.utils import ensure_dir, read_json, write_json
from modules.virus_bridge.lifecycle import record_ticket_lifecycle_event
from modules.virus_bridge.trade_candidate import load_trade_candidate
from modules.v2.telegram.copy import candidate_name


OPEN_POSITION_STATUSES = {"EXECUTED", "PARTIALLY_CLOSED"}
EXIT_REASON_LABELS = {
    "STOP_LOSS": "Stop-Loss",
    "TARGET_REACHED": "Ziel erreicht",
    "MANUAL_EXIT": "Manuell",
    "PARTIAL_TAKE_PROFIT": "Teilgewinn",
    "RISK_REDUCTION": "Risiko reduziert",
}


def _root_dir(cfg: dict) -> Path:
    return Path(cfg.get("app", {}).get("root_dir", Path.cwd()))


def _state_path(cfg: dict) -> Path:
    return _root_dir(cfg) / "data" / "virus_bridge" / "ticket_state.json"


def _exit_root(cfg: dict) -> Path:
    return _root_dir(cfg) / "data" / "virus_bridge" / "exits"


def _safe_float(value: object) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return round(parsed, 4)


def _now() -> str:
    return datetime.now().isoformat()


def _load_ticket_state(cfg: dict) -> dict:
    ensure_runtime_directories(cfg)
    path = _state_path(cfg)
    if not path.exists():
        return {"tickets": {}, "active_by_chat": {}}
    try:
        data = read_json(path)
    except Exception:
        return {"tickets": {}, "active_by_chat": {}}
    if not isinstance(data, dict):
        return {"tickets": {}, "active_by_chat": {}}
    data.setdefault("tickets", {})
    data.setdefault("active_by_chat", {})
    return data


def _save_ticket_state(cfg: dict, state: dict) -> None:
    path = _state_path(cfg)
    ensure_dir(path.parent)
    write_json(path, state)


def _entry_row(ticket_id: str, cfg: dict) -> tuple[dict, dict]:
    state = _load_ticket_state(cfg)
    tickets = state.setdefault("tickets", {})
    row = tickets.setdefault(ticket_id, {})
    return state, row


def _latest_execution(ticket_id: str, cfg: dict) -> dict | None:
    root = _root_dir(cfg) / "data" / "virus_bridge" / "executions"
    if not root.exists():
        return None
    matches = sorted(root.rglob(f"execution_{ticket_id}.json"))
    for path in reversed(matches):
        try:
            payload = read_json(path)
        except Exception:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def load_exit_records(cfg: dict, ticket_id: str | None = None) -> list[dict]:
    root = _exit_root(cfg)
    if not root.exists():
        return []
    rows: list[dict] = []
    pattern = f"exit_{ticket_id}_*.json" if ticket_id else "exit_*.json"
    for path in sorted(root.rglob(pattern)):
        try:
            payload = read_json(path)
        except Exception:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    rows.sort(key=lambda row: str(row.get("timestamp") or ""), reverse=True)
    return rows


def latest_exit_record(ticket_id: str, cfg: dict) -> dict | None:
    rows = load_exit_records(cfg, ticket_id=ticket_id)
    return rows[0] if rows else None


def compute_realized_pnl(entry_price, exit_price, size_eur, direction="long") -> dict:
    entry = _safe_float(entry_price)
    exit_value = _safe_float(exit_price)
    size = _safe_float(size_eur)
    if entry in (None, 0) or exit_value is None or size is None:
        return {"realized_pnl_eur": None, "realized_pnl_pct": None}
    multiplier = -1.0 if str(direction or "long").strip().lower() == "short" else 1.0
    pnl_pct = ((exit_value - entry) / entry) * 100.0 * multiplier
    pnl_eur = size * pnl_pct / 100.0
    return {"realized_pnl_eur": round(pnl_eur, 2), "realized_pnl_pct": round(pnl_pct, 4)}


def _quantity(size_eur: float | None, entry_price: float | None) -> float | None:
    if size_eur in (None, 0) or entry_price in (None, 0):
        return None
    return round(float(size_eur) / float(entry_price), 6)


def _write_exit_record(ticket_id: str, payload: dict, cfg: dict) -> str:
    stamp = datetime.now().strftime("%Y%m%d")
    day_dir = _exit_root(cfg) / stamp
    ensure_dir(day_dir)
    suffix = datetime.now().strftime("%Y%m%dT%H%M%S_%f")
    path = day_dir / f"exit_{ticket_id}_{suffix}.json"
    collision_idx = 1
    while path.exists():
        path = day_dir / f"exit_{ticket_id}_{suffix}_{collision_idx}.json"
        collision_idx += 1
    write_json(path, payload)
    return str(path)


def _fraction(size_eur: float | None, entry_size_eur: float | None, exit_type: str) -> float:
    if exit_type == "FULL":
        return 1.0
    if size_eur is None or entry_size_eur in (None, 0):
        return 0.0
    return round(max(0.0, min(1.0, size_eur / entry_size_eur)), 4)


def _event_type_for_exit(full: bool, final_status: str, exit_reason: str) -> str:
    reason = str(exit_reason or "MANUAL_EXIT").strip().upper()
    status = str(final_status or "").strip().upper()
    if not full and status == "PARTIALLY_CLOSED":
        return "TRADE_PARTIAL_EXIT"
    if reason == "STOP_LOSS":
        return "TRADE_CLOSED_STOP_LOSS"
    if reason == "TARGET_REACHED":
        return "TRADE_CLOSED_TARGET_REACHED"
    return "TRADE_CLOSED_MANUAL"


def _validate_exit_record(entry_size_eur: float | None, remaining_size_eur: float | None, exit_price: float | None, size_eur: float | None, *, full: bool) -> None:
    if exit_price in (None, 0) or float(exit_price) <= 0:
        raise ValueError("exit_price_invalid")
    if full:
        effective_size = size_eur or remaining_size_eur or entry_size_eur
        if effective_size in (None, 0) or float(effective_size) <= 0:
            raise ValueError("exit_size_missing")
        return
    if size_eur in (None, 0) or float(size_eur) <= 0:
        raise ValueError("partial_exit_size_invalid")
    if remaining_size_eur not in (None, 0) and float(size_eur) > float(remaining_size_eur):
        raise ValueError("partial_exit_size_exceeds_remaining")


def _finalize_exit(ticket_id: str, exit_record: dict, cfg: dict, *, full: bool) -> dict:
    trade_candidate = load_trade_candidate(ticket_id, cfg) or {}
    state, row = _entry_row(ticket_id, cfg)
    execution = _latest_execution(ticket_id, cfg) or {}
    entry_price = _safe_float(row.get("entry_price")) or _safe_float(execution.get("buy_price"))
    entry_size_eur = _safe_float(row.get("entry_size_eur")) or _safe_float(execution.get("size_eur"))
    remaining_size_eur = _safe_float(row.get("remaining_size_eur"))
    if remaining_size_eur is None:
        remaining_size_eur = entry_size_eur

    size_eur = _safe_float(exit_record.get("size_eur"))
    if full:
        size_eur = size_eur or remaining_size_eur or entry_size_eur
    exit_price = _safe_float(exit_record.get("exit_price"))
    _validate_exit_record(entry_size_eur, remaining_size_eur, exit_price, size_eur, full=full)
    direction = trade_candidate.get("direction") or "long"
    pnl = compute_realized_pnl(entry_price, exit_price, size_eur, direction=direction)
    remaining_after = 0.0 if full else remaining_size_eur
    if not full and size_eur is not None and remaining_size_eur is not None:
        remaining_after = round(max(0.0, remaining_size_eur - size_eur), 2)
    record = {
        "ticket_id": ticket_id,
        "exit_type": "FULL" if full else "PARTIAL",
        "exit_reason": str(exit_record.get("exit_reason") or "MANUAL_EXIT").strip().upper(),
        "exit_price": exit_price,
        "size_eur": size_eur,
        "exit_quantity": _quantity(size_eur, entry_price),
        "entry_price": entry_price,
        "entry_size_eur": entry_size_eur,
        "remaining_size_eur_before": remaining_size_eur,
        "remaining_size_eur_after": remaining_after,
        "direction": direction,
        "exit_note": str(exit_record.get("exit_note") or "").strip() or None,
        "closed_fraction": _fraction(size_eur, entry_size_eur, "FULL" if full else "PARTIAL"),
        "realized_pnl_eur": pnl["realized_pnl_eur"],
        "realized_pnl_pct": pnl["realized_pnl_pct"],
        "timestamp": str(exit_record.get("timestamp") or _now()),
    }
    path = _write_exit_record(ticket_id, record, cfg)

    row["entry_price"] = entry_price
    row["entry_size_eur"] = entry_size_eur
    row["last_updated"] = record["timestamp"]
    row["awaiting_input"] = None
    row["pending_action"] = None
    row["pending_exit_reason"] = None
    row["pending_exit_price"] = None
    row["pending_exit_size_eur"] = None
    row["pending_exit_note"] = None
    if full:
        row["remaining_size_eur"] = 0.0
        row["status"] = "CLOSED"
    else:
        if size_eur is not None and remaining_size_eur is not None:
            row["remaining_size_eur"] = remaining_after
        row["status"] = "PARTIALLY_CLOSED" if float(row.get("remaining_size_eur") or 0) > 0 else "CLOSED"
    _save_ticket_state(cfg, state)

    event_type = _event_type_for_exit(full, row["status"], record["exit_reason"])
    record_ticket_lifecycle_event(
        event_type,
        {
            "ticket_id": ticket_id,
            "source_proposal_id": trade_candidate.get("source_proposal_id"),
            "asset": trade_candidate.get("asset"),
            "decision": trade_candidate.get("decision"),
            "status": row["status"],
            "size_eur": record["size_eur"],
            "exit_price": record["exit_price"],
            "exit_reason": record["exit_reason"],
            "exit_note": record["exit_note"],
            "closed_fraction": record["closed_fraction"],
            "realized_pnl_eur": record["realized_pnl_eur"],
            "realized_pnl_pct": record["realized_pnl_pct"],
            "timestamp": record["timestamp"],
        },
        cfg,
    )
    return {"path": path, "record": record, "status": row["status"]}


def load_executed_open_tickets(cfg) -> list[dict]:
    state = _load_ticket_state(cfg)
    rows: list[dict] = []
    for ticket_id, row in (state.get("tickets", {}) or {}).items():
        status = str(row.get("status") or "").upper()
        if status not in OPEN_POSITION_STATUSES:
            continue
        trade_candidate = load_trade_candidate(ticket_id, cfg) or {}
        asset = dict(trade_candidate.get("asset") or {"name": row.get("asset_name") or ticket_id})
        rows.append(
            {
                "ticket_id": ticket_id,
                "asset": asset,
                "status": status,
                "entry_price": _safe_float(row.get("entry_price")),
                "entry_size_eur": _safe_float(row.get("entry_size_eur")),
                "remaining_size_eur": _safe_float(row.get("remaining_size_eur")),
            }
        )
    rows.sort(key=lambda row: str(row.get("ticket_id") or ""), reverse=True)
    return rows


def mark_partial_exit(ticket_id, exit_record, cfg) -> None:
    _finalize_exit(str(ticket_id), dict(exit_record or {}), cfg, full=False)


def mark_full_exit(ticket_id, exit_record, cfg) -> None:
    _finalize_exit(str(ticket_id), dict(exit_record or {}), cfg, full=True)


def render_open_position_text(ticket_id: str, cfg: dict) -> str:
    trade_candidate = load_trade_candidate(ticket_id, cfg) or {}
    state = _load_ticket_state(cfg)
    row = (state.get("tickets", {}) or {}).get(ticket_id, {})
    name = candidate_name((trade_candidate.get("asset") or {}) or {"name": row.get("asset_name") or ticket_id})
    entry_price = row.get("entry_price")
    entry_size_eur = row.get("entry_size_eur")
    remaining_size_eur = row.get("remaining_size_eur")
    return (
        f"OFFENE POSITION: {name}\n\n"
        f"Kaufkurs: {entry_price if entry_price is not None else '-'}\n"
        f"Einsatz: {entry_size_eur if entry_size_eur is not None else '-'} EUR\n"
        f"Restgroesse: {remaining_size_eur if remaining_size_eur is not None else '-'} EUR\n"
        f"Aktueller Status: {row.get('status')}\n\n"
        "Moegliche Aktion:\n"
        "- Teilverkauf\n"
        "- Komplettverkauf\n"
        "- Ziel erreicht\n"
        "- Stop-Loss"
    )[:1800]
