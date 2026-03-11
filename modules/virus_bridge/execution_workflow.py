from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from modules.common.runtime_dirs import ensure_runtime_directories
from modules.common.utils import ensure_dir, read_json, write_json
from modules.telegram_commands.ui import build_ticket_buttons, ticket_action_name
from modules.virus_bridge.execution_performance import render_ticket_performance
from modules.virus_bridge.exit_flow import (
    EXIT_REASON_LABELS,
    OPEN_POSITION_STATUSES,
    compute_realized_pnl,
    latest_exit_record,
    mark_full_exit,
    mark_partial_exit,
    render_open_position_text,
)
from modules.virus_bridge.lifecycle import load_lifecycle, record_ticket_lifecycle_event
from modules.virus_bridge.ticket_render import render_ticket_text
from modules.virus_bridge.trade_candidate import load_recent_trade_candidates, load_trade_candidate
from modules.v2.telegram.copy import candidate_name


VALID_STATUSES = {"OPEN", "EXECUTED", "PARTIALLY_CLOSED", "CLOSED", "REJECTED", "DEFERRED"}
PARTIAL_REASON_MAP = {"1": "PARTIAL_TAKE_PROFIT", "2": "RISK_REDUCTION", "3": "MANUAL_EXIT"}
FULL_REASON_MAP = {"1": "TARGET_REACHED", "2": "STOP_LOSS", "3": "MANUAL_EXIT"}
STATUS_LABELS = {
    "CREATED": "ERSTELLT",
    "SENT": "GESENDET",
    "OPEN": "OFFEN",
    "EXECUTED": "AUSGEFUEHRT",
    "PARTIALLY_CLOSED": "TEILWEISE VERKAUFT",
    "CLOSED": "GESCHLOSSEN",
    "REJECTED": "ABGELEHNT",
    "DEFERRED": "VERSCHOBEN",
}
OPEN_TICKET_STATUSES = {"CREATED", "SENT", "OPEN"}

log = logging.getLogger(__name__)


def _root_dir(cfg: dict) -> Path:
    return Path(cfg.get("app", {}).get("root_dir", Path.cwd()))


def _state_path(cfg: dict) -> Path:
    return _root_dir(cfg) / "data" / "virus_bridge" / "ticket_state.json"


def _execution_dir(cfg: dict) -> Path:
    return _root_dir(cfg) / "data" / "virus_bridge" / "executions" / datetime.now().strftime("%Y%m%d")


def _now() -> str:
    return datetime.now().isoformat()


def _default_entry() -> dict:
    return {
        "status": "OPEN",
        "last_updated": _now(),
        "awaiting_input": None,
        "pending_action": None,
        "asset_name": None,
        "entry_price": None,
        "entry_size_eur": None,
        "remaining_size_eur": None,
        "pending_exit_note": None,
    }


def load_ticket_state(cfg: dict) -> dict:
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
    tickets = data.get("tickets", {})
    active_by_chat = data.get("active_by_chat", {})
    return {
        "tickets": tickets if isinstance(tickets, dict) else {},
        "active_by_chat": active_by_chat if isinstance(active_by_chat, dict) else {},
    }


def save_ticket_state(cfg: dict, state: dict) -> None:
    path = _state_path(cfg)
    ensure_dir(path.parent)
    write_json(path, state)


def _entry(state: dict, ticket_id: str) -> dict:
    tickets = state.setdefault("tickets", {})
    row = tickets.setdefault(ticket_id, _default_entry())
    if str(row.get("status") or "").upper() not in VALID_STATUSES:
        row["status"] = "OPEN"
    row.setdefault("awaiting_input", None)
    row.setdefault("pending_action", None)
    row.setdefault("last_updated", _now())
    row.setdefault("asset_name", None)
    row.setdefault("entry_price", None)
    row.setdefault("entry_size_eur", None)
    row.setdefault("remaining_size_eur", None)
    row.setdefault("pending_exit_note", None)
    return row


def _ticket_keyboard(ticket_id: str) -> list[list[str]]:
    rows = build_ticket_buttons(ticket_id, mode="default")
    rows.append(["🎫 Tickets", "📊 Status"])
    return rows


def _ticket_keyboard_for_candidate(ticket_id: str, trade_candidate: dict) -> list[list[str]]:
    market_status = trade_candidate.get("market_status")
    if isinstance(market_status, dict) and "is_open" in market_status:
        market_open = bool(market_status.get("is_open"))
    else:
        market_open = str(trade_candidate.get("decision") or "").upper() in {"APPROVED", "REDUCED"}
    if market_open:
        return _ticket_keyboard(ticket_id)
    return build_ticket_buttons(ticket_id, mode="closed_market")


def _position_keyboard(ticket_id: str) -> list[list[str]]:
    return build_ticket_buttons(ticket_id, mode="executed_position")


def _resolved_status(ticket_id: str, state_row: dict | None, cfg: dict) -> tuple[str, dict | None]:
    lifecycle = load_lifecycle(ticket_id, cfg)
    lifecycle_status = str((lifecycle or {}).get("current_status") or "").strip().upper()
    state_status = str((state_row or {}).get("status") or "").strip().upper()
    if lifecycle_status in OPEN_TICKET_STATUSES and state_status in {"EXECUTED", "PARTIALLY_CLOSED", "CLOSED", "REJECTED", "DEFERRED"}:
        log.warning(
            "ticket_status_conflict: ticket_id=%s lifecycle=%s state=%s fallback=state",
            ticket_id,
            lifecycle_status,
            state_status,
        )
        return state_status, lifecycle
    if lifecycle_status and state_status and lifecycle_status != state_status and (lifecycle_status, state_status) not in {
        ("SENT", "OPEN"),
        ("OPEN", "SENT"),
        ("CREATED", "OPEN"),
        ("OPEN", "CREATED"),
    }:
        log.warning(
            "ticket_status_conflict: ticket_id=%s lifecycle=%s state=%s",
            ticket_id,
            lifecycle_status,
            state_status,
        )
    return lifecycle_status or state_status or "OPEN", lifecycle


def _status_label(status: str) -> str:
    return STATUS_LABELS.get(str(status or "").upper(), str(status or "-").upper())


def _event_time(lifecycle: dict, event_types: tuple[str, ...]) -> str | None:
    for event in lifecycle.get("events", []):
        if str(event.get("event_type") or "").upper() in event_types:
            return str(event.get("timestamp") or "")
    return None


def _format_lifecycle_detail(ticket_id: str, cfg: dict) -> str:
    lifecycle = load_lifecycle(ticket_id, cfg)
    if not lifecycle:
        return ""
    timeline: list[str] = []
    checkpoints = [
        ("erstellt", ("TRADE_CANDIDATE_CREATED",)),
        ("gesendet", ("TRADE_TICKET_SENT",)),
        ("gekauft", ("TRADE_EXECUTED_MANUAL",)),
        ("teilverkauft", ("TRADE_PARTIAL_EXIT",)),
        ("geschlossen", ("TRADE_CLOSED_MANUAL", "TRADE_CLOSED_STOP_LOSS", "TRADE_CLOSED_TARGET_REACHED")),
        ("abgelehnt", ("TRADE_REJECTED_MANUAL",)),
        ("verschoben", ("TRADE_DEFERRED",)),
    ]
    for label, event_types in checkpoints:
        timestamp = _event_time(lifecycle, event_types)
        if timestamp:
            timeline.append(f"- {label}: {timestamp}")
    lines = [
        f"Ticket: {ticket_id}",
        f"Status: {_status_label(str(lifecycle.get('current_status') or '-'))}",
    ]
    if timeline:
        lines.extend(["", "Verlauf:"] + timeline)
    audit_refs = [row for row in lifecycle.get("audit_refs", []) if isinstance(row, dict) and row.get("ref")]
    if audit_refs:
        lines.append("")
        lines.append(f"Audit-Eintraege: {len(audit_refs)}")
    events = lifecycle.get("events", [])
    if events:
        lines.append(f"Letztes Ereignis: {str(events[-1].get('event_type') or '-').upper()}")
    return "\n".join(lines)


def set_active_ticket(chat_id: str, ticket_id: str, cfg: dict) -> None:
    state = load_ticket_state(cfg)
    active_by_chat = state.setdefault("active_by_chat", {})
    active_by_chat[str(chat_id)] = str(ticket_id)
    save_ticket_state(cfg, state)


def _active_ticket(chat_id: str, state: dict) -> str | None:
    active_by_chat = state.get("active_by_chat", {})
    if not isinstance(active_by_chat, dict):
        return None
    ticket_id = str(active_by_chat.get(str(chat_id)) or "").strip()
    return ticket_id or None


def _status(ticket_id: str, cfg: dict) -> str:
    state = load_ticket_state(cfg)
    status, _ = _resolved_status(ticket_id, (state.get("tickets", {}).get(ticket_id) or {}), cfg)
    return status


def _format_number(value: object) -> str:
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "-"


def _format_eur(value: object) -> str:
    try:
        return f"{float(value):.2f} EUR"
    except (TypeError, ValueError):
        return "- EUR"


def _ticket_operator_state(trade_candidate: dict) -> str:
    actionable = bool(trade_candidate.get("operational_is_actionable", True))
    if not actionable:
        return "unvollstaendig"
    decision = str(trade_candidate.get("decision") or "").upper()
    if decision == "PENDING_MARKET_OPEN":
        return "Markt geschlossen"
    if decision == "REDUCED":
        return "reduziert"
    if decision == "APPROVED":
        return "operativ"
    return "offen"


def _clear_pending_exit_fields(row: dict) -> None:
    row["pending_exit_reason"] = None
    row["pending_exit_price"] = None
    row["pending_exit_size_eur"] = None
    row["pending_exit_note"] = None


def _exit_title(action: str, reason: object = None) -> str:
    reason_code = str(reason or "").strip().upper()
    if reason_code == "STOP_LOSS":
        return "STOP-LOSS"
    if reason_code == "TARGET_REACHED":
        return "ZIEL ERREICHT"
    if str(action or "").strip().upper() == "PARTIAL_EXIT":
        return "TEILVERKAUF"
    return "VOLLVERKAUF"


def _exit_reason_label(reason: object, action: str | None = None) -> str:
    code = str(reason or "").strip().upper()
    if not code:
        return "-"
    if code == "MANUAL_EXIT" and str(action or "").strip().upper() == "FULL_EXIT":
        return "Manuell geschlossen"
    return EXIT_REASON_LABELS.get(code, code.replace("_", " ").title())


def _exit_price_prompt(name: str, action: str, reason: object = None) -> str:
    return (
        f"{_exit_title(action, reason)}: {name}\n\n"
        "Exit-Kurs:\n"
        "Bitte nur Zahl senden."
    )


def _exit_size_prompt(name: str, remaining_size_eur: object) -> str:
    lines = [f"TEILVERKAUF: {name}", "", "Exit-Menge:"]
    if remaining_size_eur is not None:
        lines.append(f"Aktuelle Restgroesse: {_format_eur(remaining_size_eur)}")
    lines.append("Bitte Betrag in EUR senden.")
    return "\n".join(lines)


def _exit_reason_prompt(name: str, action: str) -> str:
    if action == "PARTIAL_EXIT":
        return (
            f"TEILVERKAUF: {name}\n\n"
            "Exit-Grund:\n"
            "1 = Teilgewinn\n"
            "2 = Risiko reduziert\n"
            "3 = Manuell"
        )
    return (
        f"VOLLVERKAUF: {name}\n\n"
        "Exit-Grund:\n"
        "1 = Ziel erreicht\n"
        "2 = Stop-Loss\n"
        "3 = Manuell"
    )


def _exit_note_prompt(name: str, row: dict) -> str:
    action = str(row.get("pending_action") or "").upper()
    reason = str(row.get("pending_exit_reason") or "").upper()
    lines = [
        f"{_exit_title(action, reason)}: {name}",
        "",
        "Exit-Zusammenfassung:",
        f"- Exit-Kurs: {_format_number(row.get('pending_exit_price'))}",
    ]
    if action == "PARTIAL_EXIT":
        lines.append(f"- Exit-Menge: {_format_eur(row.get('pending_exit_size_eur'))}")
    lines.append(f"- Exit-Grund: {_exit_reason_label(reason, action)}")
    lines.extend(["", "Bemerkung optional:", "Kurzen Text senden oder - zum Ueberspringen."])
    return "\n".join(lines)


def _normalize_exit_note(raw: str) -> str | None:
    text = str(raw or "").strip()
    if not text or text.lower() in {"-", "skip", "/skip", "weiter", "keine", "kein", "nein"}:
        return None
    return text[:250]


def _write_execution_record(ticket_id: str, payload: dict, cfg: dict, prefix: str) -> str:
    day_dir = _execution_dir(cfg)
    ensure_dir(day_dir)
    path = day_dir / f"{prefix}_{ticket_id}.json"
    write_json(path, payload)
    return str(path)


def _ticket_text_with_status(ticket_id: str, cfg: dict) -> str:
    trade_candidate = load_trade_candidate(ticket_id, cfg)
    if not trade_candidate:
        return f"Kein Ticket fuer '{ticket_id}' gefunden."
    text = f"{render_ticket_text(trade_candidate)}\n\nStatus: {_status_label(_status(ticket_id, cfg))}"
    performance = render_ticket_performance(ticket_id, cfg)
    if performance:
        text = f"{text}\n\n{performance}"
    detail = _format_lifecycle_detail(ticket_id, cfg)
    if detail:
        text = f"{text}\n\n{detail}"
    return text[:1800]


def _latest_execution_records(cfg: dict) -> dict[str, dict]:
    root = _root_dir(cfg) / "data" / "virus_bridge" / "executions"
    if not root.exists():
        return {}
    records: dict[str, dict] = {}
    for path in sorted(root.rglob("execution_*.json")):
        try:
            payload = read_json(path)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        ticket_id = str(payload.get("ticket_id") or "").strip()
        if ticket_id:
            records[ticket_id] = payload
    return records


def render_tickets_text(cfg: dict, limit: int = 10, status_filter: str | None = None) -> str:
    rows = load_recent_trade_candidates(cfg, limit=limit)
    state = load_ticket_state(cfg)
    state_rows = (state.get("tickets") or {}) if isinstance(state, dict) else {}
    executions = _latest_execution_records(cfg)
    if not rows and not state_rows:
        return "Keine Trade-Tickets vorhanden."

    open_ticket_lines: list[str] = []
    open_position_lines: list[str] = []
    partial_lines: list[str] = []
    closed_lines: list[str] = []
    rejected_lines: list[str] = []
    deferred_lines: list[str] = []
    seen_ticket_ids: set[str] = set()

    for row in rows:
        ticket_id = str(row.get("ticket_id") or "").strip()
        if not ticket_id:
            continue
        seen_ticket_ids.add(ticket_id)
        asset = row.get("asset") or {}
        name = candidate_name(asset)
        status, _ = _resolved_status(ticket_id, (state_rows.get(ticket_id) or {}), cfg)
        status = status.upper()
        operator_state = _ticket_operator_state(row)
        if status in OPEN_TICKET_STATUSES:
            open_ticket_lines.append(f"{len(open_ticket_lines) + 1}. {name} | offen | {operator_state}")
            continue
        if status == "DEFERRED":
            deferred_lines.append(f"{len(deferred_lines) + 1}. {name} | verschoben | {operator_state}")
            continue
        if status == "EXECUTED":
            size_eur = (state_rows.get(ticket_id) or {}).get("entry_size_eur")
            if size_eur is None:
                size_eur = (executions.get(ticket_id) or {}).get("size_eur")
            open_position_lines.append(f"{len(open_position_lines) + 1}. {name} | offen | Einsatz {_format_eur(size_eur)}")
            continue
        if status == "PARTIALLY_CLOSED":
            remaining = (state_rows.get(ticket_id) or {}).get("remaining_size_eur")
            partial_lines.append(f"{len(partial_lines) + 1}. {name} | Rest {_format_eur(remaining)}")
            continue
        if status == "CLOSED":
            exit_record = latest_exit_record(ticket_id, cfg) or {}
            pnl_eur = exit_record.get("realized_pnl_eur")
            pnl_pct = exit_record.get("realized_pnl_pct")
            if pnl_eur is not None and pnl_pct is not None:
                closed_lines.append(f"{len(closed_lines) + 1}. {name} | Ergebnis {_format_number(pnl_eur)} EUR / {_format_number(pnl_pct)} %")
            else:
                closed_lines.append(f"{len(closed_lines) + 1}. {name} | geschlossen")
            continue
        if status == "REJECTED":
            rejected_lines.append(f"{len(rejected_lines) + 1}. {name}")

    for ticket_id, row in state_rows.items():
        if ticket_id in seen_ticket_ids:
            continue
        status, _ = _resolved_status(ticket_id, row, cfg)
        status = status.upper()
        name = str(row.get("asset_name") or ticket_id)
        if status == "EXECUTED":
            open_position_lines.append(f"{len(open_position_lines) + 1}. {name} | offen | Einsatz {_format_eur(row.get('entry_size_eur'))}")
        elif status in OPEN_TICKET_STATUSES:
            open_ticket_lines.append(f"{len(open_ticket_lines) + 1}. {name} | offen | Ticket")
        elif status == "PARTIALLY_CLOSED":
            partial_lines.append(f"{len(partial_lines) + 1}. {name} | Rest {_format_eur(row.get('remaining_size_eur'))}")
        elif status == "CLOSED":
            exit_record = latest_exit_record(ticket_id, cfg) or {}
            pnl_eur = exit_record.get("realized_pnl_eur")
            pnl_pct = exit_record.get("realized_pnl_pct")
            closed_lines.append(
                f"{len(closed_lines) + 1}. {name} | Ergebnis {_format_number(pnl_eur)} EUR / {_format_number(pnl_pct)} %"
                if pnl_eur is not None and pnl_pct is not None
                else f"{len(closed_lines) + 1}. {name} | geschlossen"
            )
        elif status == "REJECTED":
            rejected_lines.append(f"{len(rejected_lines) + 1}. {name}")
        elif status == "DEFERRED":
            deferred_lines.append(f"{len(deferred_lines) + 1}. {name} | {status}")

    if status_filter == "OPEN":
        lines = ["Offene Positionen:"] + (open_position_lines or ["Keine offenen Positionen."])
        if open_ticket_lines:
            lines.extend(["", "Offene Tickets:"] + open_ticket_lines)
        return "\n".join(lines)[:1800]
    if status_filter == "PARTIALLY_CLOSED":
        return "\n".join(["Teilweise verkauft:"] + (partial_lines or ["Keine teilweise verkauften Positionen."]))[:1800]
    if status_filter == "EXECUTED":
        return "\n".join(["Offene Positionen:"] + (open_position_lines or ["Keine offenen Positionen."]))[:1800]
    if status_filter == "CLOSED":
        return "\n".join(["Geschlossen:"] + (closed_lines or ["Keine geschlossenen Positionen."]))[:1800]
    if status_filter == "REJECTED":
        return "\n".join(["Abgelehnte Tickets:"] + (rejected_lines or ["Keine abgelehnten Tickets."]))[:1800]
    if status_filter == "DEFERRED":
        return "\n".join(["Später:"] + (deferred_lines or ["Keine späteren Tickets."]))[:1800]

    if not open_ticket_lines and not open_position_lines and not partial_lines and not closed_lines and not rejected_lines and not deferred_lines:
        return "Keine Tickets vorhanden."

    lines = []
    if open_position_lines:
        lines.extend(["Offene Positionen:"] + open_position_lines + [""])
    if partial_lines:
        lines.extend(["Teilweise verkauft:"] + partial_lines + [""])
    if closed_lines:
        lines.extend(["Geschlossen:"] + closed_lines + [""])
    if open_ticket_lines:
        lines.extend(["Offene Tickets:"] + open_ticket_lines + [""])
    if deferred_lines:
        lines.extend(["Später:"] + deferred_lines + [""])
    if rejected_lines:
        lines.extend(["Abgelehnt:"] + rejected_lines + [""])
    lines.append("Nutze /ticket <ticket_id> fuer Details.")
    return "\n".join(lines)[:1800]


def render_ticket_command_text(ticket_id: str, cfg: dict) -> tuple[str, dict]:
    trade_candidate = load_trade_candidate(ticket_id, cfg)
    if not trade_candidate:
        return f"Kein Ticket fuer '{ticket_id}' gefunden.", {"action": "ticket_missing", "ticket_id": ticket_id}
    action = {"action": "ticket", "ticket_id": ticket_id, "ui_context": "ticket"}
    status = _status(ticket_id, cfg)
    if status in OPEN_TICKET_STATUSES:
        action["reply_keyboard"] = _ticket_keyboard_for_candidate(ticket_id, trade_candidate)
        return _ticket_text_with_status(ticket_id, cfg), action
    if status in OPEN_POSITION_STATUSES:
        action["reply_keyboard"] = _position_keyboard(ticket_id)
        action["ui_context"] = "position"
        performance = render_ticket_performance(ticket_id, cfg)
        detail = _format_lifecycle_detail(ticket_id, cfg)
        text = render_open_position_text(ticket_id, cfg)
        if performance:
            text = f"{text}\n\n{performance}"
        if detail:
            text = f"{text}\n\n{detail}"
        return text[:1800], action
    return _ticket_text_with_status(ticket_id, cfg), action


def _parse_positive_float(text: str) -> float | None:
    try:
        value = float(str(text).strip().replace(",", "."))
    except ValueError:
        return None
    return value if value > 0 else None


def _pending_ticket_for_chat(chat_id: str, state: dict) -> tuple[str, dict] | tuple[None, None]:
    matches: list[tuple[str, dict]] = []
    for ticket_id, row in (state.get("tickets", {}) or {}).items():
        if row.get("awaiting_input") and str(row.get("chat_id") or "") == chat_id:
            matches.append((ticket_id, row))
    if not matches:
        return None, None
    matches.sort(key=lambda item: str(item[1].get("last_updated") or ""), reverse=True)
    return matches[0]


def _resolve_exit_reason(raw: str, action: str) -> str | None:
    value = str(raw or "").strip().upper()
    if not value:
        return None
    mapping = PARTIAL_REASON_MAP if action == "PARTIAL_EXIT" else FULL_REASON_MAP
    if value in mapping:
        return mapping[value]
    normalized = value.replace(" ", "_").replace("-", "_")
    for reason, label in EXIT_REASON_LABELS.items():
        if normalized in {reason, str(label).strip().upper().replace(" ", "_").replace("-", "_")}:
            return reason
    return None


def _finalize_exit_from_state(ticket_id: str, row: dict, cfg: dict) -> tuple[str, dict]:
    trade_candidate = load_trade_candidate(ticket_id, cfg) or {}
    name = candidate_name((trade_candidate.get("asset") or {}) or {"name": ticket_id})
    action = str(row.get("pending_action") or "").upper()
    note = str(row.get("pending_exit_note") or "").strip() or None
    exit_record = {
        "exit_price": row.get("pending_exit_price"),
        "size_eur": row.get("pending_exit_size_eur"),
        "exit_reason": row.get("pending_exit_reason"),
        "exit_note": note,
        "timestamp": _now(),
    }
    try:
        if action == "PARTIAL_EXIT":
            mark_partial_exit(ticket_id, exit_record, cfg)
            updated_row = (load_ticket_state(cfg).get("tickets", {}) or {}).get(ticket_id, {})
            realized = compute_realized_pnl(row.get("entry_price"), row.get("pending_exit_price"), row.get("pending_exit_size_eur"))
            return (
                f"Teilverkauf gespeichert:\n{name}\n"
                f"Exit-Kurs: {row.get('pending_exit_price')}\n"
                f"Exit-Menge: {row.get('pending_exit_size_eur')} EUR\n"
                f"Exit-Grund: {_exit_reason_label(row.get('pending_exit_reason'), action)}\n"
                f"Bemerkung: {note or '-'}\n"
                f"Restgroesse: {_format_eur(updated_row.get('remaining_size_eur'))}\n"
                f"Ergebnis: {_format_number(realized.get('realized_pnl_eur'))} EUR / {_format_number(realized.get('realized_pnl_pct'))} %",
                {"action": "ticket_partial_exit", "ticket_id": ticket_id},
            )
        mark_full_exit(ticket_id, exit_record, cfg)
        size_eur = row.get("remaining_size_eur") or row.get("entry_size_eur")
        realized = compute_realized_pnl(row.get("entry_price"), row.get("pending_exit_price"), size_eur)
        return (
            f"Vollverkauf gespeichert:\n{name}\n"
            f"Exit-Kurs: {row.get('pending_exit_price')}\n"
            f"Exit-Grund: {_exit_reason_label(row.get('pending_exit_reason'), action)}\n"
            f"Bemerkung: {note or '-'}\n"
            f"Ergebnis: {_format_number(realized.get('realized_pnl_eur'))} EUR / {_format_number(realized.get('realized_pnl_pct'))} %",
            {"action": "ticket_full_exit", "ticket_id": ticket_id},
        )
    except ValueError:
        state = load_ticket_state(cfg)
        state_row = _entry(state, ticket_id)
        _clear_pending_exit_fields(state_row)
        state_row["awaiting_input"] = None
        state_row["pending_action"] = None
        state_row["last_updated"] = _now()
        save_ticket_state(cfg, state)
        return (
            "Exit konnte nicht gespeichert werden. Bitte Exit-Kurs, Exit-Menge und Restgroesse pruefen.",
            {"action": "ticket_exit_finalize_invalid", "ticket_id": ticket_id},
        )


def handle_pending_ticket_input(text: str, chat_id: str, cfg: dict) -> tuple[str, dict] | None:
    state = load_ticket_state(cfg)
    ticket_id, row = _pending_ticket_for_chat(str(chat_id), state)
    if not ticket_id or not row:
        return None

    value = _parse_positive_float(text)
    if row.get("awaiting_input") == "BUY_PRICE":
        if value is None:
            return (
                "Bitte nur einen gueltigen positiven Kurs senden, z. B. 257.10",
                {"action": "ticket_buy_price_invalid", "ticket_id": ticket_id},
            )
        row["buy_price"] = round(value, 4)
        row["awaiting_input"] = "BUY_SIZE_EUR"
        row["last_updated"] = _now()
        save_ticket_state(cfg, state)
        return (
            "Wie viel investiert? Bitte in EUR eingeben, z. B. 875",
            {"action": "ticket_buy_price", "ticket_id": ticket_id, "buy_price": row["buy_price"]},
        )

    if row.get("awaiting_input") == "BUY_SIZE_EUR":
        if value is None:
            return (
                "Bitte nur einen gueltigen positiven EUR-Betrag senden, z. B. 875",
                {"action": "ticket_buy_size_invalid", "ticket_id": ticket_id},
            )
        trade_candidate = load_trade_candidate(ticket_id, cfg)
        name = candidate_name((trade_candidate or {}).get("asset") or {"name": ticket_id})
        row["size_eur"] = round(value, 2)
        row["status"] = "EXECUTED"
        row["awaiting_input"] = None
        row["pending_action"] = None
        row["last_updated"] = _now()
        row["entry_price"] = row.get("buy_price")
        row["entry_size_eur"] = row["size_eur"]
        row["remaining_size_eur"] = row["size_eur"]
        execution_record = {
            "ticket_id": ticket_id,
            "status": "EXECUTED",
            "buy_price": row.get("buy_price"),
            "size_eur": row["size_eur"],
            "executed_at": row["last_updated"],
            "source": "telegram_manual",
        }
        save_ticket_state(cfg, state)
        path = _write_execution_record(ticket_id, execution_record, cfg, "execution")
        record_ticket_lifecycle_event(
            "TRADE_EXECUTED_MANUAL",
            {
                "ticket_id": ticket_id,
                "source_proposal_id": (trade_candidate or {}).get("source_proposal_id"),
                "asset": (trade_candidate or {}).get("asset"),
                "decision": (trade_candidate or {}).get("decision"),
                "status": "EXECUTED",
                "buy_price": row.get("buy_price"),
                "size_eur": row["size_eur"],
                "timestamp": row["last_updated"],
            },
            cfg,
        )
        return (
            f"Ausfuehrung gespeichert:\n{name}\nKaufkurs: {row.get('buy_price')}\nEinsatz: {row['size_eur']} EUR",
            {"action": "ticket_executed", "ticket_id": ticket_id, "path": path},
        )

    if row.get("awaiting_input") == "EXIT_PRICE":
        if value is None:
            return (
                "Bitte nur einen gueltigen positiven Verkaufskurs senden.",
                {"action": "ticket_exit_price_invalid", "ticket_id": ticket_id},
            )
        trade_candidate = load_trade_candidate(ticket_id, cfg)
        name = candidate_name((trade_candidate or {}).get("asset") or {"name": ticket_id})
        row["pending_exit_price"] = round(value, 4)
        row["last_updated"] = _now()
        if str(row.get("pending_action") or "").upper() == "PARTIAL_EXIT":
            row["awaiting_input"] = "EXIT_SIZE_EUR"
            save_ticket_state(cfg, state)
            return (
                _exit_size_prompt(name, row.get("remaining_size_eur")),
                {"action": "ticket_exit_price", "ticket_id": ticket_id},
            )
        if row.get("pending_exit_reason"):
            row["awaiting_input"] = "EXIT_NOTE"
            save_ticket_state(cfg, state)
            return (_exit_note_prompt(name, row), {"action": "ticket_exit_price", "ticket_id": ticket_id})
        row["awaiting_input"] = "EXIT_REASON"
        save_ticket_state(cfg, state)
        return (_exit_reason_prompt(name, str(row.get("pending_action") or "")), {"action": "ticket_exit_price", "ticket_id": ticket_id})

    if row.get("awaiting_input") == "EXIT_SIZE_EUR":
        if value is None:
            return (
                "Bitte nur einen gueltigen positiven Verkaufsbetrag senden.",
                {"action": "ticket_exit_size_invalid", "ticket_id": ticket_id},
            )
        remaining = _parse_positive_float(str(row.get("remaining_size_eur") or ""))
        if remaining is not None and value > remaining:
            return (
                f"Verkaufsbetrag darf die Restgroesse nicht uebersteigen. Aktuell: {remaining:.2f} EUR",
                {"action": "ticket_exit_size_too_large", "ticket_id": ticket_id},
            )
        row["pending_exit_size_eur"] = round(value, 2)
        row["awaiting_input"] = "EXIT_REASON"
        row["last_updated"] = _now()
        save_ticket_state(cfg, state)
        trade_candidate = load_trade_candidate(ticket_id, cfg)
        name = candidate_name((trade_candidate or {}).get("asset") or {"name": ticket_id})
        return (_exit_reason_prompt(name, str(row.get("pending_action") or "")), {"action": "ticket_exit_size", "ticket_id": ticket_id})

    if row.get("awaiting_input") == "EXIT_REASON":
        reason = _resolve_exit_reason(text, str(row.get("pending_action") or "").upper())
        if not reason:
            return (
                "Bitte Grund mit 1, 2 oder 3 angeben.",
                {"action": "ticket_exit_reason_invalid", "ticket_id": ticket_id},
            )
        row["pending_exit_reason"] = reason
        row["awaiting_input"] = "EXIT_NOTE"
        row["last_updated"] = _now()
        save_ticket_state(cfg, state)
        trade_candidate = load_trade_candidate(ticket_id, cfg)
        name = candidate_name((trade_candidate or {}).get("asset") or {"name": ticket_id})
        return (_exit_note_prompt(name, row), {"action": "ticket_exit_reason", "ticket_id": ticket_id})

    if row.get("awaiting_input") == "EXIT_NOTE":
        row["pending_exit_note"] = _normalize_exit_note(text)
        row["last_updated"] = _now()
        save_ticket_state(cfg, state)
        return _finalize_exit_from_state(ticket_id, row, cfg)
    return None


def handle_ticket_action(text: str, chat_id: str, cfg: dict, ui_context: str | None = None) -> tuple[str, dict] | None:
    raw = str(text or "").strip()
    state = load_ticket_state(cfg)
    action_name = ""
    ticket_id = ""
    if ":" in raw:
        action_name, ticket_id = raw.split(":", 1)
        action_name = action_name.strip().upper()
        ticket_id = ticket_id.strip()
    else:
        resolved = ticket_action_name(raw, context=ui_context)
        if not resolved:
            return None
        action_name = resolved
        ticket_id = str(_active_ticket(chat_id, state) or "").strip()
    if action_name not in {"BOUGHT", "NOT_BOUGHT", "LATER", "DETAILS", "PARTIAL_EXIT", "FULL_EXIT", "TARGET_HIT", "STOP_HIT"} or not ticket_id:
        return None

    trade_candidate = load_trade_candidate(ticket_id, cfg)
    if not trade_candidate:
        return f"Kein Ticket fuer '{ticket_id}' gefunden.", {"action": "ticket_missing", "ticket_id": ticket_id}

    for other_id, other_row in (state.get("tickets", {}) or {}).items():
        if str(other_row.get("chat_id") or "") == str(chat_id) and other_id != ticket_id:
            other_row["awaiting_input"] = None
    row = _entry(state, ticket_id)
    row["asset_name"] = candidate_name((trade_candidate or {}).get("asset") or {"name": ticket_id})
    state.setdefault("active_by_chat", {})[str(chat_id)] = ticket_id

    if action_name == "DETAILS":
        action = {"action": "ticket_details", "ticket_id": ticket_id}
        status = _status(ticket_id, cfg)
        if status == "OPEN":
            action["reply_keyboard"] = _ticket_keyboard_for_candidate(ticket_id, trade_candidate)
            action["ui_context"] = "ticket"
            save_ticket_state(cfg, state)
            return _ticket_text_with_status(ticket_id, cfg), action
        if status in OPEN_POSITION_STATUSES:
            action["reply_keyboard"] = _position_keyboard(ticket_id)
            action["ui_context"] = "position"
        save_ticket_state(cfg, state)
        if status in OPEN_POSITION_STATUSES:
            return render_open_position_text(ticket_id, cfg), action
        return _ticket_text_with_status(ticket_id, cfg), action

    if action_name == "BOUGHT":
        market_status = trade_candidate.get("market_status")
        if isinstance(market_status, dict) and "is_open" in market_status and not bool(market_status.get("is_open")):
            return (
                "Markt ist aktuell geschlossen. Kauf erst pruefen, wenn der Markt wieder offen ist.",
                {"action": "ticket_market_closed", "ticket_id": ticket_id},
            )
        row["status"] = "OPEN"
        row["chat_id"] = str(chat_id)
        row["awaiting_input"] = "BUY_PRICE"
        row["last_updated"] = _now()
        row["pending_action"] = None
        row.pop("size_eur", None)
        row.pop("buy_price", None)
        _clear_pending_exit_fields(row)
        save_ticket_state(cfg, state)
        return (
            "Zu welchem Kurs gekauft? Bitte nur Zahl senden, z. B. 257.10",
            {"action": "ticket_bought_start", "ticket_id": ticket_id},
        )

    if action_name in {"PARTIAL_EXIT", "FULL_EXIT", "TARGET_HIT", "STOP_HIT"}:
        status = str(row.get("status") or "").upper()
        if status not in OPEN_POSITION_STATUSES:
            return (
                "Fuer dieses Ticket ist aktuell keine offene Position hinterlegt.",
                {"action": "ticket_exit_not_open", "ticket_id": ticket_id},
            )
        row["chat_id"] = str(chat_id)
        row["last_updated"] = _now()
        row["pending_action"] = "PARTIAL_EXIT" if action_name == "PARTIAL_EXIT" else "FULL_EXIT"
        row["awaiting_input"] = "EXIT_PRICE"
        _clear_pending_exit_fields(row)
        if action_name == "TARGET_HIT":
            row["pending_exit_reason"] = "TARGET_REACHED"
        elif action_name == "STOP_HIT":
            row["pending_exit_reason"] = "STOP_LOSS"
        save_ticket_state(cfg, state)
        if row["pending_action"] == "PARTIAL_EXIT":
            return (
                _exit_price_prompt(row["asset_name"], row["pending_action"]),
                {"action": "ticket_partial_exit_start", "ticket_id": ticket_id},
            )
        return (
            _exit_price_prompt(row["asset_name"], row["pending_action"], row.get("pending_exit_reason")),
            {"action": "ticket_full_exit_start", "ticket_id": ticket_id},
        )

    row["chat_id"] = str(chat_id)
    row["awaiting_input"] = None
    row["pending_action"] = None
    row["last_updated"] = _now()
    _clear_pending_exit_fields(row)
    if action_name == "NOT_BOUGHT":
        row["status"] = "REJECTED"
        path = _write_execution_record(
            ticket_id,
            {"ticket_id": ticket_id, "status": "REJECTED", "updated_at": row["last_updated"], "source": "telegram_manual"},
            cfg,
            "status",
        )
        save_ticket_state(cfg, state)
        record_ticket_lifecycle_event(
            "TRADE_REJECTED_MANUAL",
            {
                "ticket_id": ticket_id,
                "source_proposal_id": trade_candidate.get("source_proposal_id"),
                "asset": trade_candidate.get("asset"),
                "decision": trade_candidate.get("decision"),
                "status": "REJECTED",
                "timestamp": row["last_updated"],
            },
            cfg,
        )
        return "Trade-Ticket als nicht gekauft markiert.", {"action": "ticket_rejected", "ticket_id": ticket_id, "path": path}

    row["status"] = "DEFERRED"
    path = _write_execution_record(
        ticket_id,
        {"ticket_id": ticket_id, "status": "DEFERRED", "updated_at": row["last_updated"], "source": "telegram_manual"},
        cfg,
        "status",
    )
    save_ticket_state(cfg, state)
    record_ticket_lifecycle_event(
        "TRADE_DEFERRED",
        {
            "ticket_id": ticket_id,
            "source_proposal_id": trade_candidate.get("source_proposal_id"),
            "asset": trade_candidate.get("asset"),
            "decision": trade_candidate.get("decision"),
            "status": "DEFERRED",
            "timestamp": row["last_updated"],
        },
        cfg,
    )
    return "Trade-Ticket bleibt offen und wurde auf spaeter gesetzt.", {"action": "ticket_deferred", "ticket_id": ticket_id, "path": path}
