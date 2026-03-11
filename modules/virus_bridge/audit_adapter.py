from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from modules.common.utils import append_jsonl, ensure_dir, now_iso_tz

try:
    from modules.portfolio_ingest.reporter_audit_notify import append_audit_event as _append_audit_event
except Exception:  # pragma: no cover
    _append_audit_event = None


def _root_dir(cfg: dict) -> Path:
    return Path(cfg.get("app", {}).get("root_dir", Path.cwd()))


def _official_audit_path(cfg: dict) -> Path:
    root = _root_dir(cfg)
    configured = cfg.get("paths", {}).get("audit_jsonl")
    return Path(configured) if configured else (root / "data" / "audit" / "portfolio_audit.jsonl")


def _fallback_audit_path(cfg: dict) -> Path:
    stamp = datetime.now().strftime("%Y%m%d")
    return _root_dir(cfg) / "data" / "virus_bridge" / f"audit_events_{stamp}.jsonl"


def _json_safe(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
    except Exception:
        return str(value)


def build_audit_payload(ticket: dict, extra: dict | None = None) -> dict:
    merged = dict(ticket or {})
    if isinstance(extra, dict):
        merged.update(extra)
    timestamp = str(
        merged.get("timestamp")
        or merged.get("executed_at")
        or merged.get("updated_at")
        or merged.get("last_updated")
        or now_iso_tz()
    )
    return _json_safe(
        {
            "ticket_id": merged.get("ticket_id"),
            "source_proposal_id": merged.get("source_proposal_id"),
            "asset": dict(merged.get("asset") or {}),
            "status": merged.get("status"),
            "decision": merged.get("decision"),
            "buy_price": merged.get("buy_price"),
            "size_eur": merged.get("size_eur"),
            "exit_price": merged.get("exit_price"),
            "exit_reason": merged.get("exit_reason"),
            "closed_fraction": merged.get("closed_fraction"),
            "realized_pnl_eur": merged.get("realized_pnl_eur"),
            "realized_pnl_pct": merged.get("realized_pnl_pct"),
            "timestamp": timestamp,
        }
    )


def _event_row(event_type: str, payload: dict, cfg: dict) -> dict:
    return {
        "ts": str(payload.get("timestamp") or now_iso_tz(cfg.get("app", {}).get("timezone", "Europe/Berlin"))),
        "event_type": event_type,
        "source": {"module": "virus_bridge", "layer": "ticket_lifecycle"},
        **build_audit_payload(payload),
    }


def emit_ticket_event(event_type: str, payload: dict, cfg: dict) -> dict:
    event = _event_row(event_type, payload, cfg)
    official_path = _official_audit_path(cfg)
    if _append_audit_event is not None:
        try:
            _append_audit_event(event, str(official_path))
            ref = f"{official_path}#{event['ts']}"
            return {
                "status": "ok",
                "event_type": event_type,
                "ref": ref,
                "ok": True,
                "mode": "official",
                "path": str(official_path),
                "event": event,
            }
        except Exception:
            pass

    fallback_path = _fallback_audit_path(cfg)
    try:
        ensure_dir(fallback_path.parent)
        append_jsonl(fallback_path, event)
        ref = f"{fallback_path}#{event['ts']}"
        return {
            "status": "fallback",
            "event_type": event_type,
            "ref": ref,
            "ok": True,
            "mode": "fallback",
            "path": str(fallback_path),
            "event": event,
        }
    except Exception as exc:
        return {
            "status": "error",
            "event_type": event_type,
            "ref": None,
            "ok": False,
            "mode": "error",
            "path": str(fallback_path),
            "event": event,
            "error": str(exc),
        }
