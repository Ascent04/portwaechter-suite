from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from modules.common.utils import read_json
from modules.virus_bridge.data_quality import compute_quote_age_minutes, is_quote_fresh
from modules.virus_bridge.exit_flow import EXIT_REASON_LABELS, load_exit_records as _load_exit_records
from modules.virus_bridge.lifecycle import load_lifecycle
from modules.virus_bridge.trade_candidate import load_trade_candidate


LIFECYCLE_REASON_MAP = {
    "TRADE_CLOSED_STOP_LOSS": "STOP_LOSS",
    "TRADE_CLOSED_TARGET_REACHED": "TARGET_REACHED",
    "TRADE_CLOSED_MANUAL": "MANUAL_EXIT",
}


def _root_dir(cfg: dict) -> Path:
    return Path(cfg.get("app", {}).get("root_dir", Path.cwd()))


def _safe_float(value: object) -> float | None:
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


def _direction_multiplier(direction: object) -> float:
    return -1.0 if str(direction or "long").strip().lower() == "short" else 1.0


def _text(value: object) -> str:
    return str(value or "").strip()


def _quantity(size_eur: object, price: object) -> float | None:
    notional = _safe_float(size_eur)
    entry = _safe_float(price)
    if notional in {None, 0} or entry in {None, 0}:
        return None
    return round(notional / entry, 6)


def _reason_label(reason: object) -> str:
    code = _text(reason).upper()
    if not code:
        return ""
    return EXIT_REASON_LABELS.get(code, code.replace("_", " ").title())


def _exit_type(row: dict) -> str:
    return _text(row.get("exit_type")).upper() or "PARTIAL"


def _exit_size_eur(row: dict, remaining_before: float, entry_size_eur: float) -> float | None:
    size_eur = _safe_float(row.get("size_eur"))
    if size_eur is None and _exit_type(row) == "FULL":
        if remaining_before > 0:
            size_eur = remaining_before
        elif entry_size_eur > 0:
            size_eur = entry_size_eur
    if size_eur is None:
        return None
    if remaining_before > 0:
        return round(min(size_eur, remaining_before), 4)
    return round(size_eur, 4)


def _row_realized_pnl(row: dict, entry_price: float | None, direction: object, size_eur: float | None) -> float | None:
    explicit = _safe_float(row.get("realized_pnl_eur"))
    if explicit is not None:
        return round(explicit, 2)
    exit_price = _safe_float(row.get("exit_price"))
    if entry_price in (None, 0) or exit_price is None or size_eur in (None, 0):
        return None
    pnl_pct = ((exit_price - entry_price) / entry_price) * 100.0 * _direction_multiplier(direction)
    return round(size_eur * pnl_pct / 100.0, 2)


def _lifecycle_reason(ticket: dict) -> str | None:
    explicit = _text(ticket.get("lifecycle_closed_exit_reason")).upper()
    if explicit:
        return explicit
    event_type = _text(ticket.get("lifecycle_closed_event_type")).upper()
    return LIFECYCLE_REASON_MAP.get(event_type)


def _resolve_exit_reason(ticket: dict, relevant: list[dict], status: str) -> dict:
    explicit_reasons = [_text(row.get("exit_reason")).upper() for row in relevant if _text(row.get("exit_reason"))]
    if explicit_reasons:
        latest = explicit_reasons[-1]
        return {
            "exit_reason": _reason_label(latest),
            "exit_reason_code": latest,
            "exit_reason_quality": "HOCH" if len(set(explicit_reasons)) == 1 else "MITTEL",
            "exit_reason_source": "EXIT_RECORD",
        }

    lifecycle_reason = _lifecycle_reason(ticket)
    if lifecycle_reason:
        return {
            "exit_reason": _reason_label(lifecycle_reason),
            "exit_reason_code": lifecycle_reason,
            "exit_reason_quality": "MITTEL",
            "exit_reason_source": "LIFECYCLE",
        }

    lifecycle_status = _text(ticket.get("lifecycle_status")).upper()
    if status == "CLOSED" or lifecycle_status == "CLOSED":
        return {
            "exit_reason": "Status-Fallback: CLOSED",
            "exit_reason_code": None,
            "exit_reason_quality": "NIEDRIG",
            "exit_reason_source": "STATUS",
        }

    return {
        "exit_reason": None,
        "exit_reason_code": None,
        "exit_reason_quality": None,
        "exit_reason_source": None,
    }


def _ticket_state(cfg: dict) -> dict[str, dict]:
    path = _root_dir(cfg) / "data" / "virus_bridge" / "ticket_state.json"
    if not path.exists():
        return {}
    try:
        data = read_json(path)
    except Exception:
        return {}
    tickets = data.get("tickets", {}) if isinstance(data, dict) else {}
    return tickets if isinstance(tickets, dict) else {}


def _execution_rows(cfg: dict) -> dict[str, dict]:
    root = _root_dir(cfg) / "data" / "virus_bridge" / "executions"
    rows: dict[str, dict] = {}
    if not root.exists():
        return rows
    for path in sorted(root.rglob("execution_*.json")):
        try:
            payload = read_json(path)
        except Exception:
            continue
        if not isinstance(payload, dict) or str(payload.get("status") or "").upper() != "EXECUTED":
            continue
        ticket_id = str(payload.get("ticket_id") or "").strip()
        if ticket_id:
            rows[ticket_id] = payload
    return rows


def _lifecycle_rows(cfg: dict) -> dict[str, dict]:
    root = _root_dir(cfg) / "data" / "virus_bridge" / "ticket_lifecycle"
    rows: dict[str, dict] = {}
    if not root.exists():
        return rows
    for path in sorted(root.glob("*.json")):
        lifecycle = load_lifecycle(path.stem, cfg)
        if lifecycle:
            rows[path.stem] = lifecycle
    return rows


def _executed_event(lifecycle: dict) -> dict:
    if isinstance(lifecycle.get("executed"), dict) and lifecycle.get("executed"):
        return dict(lifecycle["executed"])
    for event in lifecycle.get("events", []):
        if str(event.get("event_type") or "").upper() == "TRADE_EXECUTED_MANUAL":
            data = dict(event.get("data") or {})
            data.setdefault("timestamp", event.get("timestamp"))
            return data
    return {}


def _candidate_quote(ticket_id: str, cfg: dict) -> dict | None:
    trade_candidate = load_trade_candidate(ticket_id, cfg) or {}
    price = _safe_float(trade_candidate.get("last_price"))
    if price is None:
        return None
    return {
        "price": price,
        "currency": str(trade_candidate.get("currency") or "").strip().upper() or None,
        "timestamp": trade_candidate.get("timestamp"),
    }


def _latest_quote_map(cfg: dict) -> dict[str, dict]:
    root = _root_dir(cfg) / str(cfg.get("v2", {}).get("data_dir", "data/v2"))
    files = sorted(root.glob("candidates_*.json"))
    if not files:
        return {}
    try:
        payload = read_json(files[-1])
    except Exception:
        return {}
    rows = payload.get("candidates", []) if isinstance(payload, dict) else payload
    out: dict[str, dict] = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        quote = row.get("quote") or {}
        price = _safe_float(quote.get("price") or quote.get("last_price"))
        if price is None:
            continue
        snapshot = {
            "price": price,
            "currency": str(quote.get("currency") or row.get("currency") or "").strip().upper() or None,
            "timestamp": quote.get("timestamp") or row.get("timestamp"),
        }
        for key in (row.get("symbol"), row.get("isin")):
            needle = str(key or "").strip().upper()
            if needle:
                out[needle] = snapshot
    return out


def _quote_for_ticket(ticket: dict, quote_map: dict[str, dict], cfg: dict) -> dict | None:
    asset = ticket.get("asset") or {}
    for key in (asset.get("symbol"), asset.get("isin")):
        needle = str(key or "").strip().upper()
        if needle and needle in quote_map:
            return dict(quote_map[needle])
    return _candidate_quote(str(ticket.get("ticket_id") or ""), cfg)


def load_executed_tickets(cfg) -> list[dict]:
    state = _ticket_state(cfg)
    executions = _execution_rows(cfg)
    lifecycles = _lifecycle_rows(cfg)
    ticket_ids = sorted(set(executions) | {ticket_id for ticket_id, lifecycle in lifecycles.items() if _executed_event(lifecycle)})
    rows: list[dict] = []
    for ticket_id in ticket_ids:
        lifecycle = lifecycles.get(ticket_id, {})
        executed = _executed_event(lifecycle)
        execution = executions.get(ticket_id, {})
        trade_candidate = load_trade_candidate(ticket_id, cfg) or {}
        state_row = state.get(ticket_id, {}) if isinstance(state.get(ticket_id), dict) else {}
        entry_price = _safe_float(execution.get("buy_price") or executed.get("buy_price") or state_row.get("entry_price"))
        entry_size_eur = _safe_float(execution.get("size_eur") or executed.get("size_eur") or state_row.get("entry_size_eur"))
        if entry_price is None or entry_size_eur is None:
            continue
        asset = dict(trade_candidate.get("asset") or lifecycle.get("asset") or {"name": state_row.get("asset_name") or ticket_id})
        rows.append(
            {
                "ticket_id": ticket_id,
                "source_proposal_id": trade_candidate.get("source_proposal_id") or lifecycle.get("source_proposal_id"),
                "asset": asset,
                "direction": trade_candidate.get("direction") or "long",
                "entry_price": entry_price,
                "entry_size_eur": entry_size_eur,
                "remaining_size_eur": _safe_float(state_row.get("remaining_size_eur")) or entry_size_eur,
                "status": str(state_row.get("status") or lifecycle.get("current_status") or "EXECUTED").upper(),
                "lifecycle_status": str(lifecycle.get("current_status") or "").upper() or None,
                "entry_timestamp": execution.get("executed_at") or executed.get("timestamp"),
                "latest_exit_price": _safe_float(((lifecycle.get("closed") or {}).get("exit_price")) if isinstance(lifecycle, dict) else None),
                "latest_exit_timestamp": ((lifecycle.get("closed") or {}).get("timestamp") if isinstance(lifecycle, dict) else None),
                "lifecycle_closed_event_type": _text(((lifecycle.get("closed") or {}).get("event_type")) if isinstance(lifecycle, dict) else "").upper() or None,
                "lifecycle_closed_exit_reason": _text(((lifecycle.get("closed") or {}).get("exit_reason")) if isinstance(lifecycle, dict) else "").upper() or None,
                "lifecycle_closed_timestamp": ((lifecycle.get("closed") or {}).get("timestamp") if isinstance(lifecycle, dict) else None),
            }
        )
    rows.sort(key=lambda row: str(row.get("entry_timestamp") or ""), reverse=True)
    return rows


def load_exit_records(cfg) -> list[dict]:
    rows = _load_exit_records(cfg)
    rows.sort(key=lambda row: (str(row.get("timestamp") or ""), str(row.get("ticket_id") or "")))
    return rows


def build_position_state(ticket: dict, exits: list[dict], cfg: dict) -> dict:
    del cfg
    entry_size = _safe_float(ticket.get("entry_size_eur")) or 0.0
    entry_price = _safe_float(ticket.get("entry_price"))
    relevant = [dict(row) for row in exits if str(row.get("ticket_id") or "") == str(ticket.get("ticket_id") or "")]
    remaining = entry_size
    exited_size_total = 0.0
    realized_eur_total = 0.0
    realized_complete = True
    weighted_exit_value = 0.0
    weighted_exit_size_total = 0.0
    latest_exit_timestamp = ticket.get("latest_exit_timestamp")
    latest_exit_price = _safe_float(ticket.get("latest_exit_price"))
    partial_exit_count = 0
    has_partial_exits = False
    saw_full_exit = False
    for row in relevant:
        exit_kind = _exit_type(row)
        exit_size = _exit_size_eur(row, remaining, entry_size)
        exit_price = _safe_float(row.get("exit_price"))
        if exit_kind == "PARTIAL":
            partial_exit_count += 1
            has_partial_exits = True
        if exit_kind == "FULL":
            saw_full_exit = True
        if exit_size is not None:
            exited_size_total += exit_size
            remaining = max(0.0, remaining - exit_size)
            if exit_price is not None:
                weighted_exit_value += exit_price * exit_size
                weighted_exit_size_total += exit_size
        if exit_price is not None:
            latest_exit_price = exit_price
        pnl_eur = _row_realized_pnl(row, entry_price, ticket.get("direction"), exit_size)
        if exit_size not in (None, 0) and pnl_eur is None:
            realized_complete = False
        elif pnl_eur is not None:
            realized_eur_total += pnl_eur
        latest_exit_timestamp = str(row.get("timestamp") or latest_exit_timestamp or "")

    lifecycle_status = _text(ticket.get("lifecycle_status") or ticket.get("status")).upper()
    status = "OPEN"
    if relevant and remaining > 0 and exited_size_total > 0:
        status = "PARTIALLY_CLOSED"
    if relevant and remaining <= 0:
        status = "CLOSED"
        remaining = 0.0
    if relevant and status != "CLOSED" and lifecycle_status == "CLOSED":
        status = "CLOSED"
        if entry_size > exited_size_total:
            realized_complete = False
            exited_size_total = entry_size
        remaining = 0.0
    if relevant and status != "CLOSED" and saw_full_exit and entry_size > 0:
        status = "CLOSED"
        if entry_size > exited_size_total:
            realized_complete = False
            exited_size_total = entry_size
        remaining = 0.0
    if not relevant and lifecycle_status == "PARTIALLY_CLOSED":
        status = "PARTIALLY_CLOSED"
        remaining = _safe_float(ticket.get("remaining_size_eur")) or remaining
    if not relevant and lifecycle_status == "CLOSED":
        status = "CLOSED"
        remaining = 0.0
        exit_price = _safe_float(ticket.get("latest_exit_price"))
        if entry_price not in (None, 0) and exit_price is not None:
            exited_size_total = entry_size
            weighted_exit_value = exit_price * entry_size
            weighted_exit_size_total = entry_size
            realized_eur = _row_realized_pnl({"realized_pnl_eur": None, "exit_price": exit_price}, entry_price, ticket.get("direction"), entry_size)
            if realized_eur is not None:
                realized_eur_total = realized_eur
            else:
                realized_complete = False

    remaining = round(max(0.0, remaining), 2)
    if status == "OPEN":
        exited_size_total = round(exited_size_total, 2)
    elif status == "PARTIALLY_CLOSED":
        exited_size_total = round(min(entry_size, exited_size_total), 2)
    else:
        exited_size_total = round(entry_size if entry_size > 0 else exited_size_total, 2)

    average_exit_price_weighted = None
    if weighted_exit_size_total > 0 and round(weighted_exit_size_total, 2) >= round(min(exited_size_total, weighted_exit_size_total), 2):
        average_exit_price_weighted = round(weighted_exit_value / weighted_exit_size_total, 4)

    exited_quantity_total = _quantity(exited_size_total, entry_price) if exited_size_total > 0 else (0.0 if entry_price not in (None, 0) else None)
    entry_quantity = _quantity(entry_size, entry_price)
    remaining_quantity = _quantity(remaining, entry_price) if remaining > 0 else (0.0 if entry_price not in (None, 0) else None)

    realized_eur = round(realized_eur_total, 2) if (exited_size_total == 0 or realized_complete) else None
    realized_pct = round((realized_eur / exited_size_total) * 100.0, 4) if realized_eur is not None and exited_size_total > 0 else (0.0 if exited_size_total == 0 else None)
    closed_at = latest_exit_timestamp if status == "CLOSED" else None
    if status == "CLOSED" and not closed_at:
        closed_at = ticket.get("lifecycle_closed_timestamp") or ticket.get("latest_exit_timestamp")
    reason = _resolve_exit_reason(ticket, relevant, status)
    weighted_exit_method = bool(status == "CLOSED" and average_exit_price_weighted is not None and weighted_exit_size_total >= exited_size_total > 0)
    return {
        **ticket,
        "remaining_size_eur": remaining,
        "entry_quantity": entry_quantity,
        "exited_size_eur_total": exited_size_total,
        "exited_quantity_total": exited_quantity_total,
        "remaining_quantity": remaining_quantity,
        "average_entry_price": entry_price,
        "average_exit_price_weighted": average_exit_price_weighted,
        "weighted_exit_method": weighted_exit_method,
        "realized_pnl_eur": realized_eur,
        "realized_pnl_pct": realized_pct,
        "pnl_eur": realized_eur,
        "pnl_pct": realized_pct,
        "status": status,
        "lifecycle_status": lifecycle_status or None,
        "has_partial_exits": has_partial_exits,
        "partial_exit_count": partial_exit_count,
        "latest_exit_price": latest_exit_price,
        "latest_exit_timestamp": latest_exit_timestamp or ticket.get("latest_exit_timestamp"),
        "closed_at": closed_at,
        "exit_reason": reason["exit_reason"],
        "exit_reason_code": reason["exit_reason_code"],
        "exit_reason_quality": reason["exit_reason_quality"],
        "exit_reason_source": reason["exit_reason_source"],
        "current_price": None,
        "price_status": "unavailable",
        "unrealized_pnl_eur": None,
        "unrealized_pnl_pct": None,
    }


def attach_mark_to_market(position: dict, current_quote: dict | None, cfg: dict) -> dict:
    updated = dict(position)
    remaining = _safe_float(updated.get("remaining_size_eur")) or 0.0
    price = _safe_float((current_quote or {}).get("price") or (current_quote or {}).get("current_price") or (current_quote or {}).get("last_price"))
    closed_price = _safe_float(updated.get("latest_exit_price"))
    if price is None:
        if remaining <= 0 and closed_price is not None:
            updated["current_price"] = closed_price
            updated["price_status"] = "stale"
            updated["pnl_eur"] = updated.get("realized_pnl_eur")
            updated["pnl_pct"] = updated.get("realized_pnl_pct")
            return updated
        updated["price_status"] = "unavailable"
        return updated
    timestamp = (current_quote or {}).get("timestamp")
    quote = {"price": price, "timestamp": timestamp}
    age = compute_quote_age_minutes(quote, None, cfg)
    updated["current_price"] = price
    updated["currency"] = str((current_quote or {}).get("currency") or updated.get("currency") or "").strip().upper() or None
    updated["price_status"] = "fresh" if is_quote_fresh(quote, None, cfg) else ("stale" if age is not None or timestamp else "unavailable")
    if remaining <= 0:
        if closed_price is not None:
            updated["current_price"] = closed_price
            updated["price_status"] = "stale"
        updated["pnl_eur"] = updated.get("realized_pnl_eur")
        updated["pnl_pct"] = updated.get("realized_pnl_pct")
        return updated
    entry_price = _safe_float(updated.get("entry_price"))
    if entry_price in (None, 0):
        return updated
    pnl_pct = ((price - entry_price) / entry_price) * 100.0 * _direction_multiplier(updated.get("direction"))
    updated["unrealized_pnl_pct"] = round(pnl_pct, 4)
    updated["unrealized_pnl_eur"] = round(remaining * pnl_pct / 100.0, 2)
    updated["pnl_pct"] = updated["unrealized_pnl_pct"]
    updated["pnl_eur"] = updated["unrealized_pnl_eur"]
    return updated


def compute_execution_summary(positions: list[dict], cfg: dict) -> dict:
    del cfg
    active = [row for row in positions if row.get("status") in {"OPEN", "PARTIALLY_CLOSED"}]
    closed = [row for row in positions if row.get("status") == "CLOSED"]
    closed_with_pct = [row for row in closed if row.get("realized_pnl_pct") is not None]
    wins = [row for row in closed_with_pct if float(row.get("realized_pnl_pct") or 0) > 0]
    losses = [row for row in closed_with_pct if float(row.get("realized_pnl_pct") or 0) < 0]
    priced_active = [row for row in active if row.get("unrealized_pnl_eur") is not None]
    priced_active_total = round(sum(float(row.get("unrealized_pnl_eur") or 0) for row in priced_active), 2)
    avg_open = round(sum(float(row.get("unrealized_pnl_pct") or 0) for row in active if row.get("unrealized_pnl_pct") is not None) / len([row for row in active if row.get("unrealized_pnl_pct") is not None]), 4) if any(row.get("unrealized_pnl_pct") is not None for row in active) else 0.0
    avg_closed = round(sum(float(row.get("realized_pnl_pct") or 0) for row in closed_with_pct) / len(closed_with_pct), 4) if closed_with_pct else 0.0
    best = max(closed_with_pct, key=lambda row: float(row.get("realized_pnl_pct") or 0), default=None)
    worst = min(closed_with_pct, key=lambda row: float(row.get("realized_pnl_pct") or 0), default=None)
    realized_rows = []
    for row in positions:
        exited_size = _safe_float(row.get("exited_size_eur_total"))
        if exited_size is not None and exited_size > 0:
            realized_rows.append(row)
            continue
        if row.get("status") in {"PARTIALLY_CLOSED", "CLOSED"} and row.get("realized_pnl_eur") is not None:
            realized_rows.append(row)
    realized_complete = all(row.get("realized_pnl_eur") is not None for row in realized_rows)
    realized_total = round(sum(float(row.get("realized_pnl_eur") or 0) for row in realized_rows), 2) if realized_complete else None
    total_pnl = round(realized_total + priced_active_total, 2) if realized_total is not None and len(priced_active) == len(active) else None
    partial_exit_count = sum(int(row.get("partial_exit_count") or (1 if row.get("status") == "PARTIALLY_CLOSED" else 0)) for row in positions)
    return {
        "executed_total": len(positions),
        "open_total": len([row for row in positions if row.get("status") == "OPEN"]),
        "open_positions_count": len(active),
        "partially_closed_total": len([row for row in positions if row.get("status") == "PARTIALLY_CLOSED"]),
        "partial_exit_count": partial_exit_count,
        "closed_total": len(closed),
        "closed_positions_count": len(closed),
        "realized_pnl_eur_total": realized_total,
        "unrealized_pnl_eur_total": priced_active_total if priced_active else (0.0 if not active else None),
        "total_pnl_eur": total_pnl,
        "avg_open_pnl_pct": avg_open,
        "avg_closed_pnl_pct": avg_closed,
        "win_rate_closed": round((len(wins) / len(closed_with_pct)) * 100.0, 2) if closed_with_pct else None,
        "average_win_eur": round(sum(float(row.get("realized_pnl_eur") or 0) for row in wins) / len(wins), 2) if wins else None,
        "average_loss_eur": round(sum(float(row.get("realized_pnl_eur") or 0) for row in losses) / len(losses), 2) if losses else None,
        "priced_open_total": len(priced_active),
        "unpriced_open_total": len(active) - len(priced_active),
        "realized_pnl_complete": realized_complete,
        "weighted_exit_method": all(bool(row.get("weighted_exit_method", True)) for row in closed) if closed else None,
        "best_closed_trade": best,
        "worst_closed_trade": worst,
    }


def filter_positions_by_days(positions, days: int) -> list[dict]:
    cutoff = datetime.now() - timedelta(days=max(0, int(days or 0)))
    out: list[dict] = []
    for row in positions or []:
        raw = str(row.get("latest_exit_timestamp") or row.get("entry_timestamp") or "").strip()
        try:
            timestamp = datetime.fromisoformat(raw)
        except ValueError:
            continue
        if timestamp >= cutoff:
            out.append(row)
    return out


def get_position_by_ticket(ticket_id: str, cfg: dict) -> dict | None:
    quote_map = _latest_quote_map(cfg)
    exits = load_exit_records(cfg)
    for ticket in load_executed_tickets(cfg):
        if str(ticket.get("ticket_id") or "") != str(ticket_id or ""):
            continue
        position = build_position_state(ticket, exits, cfg)
        return attach_mark_to_market(position, _quote_for_ticket(ticket, quote_map, cfg), cfg)
    return None


def compute_open_trade_mark_to_market(cfg: dict) -> list[dict]:
    return [row for row in (_build_all_positions(cfg)) if row.get("status") in {"OPEN", "PARTIALLY_CLOSED"}]


def compute_closed_trade_returns(cfg: dict) -> list[dict]:
    return [row for row in (_build_all_positions(cfg)) if row.get("status") == "CLOSED"]


def _build_all_positions(cfg: dict) -> list[dict]:
    quote_map = _latest_quote_map(cfg)
    exits = load_exit_records(cfg)
    rows: list[dict] = []
    for ticket in load_executed_tickets(cfg):
        position = build_position_state(ticket, exits, cfg)
        rows.append(attach_mark_to_market(position, _quote_for_ticket(ticket, quote_map, cfg), cfg))
    return rows


def render_ticket_performance(ticket_id: str, cfg: dict) -> str | None:
    position = get_position_by_ticket(ticket_id, cfg)
    if not position:
        return None
    lines = [
        "Performance:",
        f"- Realisiert: {float(position.get('realized_pnl_eur') or 0):.2f} EUR",
    ]
    if position.get("remaining_size_eur"):
        if position.get("unrealized_pnl_eur") is None:
            lines.append("- Aktuelle Bewertung derzeit nicht verfuegbar.")
        else:
            lines.append(f"- Offen: {float(position.get('unrealized_pnl_eur') or 0):.2f} EUR")
        lines.append(f"- Restgroesse: {float(position.get('remaining_size_eur') or 0):.2f} EUR")
    else:
        lines.append("- Offen: 0.00 EUR")
        lines.append("- Restgroesse: 0.00 EUR")
    return "\n".join(lines)


def write_execution_report(cfg: dict) -> dict:
    from modules.virus_bridge.execution_report import build_execution_report, write_execution_report as _write

    report = build_execution_report(cfg)
    return {"path": _write(report, cfg), "report": report}


def render_execution_summary(cfg: dict) -> str:
    from modules.virus_bridge.execution_report import render_execution_summary as _render

    return _render(cfg)
