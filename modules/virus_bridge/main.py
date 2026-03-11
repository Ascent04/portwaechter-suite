from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import date
from pathlib import Path

from modules.common.notification_gate import allow_notification, quiet_hours_active
from modules.common.config import load_config
from modules.common.utils import ensure_dir
from modules.integration.virus_inbox import mark_proposal_consumed
from modules.telegram_commands.poller import send_message_result
from modules.virus_bridge.entry_stop import derive_entry_hint, derive_stop_hint
from modules.virus_bridge.execution_flow import load_ticket_state, render_ticket_command_text, save_ticket_state, set_active_ticket
from modules.virus_bridge.intake import dedupe_pending_proposals, load_pending_proposals
from modules.virus_bridge.lifecycle import init_lifecycle, record_ticket_lifecycle_event
from modules.virus_bridge.risk_eval import evaluate_proposal
from modules.virus_bridge.ticket_render import render_ticket_text
from modules.virus_bridge.trade_candidate import build_trade_candidate, write_trade_candidate

log = logging.getLogger(__name__)


def _state_path(cfg: dict) -> Path:
    return Path(cfg.get("app", {}).get("root_dir", Path.cwd())) / "data" / "virus_bridge" / "telegram_state.json"


def _load_state(cfg: dict) -> dict:
    path = _state_path(cfg)
    today = date.today().isoformat()
    if not path.exists():
        return {"date": today, "sent_ticket_ids": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"date": today, "sent_ticket_ids": []}
    if str(data.get("date")) != today:
        return {"date": today, "sent_ticket_ids": []}
    return data


def _save_state(cfg: dict, state: dict) -> None:
    path = _state_path(cfg)
    ensure_dir(path.parent)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _ensure_ticket_open(ticket_id: str, cfg: dict, trade_candidate: dict | None = None) -> None:
    state = load_ticket_state(cfg)
    tickets = state.setdefault("tickets", {})
    row = tickets.setdefault(ticket_id, {"status": "OPEN", "last_updated": date.today().isoformat(), "awaiting_input": None})
    row.setdefault("status", "OPEN")
    row.setdefault("awaiting_input", None)
    row.setdefault("last_updated", date.today().isoformat())
    row.setdefault("asset_name", str(((trade_candidate or {}).get("asset") or {}).get("name") or ticket_id))
    save_ticket_state(cfg, state)


def _log_send_attempt(
    ticket_id: str,
    decision: str,
    chat_id: str,
    quiet_hours: bool,
    dedupe_hit: bool,
    allowed_to_send: bool,
) -> None:
    log.warning(
        "virus_bridge_send_attempt: ticket_id=%s decision=%s chat_id=%s quiet_hours=%s dedupe_hit=%s allowed_to_send=%s",
        ticket_id,
        decision,
        chat_id or "-",
        quiet_hours,
        dedupe_hit,
        allowed_to_send,
    )


def _log_send_result(ticket_id: str, status: str, reason: str, telegram_message_id: str | int | None = None) -> None:
    log.warning(
        "virus_bridge_send_result: ticket_id=%s status=%s reason=%s telegram_message_id=%s",
        ticket_id,
        status,
        reason or "-",
        telegram_message_id if telegram_message_id is not None else "-",
    )


def _send_trade_ticket(trade_candidate: dict, cfg: dict) -> bool:
    decision = str(trade_candidate.get("decision") or "").upper()
    operational_ready = bool(trade_candidate.get("operational_is_actionable", True))
    state = _load_state(cfg)
    ticket_id = str(trade_candidate.get("ticket_id") or "")
    dedupe_hit = ticket_id in set(state.get("sent_ticket_ids", []))

    tg_cfg = cfg.get("notify", {}).get("telegram", {})
    token = os.getenv(tg_cfg.get("bot_token_env", "TG_BOT_TOKEN"))
    chat_id = os.getenv(tg_cfg.get("chat_id_env", "TG_CHAT_ID"))
    text = render_ticket_text(trade_candidate)
    quiet_hours = quiet_hours_active(cfg)
    allowed, reason = allow_notification(text, cfg) if text else (False, None)
    sendable_decision = decision in {"APPROVED", "REDUCED", "PENDING_MARKET_OPEN"}
    allowed_to_send = bool(sendable_decision and not dedupe_hit and token and chat_id and text and allowed)
    _log_send_attempt(ticket_id, decision or "-", str(chat_id or ""), quiet_hours, dedupe_hit, allowed_to_send)

    if not sendable_decision:
        _log_send_result(ticket_id, "suppressed", "decision_not_sendable")
        return False
    if dedupe_hit:
        _log_send_result(ticket_id, "suppressed", "dedupe_hit")
        return False
    if not text:
        _log_send_result(ticket_id, "suppressed", "empty_text")
        return False
    if not token:
        _log_send_result(ticket_id, "suppressed", "missing_token")
        return False
    if not chat_id:
        _log_send_result(ticket_id, "suppressed", "missing_chat_id")
        return False
    if not allowed:
        _log_send_result(ticket_id, "suppressed", "quiet_hours" if reason == "quiet_hours_active" else "quiet_hours")
        return False

    if not operational_ready:
        send_result = send_message_result(token, chat_id, text, cfg, keyboard_rows=None)
        if not send_result.get("ok"):
            _log_send_result(ticket_id, "error", str(send_result.get("reason") or "send_error"), send_result.get("message_id"))
            return False
        state.setdefault("sent_ticket_ids", []).append(ticket_id)
        _save_state(cfg, state)
        _log_send_result(ticket_id, "sent", "informational_only", send_result.get("message_id"))
        return True

    _ensure_ticket_open(ticket_id, cfg, trade_candidate)
    set_active_ticket(chat_id, ticket_id, cfg)
    _, action = render_ticket_command_text(ticket_id, cfg)
    keyboard_rows = action.get("reply_keyboard") if isinstance(action, dict) else None
    send_result = send_message_result(token, chat_id, text, cfg, keyboard_rows=keyboard_rows)
    if not send_result.get("ok"):
        _log_send_result(ticket_id, "error", str(send_result.get("reason") or "send_error"), send_result.get("message_id"))
        return False

    state.setdefault("sent_ticket_ids", []).append(ticket_id)
    _save_state(cfg, state)
    record_ticket_lifecycle_event(
        "TRADE_TICKET_SENT",
        {
            "ticket_id": ticket_id,
            "source_proposal_id": trade_candidate.get("source_proposal_id"),
            "asset": trade_candidate.get("asset"),
            "decision": trade_candidate.get("decision"),
            "status": "SENT",
            "timestamp": trade_candidate.get("timestamp"),
        },
        cfg,
    )
    _log_send_result(ticket_id, "sent", str(send_result.get("reason") or "ok"), send_result.get("message_id"))
    return True


def run(cfg: dict | None = None) -> dict:
    active_cfg = cfg or load_config()
    proposals = load_pending_proposals(active_cfg)
    deduped = dedupe_pending_proposals(proposals)
    deduped_ids = {str(row.get("proposal_id") or "") for row in deduped}

    for proposal in proposals:
        proposal_id = str(proposal.get("proposal_id") or "")
        if proposal_id and proposal_id not in deduped_ids:
            mark_proposal_consumed(proposal_id, active_cfg)

    summary = {
        "loaded": len(proposals),
        "deduped": len(deduped),
        "approved": 0,
        "reduced": 0,
        "pending_market_open": 0,
        "rejected": 0,
    }
    written_paths: list[str] = []

    for idx, proposal in enumerate(deduped, start=1):
        risk_eval = evaluate_proposal(proposal, active_cfg)
        quote = proposal.get("quote") if isinstance(proposal.get("quote"), dict) else {}
        enriched_proposal = {
            **proposal,
            "_ticket_seq": idx,
            "entry_hint": derive_entry_hint(proposal, quote, active_cfg),
            "stop_hint": derive_stop_hint(proposal, quote, active_cfg),
        }
        trade_candidate = build_trade_candidate(enriched_proposal, risk_eval, active_cfg)
        written_paths.append(write_trade_candidate(trade_candidate, active_cfg))
        init_lifecycle(trade_candidate, active_cfg)
        record_ticket_lifecycle_event(
            "TRADE_CANDIDATE_CREATED",
            {
                "ticket_id": trade_candidate.get("ticket_id"),
                "source_proposal_id": trade_candidate.get("source_proposal_id"),
                "asset": trade_candidate.get("asset"),
                "decision": trade_candidate.get("decision"),
                "status": "CREATED",
                "timestamp": trade_candidate.get("timestamp"),
            },
            active_cfg,
        )
        _send_trade_ticket(trade_candidate, active_cfg)
        mark_proposal_consumed(str(proposal.get("proposal_id") or ""), active_cfg)

        decision = str(trade_candidate.get("decision") or "").lower()
        if decision in summary:
            summary[decision] += 1

    line = (
        "virus_bridge: "
        f"loaded={summary['loaded']} deduped={summary['deduped']} "
        f"approved={summary['approved']} reduced={summary['reduced']} "
        f"pending_market_open={summary['pending_market_open']} rejected={summary['rejected']}"
    )
    return {"status": "ok", "summary": summary, "written_paths": written_paths, "log_line": line}


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Virus bridge runner")
    parser.add_argument("command", choices=["run"])
    args = parser.parse_args()
    if args.command == "run":
        result = run()
        print(result["log_line"])


if __name__ == "__main__":
    _cli()
