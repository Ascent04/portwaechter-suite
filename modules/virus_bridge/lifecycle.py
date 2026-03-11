from __future__ import annotations

import json
from pathlib import Path

from modules.common.utils import ensure_dir, now_iso_tz, read_json
from modules.virus_bridge.audit_adapter import build_audit_payload, emit_ticket_event


VALID_STATUSES = {"CREATED", "SENT", "OPEN", "EXECUTED", "PARTIALLY_CLOSED", "CLOSED", "REJECTED", "DEFERRED"}
EVENT_STATUS_MAP = {
    "TRADE_CANDIDATE_CREATED": "CREATED",
    "TRADE_TICKET_SENT": "SENT",
    "TRADE_EXECUTED_MANUAL": "EXECUTED",
    "TRADE_REJECTED_MANUAL": "REJECTED",
    "TRADE_DEFERRED": "DEFERRED",
    "TRADE_PARTIAL_EXIT": "PARTIALLY_CLOSED",
    "TRADE_CLOSED_MANUAL": "CLOSED",
    "TRADE_CLOSED_STOP_LOSS": "CLOSED",
    "TRADE_CLOSED_TARGET_REACHED": "CLOSED",
}
TERMINAL_EVENTS = {"TRADE_REJECTED_MANUAL", "TRADE_CLOSED_MANUAL", "TRADE_CLOSED_STOP_LOSS", "TRADE_CLOSED_TARGET_REACHED"}
COMPAT_FIELDS = ("created", "sent", "executed", "rejected", "deferred", "closed")


def _root_dir(cfg: dict) -> Path:
    return Path(cfg.get("app", {}).get("root_dir", Path.cwd()))


def _lifecycle_dir(cfg: dict) -> Path:
    return _root_dir(cfg) / "data" / "virus_bridge" / "ticket_lifecycle"


def _lifecycle_path(ticket_id: str, cfg: dict) -> Path:
    return _lifecycle_dir(cfg) / f"{ticket_id}.json"


def _state_path(cfg: dict) -> Path:
    return _root_dir(cfg) / "data" / "virus_bridge" / "ticket_state.json"


def _write_lifecycle(path: Path, payload: dict) -> None:
    ensure_dir(path.parent)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def _timestamp(value: object, cfg: dict) -> str:
    raw = str(value or "").strip()
    return raw or now_iso_tz(cfg.get("app", {}).get("timezone", "Europe/Berlin"))


def _compat_event(event_type: str, timestamp: str, data: dict) -> dict:
    return {
        "event_type": event_type,
        "timestamp": timestamp,
        "decision": data.get("decision"),
        "status": data.get("status"),
        "buy_price": data.get("buy_price"),
        "size_eur": data.get("size_eur"),
        "exit_price": data.get("exit_price"),
        "exit_reason": data.get("exit_reason"),
        "closed_fraction": data.get("closed_fraction"),
        "realized_pnl_eur": data.get("realized_pnl_eur"),
        "realized_pnl_pct": data.get("realized_pnl_pct"),
    }


def _empty(ticket: dict, cfg: dict) -> dict:
    created_at = _timestamp(ticket.get("timestamp"), cfg)
    return {
        "ticket_id": str(ticket.get("ticket_id") or "").strip(),
        "source_proposal_id": ticket.get("source_proposal_id"),
        "asset": dict(ticket.get("asset") or {}),
        "created_at": created_at,
        "events": [],
        "current_status": "CREATED",
        "last_updated": created_at,
        "created": None,
        "sent": None,
        "executed": None,
        "partial_closes": [],
        "rejected": None,
        "deferred": None,
        "closed": None,
        "audit_refs": [],
    }


def _normalize_event(event: dict, cfg: dict) -> dict:
    event_type = str(event.get("event_type") or "").strip().upper()
    timestamp = _timestamp(event.get("timestamp"), cfg)
    data = dict(event.get("data") or {})
    return {
        "event_type": event_type,
        "timestamp": timestamp,
        "data": build_audit_payload(data, {"timestamp": timestamp}),
        "audit_ref": event.get("audit_ref"),
    }


def _from_legacy(data: dict, cfg: dict) -> dict:
    if isinstance(data.get("events"), list):
        events = [_normalize_event(event, cfg) for event in data.get("events", []) if isinstance(event, dict)]
        lifecycle = dict(data)
        lifecycle["events"] = sorted(events, key=lambda row: str(row.get("timestamp") or ""))
    else:
        events: list[dict] = []
        for field in COMPAT_FIELDS:
            row = data.get(field)
            if isinstance(row, dict) and row:
                events.append(
                    {
                        "event_type": str(row.get("event_type") or "").strip().upper(),
                        "timestamp": _timestamp(row.get("timestamp"), cfg),
                        "data": build_audit_payload(data, row),
                        "audit_ref": None,
                    }
                )
        for row in data.get("partial_closes", []) if isinstance(data.get("partial_closes"), list) else []:
            if isinstance(row, dict) and row:
                events.append(
                    {
                        "event_type": str(row.get("event_type") or "TRADE_PARTIAL_EXIT").strip().upper(),
                        "timestamp": _timestamp(row.get("timestamp"), cfg),
                        "data": build_audit_payload(data, row),
                        "audit_ref": None,
                    }
                )
        lifecycle = _empty(data, cfg)
        lifecycle.update({"ticket_id": data.get("ticket_id"), "source_proposal_id": data.get("source_proposal_id"), "asset": dict(data.get("asset") or {})})
        lifecycle["events"] = sorted(events, key=lambda row: str(row.get("timestamp") or ""))
        lifecycle["created_at"] = _timestamp(data.get("created_at") or data.get("last_updated"), cfg)
    return _with_compat(lifecycle)


def _status_from_event(event: dict) -> str:
    data = event.get("data") or {}
    explicit = str(data.get("status") or "").strip().upper()
    if explicit in VALID_STATUSES:
        return explicit
    return EVENT_STATUS_MAP.get(str(event.get("event_type") or "").strip().upper(), "OPEN")


def infer_current_status(events: list[dict]) -> str:
    if not events:
        return "CREATED"
    return _status_from_event(events[-1])


def _with_compat(lifecycle: dict) -> dict:
    events = sorted([_normalize_event(event, {"app": {}}) for event in lifecycle.get("events", []) if isinstance(event, dict)], key=lambda row: str(row.get("timestamp") or ""))
    lifecycle["events"] = events
    for field in COMPAT_FIELDS:
        lifecycle[field] = None
    lifecycle["partial_closes"] = []
    lifecycle["audit_refs"] = []
    for event in events:
        event_type = str(event.get("event_type") or "").upper()
        timestamp = str(event.get("timestamp") or "")
        data = dict(event.get("data") or {})
        compat = _compat_event(event_type, timestamp, data)
        if event_type == "TRADE_CANDIDATE_CREATED":
            lifecycle["created"] = compat
        elif event_type == "TRADE_TICKET_SENT":
            lifecycle["sent"] = compat
        elif event_type == "TRADE_EXECUTED_MANUAL":
            lifecycle["executed"] = compat
        elif event_type == "TRADE_REJECTED_MANUAL":
            lifecycle["rejected"] = compat
        elif event_type == "TRADE_DEFERRED":
            lifecycle["deferred"] = compat
        elif event_type == "TRADE_PARTIAL_EXIT":
            lifecycle["partial_closes"].append(compat)
        elif event_type in {"TRADE_CLOSED_MANUAL", "TRADE_CLOSED_STOP_LOSS", "TRADE_CLOSED_TARGET_REACHED"}:
            lifecycle["closed"] = compat
        lifecycle["audit_refs"].append({"event_type": event_type, "timestamp": timestamp, "ref": event.get("audit_ref")})
    lifecycle["current_status"] = infer_current_status(events)
    lifecycle["last_updated"] = str(events[-1].get("timestamp") or lifecycle.get("created_at")) if events else str(lifecycle.get("created_at"))
    lifecycle["created_at"] = str(lifecycle.get("created_at") or lifecycle.get("last_updated") or now_iso_tz())
    return lifecycle


def _load_state_row(ticket_id: str, cfg: dict) -> dict:
    path = _state_path(cfg)
    if not path.exists():
        return {}
    try:
        data = read_json(path)
    except Exception:
        return {}
    tickets = data.get("tickets", {}) if isinstance(data, dict) else {}
    row = tickets.get(ticket_id, {}) if isinstance(tickets, dict) else {}
    return row if isinstance(row, dict) else {}


def load_lifecycle(ticket_id: str, cfg: dict) -> dict | None:
    path = _lifecycle_path(ticket_id, cfg)
    if not path.exists():
        return None
    try:
        data = read_json(path)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    lifecycle = _from_legacy(data, cfg)
    return lifecycle if lifecycle.get("ticket_id") else None


def load_ticket_lifecycle(ticket_id: str, cfg: dict) -> dict | None:
    return load_lifecycle(ticket_id, cfg)


def init_lifecycle(ticket: dict, cfg: dict) -> dict:
    ticket_id = str(ticket.get("ticket_id") or "").strip()
    if not ticket_id:
        raise ValueError("ticket_id required")
    existing = load_lifecycle(ticket_id, cfg)
    if existing:
        return existing
    lifecycle = _empty(ticket, cfg)
    _write_lifecycle(_lifecycle_path(ticket_id, cfg), lifecycle)
    return lifecycle


def _can_append(lifecycle: dict, event_type: str) -> tuple[bool, str | None]:
    current_status = str(lifecycle.get("current_status") or "CREATED").upper()
    events = lifecycle.get("events", [])
    seen_types = {str(event.get("event_type") or "").upper() for event in events}
    close_seen = any(event_type_seen in TERMINAL_EVENTS - {"TRADE_REJECTED_MANUAL"} for event_type_seen in seen_types)

    if event_type == "TRADE_CANDIDATE_CREATED" and "TRADE_CANDIDATE_CREATED" in seen_types:
        return False, "duplicate_created"
    if event_type == "TRADE_TICKET_SENT" and "TRADE_TICKET_SENT" in seen_types:
        return False, "duplicate_sent"
    if event_type == "TRADE_EXECUTED_MANUAL" and current_status not in {"CREATED", "SENT", "OPEN", "DEFERRED"}:
        return False, "executed_invalid_transition"
    if event_type == "TRADE_REJECTED_MANUAL" and current_status not in {"CREATED", "SENT", "OPEN", "DEFERRED"}:
        return False, "rejected_invalid_transition"
    if event_type == "TRADE_DEFERRED" and current_status not in {"CREATED", "SENT", "OPEN", "DEFERRED"}:
        return False, "deferred_invalid_transition"
    if event_type == "TRADE_PARTIAL_EXIT" and current_status not in {"EXECUTED", "PARTIALLY_CLOSED"}:
        return False, "partial_invalid_transition"
    if event_type in {"TRADE_CLOSED_MANUAL", "TRADE_CLOSED_STOP_LOSS", "TRADE_CLOSED_TARGET_REACHED"} and current_status not in {"EXECUTED", "PARTIALLY_CLOSED"}:
        return False, "closed_invalid_transition"
    if close_seen and event_type in {"TRADE_CLOSED_MANUAL", "TRADE_CLOSED_STOP_LOSS", "TRADE_CLOSED_TARGET_REACHED"}:
        return False, "duplicate_terminal_close"
    if current_status in {"REJECTED", "CLOSED"} and event_type not in {"TRADE_CANDIDATE_CREATED"}:
        return False, "terminal_status_locked"
    return True, None


def append_lifecycle_event(ticket_id: str, event_type: str, data: dict, cfg: dict, audit_ref: str | None = None) -> dict:
    ticket_id = str(ticket_id or "").strip()
    if not ticket_id:
        raise ValueError("ticket_id required")
    lifecycle = load_lifecycle(ticket_id, cfg) or init_lifecycle({"ticket_id": ticket_id, **dict(data or {})}, cfg)
    event_type = str(event_type or "").strip().upper()
    if event_type not in EVENT_STATUS_MAP:
        raise ValueError(f"unsupported event_type: {event_type}")
    allowed, error = _can_append(lifecycle, event_type)
    if not allowed:
        return {"updated": False, "path": str(_lifecycle_path(ticket_id, cfg)), "lifecycle": lifecycle, "audit": None, "error": error}

    timestamp = _timestamp((data or {}).get("timestamp"), cfg)
    event_data = build_audit_payload(
        {
            "ticket_id": ticket_id,
            "source_proposal_id": lifecycle.get("source_proposal_id") or (data or {}).get("source_proposal_id"),
            "asset": lifecycle.get("asset") or (data or {}).get("asset"),
            **dict(data or {}),
            "timestamp": timestamp,
            "status": (data or {}).get("status") or EVENT_STATUS_MAP.get(event_type),
        }
    )
    audit = None
    ref = audit_ref
    if ref is None:
        audit = emit_ticket_event(event_type, event_data, cfg)
        ref = audit.get("ref")
    event = {"event_type": event_type, "timestamp": timestamp, "data": event_data, "audit_ref": ref}
    lifecycle["events"].append(event)
    lifecycle = _with_compat(lifecycle)
    _write_lifecycle(_lifecycle_path(ticket_id, cfg), lifecycle)
    return {"updated": True, "path": str(_lifecycle_path(ticket_id, cfg)), "lifecycle": lifecycle, "audit": audit}


def record_ticket_lifecycle_event(event_type: str, payload: dict, cfg: dict) -> dict:
    ticket_id = str(payload.get("ticket_id") or "").strip()
    if not ticket_id:
        raise ValueError("ticket_id required for lifecycle event")
    init_lifecycle(payload, cfg)
    return append_lifecycle_event(ticket_id, event_type, payload, cfg)


def _event_time(lifecycle: dict, event_type: str) -> str | None:
    for event in lifecycle.get("events", []):
        if str(event.get("event_type") or "").upper() == event_type:
            return str(event.get("timestamp") or "")
    return None


def validate_lifecycle(ticket_id: str, cfg: dict) -> dict:
    lifecycle = load_lifecycle(ticket_id, cfg)
    if not lifecycle:
        return {"ok": False, "errors": ["missing_lifecycle"]}
    events = lifecycle.get("events", [])
    errors: list[str] = []
    event_types = [str(event.get("event_type") or "").upper() for event in events]
    if "TRADE_CANDIDATE_CREATED" not in event_types:
        errors.append("created_event_missing")
    if "TRADE_EXECUTED_MANUAL" in event_types and not any(item in event_types for item in {"TRADE_CANDIDATE_CREATED", "TRADE_TICKET_SENT"}):
        errors.append("executed_before_created_or_sent")
    if event_types.count("TRADE_EXECUTED_MANUAL") > 1:
        errors.append("duplicate_executed")
    close_events = [event_type for event_type in event_types if event_type in {"TRADE_CLOSED_MANUAL", "TRADE_CLOSED_STOP_LOSS", "TRADE_CLOSED_TARGET_REACHED"}]
    if close_events and "TRADE_EXECUTED_MANUAL" not in event_types:
        errors.append("closed_before_executed")
    if len(close_events) > 1:
        errors.append("duplicate_terminal_close")

    row = _load_state_row(ticket_id, cfg)
    if row:
        entry_size = float(row.get("entry_size_eur") or 0)
        remaining = float(row.get("remaining_size_eur") or 0)
        partial_sum = 0.0
        for event in events:
            if str(event.get("event_type") or "").upper() == "TRADE_PARTIAL_EXIT":
                try:
                    partial_sum += float((event.get("data") or {}).get("size_eur") or 0)
                except (TypeError, ValueError):
                    continue
        if entry_size > 0 and lifecycle.get("current_status") == "PARTIALLY_CLOSED":
            expected = round(max(0.0, entry_size - partial_sum), 2)
            if abs(expected - remaining) > 0.05:
                errors.append("remaining_size_incoherent")
        if lifecycle.get("current_status") == "CLOSED" and remaining not in {0, 0.0}:
            errors.append("closed_remaining_nonzero")
    return {"ok": not errors, "errors": errors}


def validate_all_lifecycles(cfg: dict) -> dict:
    root = _lifecycle_dir(cfg)
    if not root.exists():
        return {"ok": True, "total": 0, "invalid": 0, "errors": {}}
    errors: dict[str, list[str]] = {}
    total = 0
    for path in sorted(root.glob("*.json")):
        total += 1
        result = validate_lifecycle(path.stem, cfg)
        if not result["ok"]:
            errors[path.stem] = result["errors"]
    return {"ok": not errors, "total": total, "invalid": len(errors), "errors": errors}


def summarize_audit_lifecycle_health(cfg) -> dict:
    validation = validate_all_lifecycles(cfg)
    fallback_path = _root_dir(cfg) / "data" / "virus_bridge"
    writable = fallback_path.exists() or fallback_path.parent.exists()
    return {
        "ok": bool(validation.get("ok")) and writable,
        "lifecycle_total": validation.get("total", 0),
        "lifecycle_invalid": validation.get("invalid", 0),
        "errors": validation.get("errors", {}),
        "audit_fallback_writable": writable,
    }
