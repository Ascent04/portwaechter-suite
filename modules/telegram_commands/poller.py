from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
from urllib import error, parse, request

from modules.common.config import load_config
from modules.common.utils import append_jsonl, now_iso_tz, read_json, write_json
from modules.integration.virus_inbox import load_pending_signal_proposals
from modules.organism.report_render import render_organism_text
from modules.telegram_commands.pdf_upload import extract_pdf_meta, save_pdf_to_inbox
from modules.telegram_commands.dashboard import render_warning_summary
from modules.telegram_commands.ui import (
    build_main_menu,
    build_settings_menu,
    build_status_menu,
    build_ticket_list_menu,
    main_menu_text,
    route_button,
    settings_menu_text,
    status_menu_text,
    supported_ui_labels,
    ticket_list_menu_text,
)
from modules.telegram_commands.handlers import (
    alerts_show_text,
    handle_alerts_set,
    handle_alerts_thresholds_market,
    portfolio_text,
    status_text,
    testalert_text,
)
from modules.v2.telegram.help import (
    explain_candidate,
    load_latest_recommendations,
    render_help_text,
    render_meaning_text,
    render_top_text,
)
from modules.v2.telegram.copy import candidate_name, classification_label, format_score, market_label
from modules.virus_bridge.execution_flow import (
    handle_pending_ticket_input,
    handle_ticket_action,
    render_ticket_command_text,
    render_tickets_text,
    set_active_ticket,
)
from modules.virus_bridge.execution_performance import render_execution_summary
from modules.virus_bridge.trade_candidate import load_recent_trade_candidates

log = logging.getLogger(__name__)


def _resolve_path(cfg: dict, key: str) -> Path:
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    value = str(cfg.get("telegram_commands", {}).get(key, ""))
    date_tag = now_iso_tz(cfg.get("app", {}).get("timezone", "Europe/Berlin"))[:10].replace("-", "")
    value = value.replace("YYYYMMDD", date_tag)
    p = Path(value)
    return p if p.is_absolute() else root / p


def _get_token_chat(cfg: dict) -> tuple[str | None, set[str]]:
    tg = cfg.get("notify", {}).get("telegram", {})
    token = os.getenv(tg.get("bot_token_env", "TG_BOT_TOKEN"))
    env_key = cfg.get("telegram_commands", {}).get("allowed_chat_ids_env", "TG_CHAT_ID")
    raw = os.getenv(env_key, "")
    allowed = {item.strip() for item in raw.split(",") if item.strip()}
    return token, allowed


def _state_path(cfg: dict) -> Path:
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    raw = str(cfg.get("telegram_commands", {}).get("state_file", "data/telegram/command_state.json"))
    p = Path(raw)
    return p if p.is_absolute() else root / p


def _load_state(cfg: dict) -> dict:
    path = _state_path(cfg)
    if not path.exists():
        return {"last_update_id": 0, "ui_context_by_chat": {}}
    data = read_json(path)
    if not isinstance(data, dict):
        return {"last_update_id": 0, "ui_context_by_chat": {}}
    data.setdefault("ui_context_by_chat", {})
    return data


def _save_state(cfg: dict, state: dict) -> None:
    write_json(_state_path(cfg), state)


def fetch_updates(token: str, offset: int) -> list[dict]:
    req = request.Request(f"https://api.telegram.org/bot{token}/getUpdates?timeout=0&offset={offset}", method="GET")
    try:
        with request.urlopen(req, timeout=15) as res:
            payload = json.loads(res.read().decode("utf-8"))
    except Exception:
        return []
    return payload.get("result", []) if payload.get("ok") else []


def _is_supported(text: str) -> bool:
    return (
        text in {"/status", "/status verbose", "/portfolio", "/alerts", "/alerts show", "/help", "/meaning", "/top", "/why", "/proposals", "/tickets", "/ticket", "/execution", "/organism"}
        or text in supported_ui_labels()
        or text.startswith("/alerts set ")
        or text.startswith("/alerts thresholds market ")
        or text.startswith("/testalert ")
        or text.startswith("/why ")
        or text.startswith("/ticket ")
        or any(text.startswith(prefix) for prefix in ("BOUGHT:", "NOT_BOUGHT:", "LATER:", "DETAILS:"))
        or text in {"/alerts quiet", "/alerts normal", "/alerts active", "/alerts off", "/alerts balanced"}
    )


def _normalize_command_text(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return raw
    parts = raw.split()
    head = parts[0]
    if head.startswith("/") and "@" in head:
        head = head.split("@", 1)[0]
    return " ".join([head] + parts[1:])


def _ui_context(state: dict, chat_id: str) -> str:
    ui_context_by_chat = state.get("ui_context_by_chat", {})
    if not isinstance(ui_context_by_chat, dict):
        return "main_menu"
    return str(ui_context_by_chat.get(str(chat_id)) or "main_menu")


def _set_ui_context(state: dict, chat_id: str, context: str) -> None:
    ui_context_by_chat = state.setdefault("ui_context_by_chat", {})
    if isinstance(ui_context_by_chat, dict):
        ui_context_by_chat[str(chat_id)] = context


def _is_command_text(text: str) -> bool:
    return str(text or "").strip().startswith("/")


def parse_commands(updates: list[dict], allowed_chat_ids: set[str]) -> list[dict]:
    out: list[dict] = []
    for upd in updates:
        msg = upd.get("message") or {}
        chat_id = str((msg.get("chat") or {}).get("id") or "")
        text = str(msg.get("text") or "").strip()
        normalized = _normalize_command_text(text)
        pdf_meta = extract_pdf_meta(msg)
        row = {
            "update_id": upd.get("update_id"),
            "chat_id": chat_id,
            "text": text,
            "normalized_text": normalized,
            "ts": now_iso_tz(),
        }
        if pdf_meta:
            row.update(pdf_meta)
        if chat_id not in allowed_chat_ids:
            row["status"] = "ignored_chat"
        elif pdf_meta:
            row["status"] = "accepted_pdf"
        elif _is_supported(normalized):
            row["status"] = "accepted"
        else:
            row["status"] = "ignored_command"
        out.append(row)
    return out


def _wrong_chat_text() -> str:
    return "Bitte den freigegebenen Gruppenchat verwenden."


def _pdf_ingest_text(result: dict) -> str:
    if result.get("ok"):
        path = str(result.get("path") or "")
        return f"PDF empfangen und gespeichert: {Path(path).name}\nPortfolio-Ingest startet automatisch."
    return "PDF konnte nicht verarbeitet werden."


def _proposals_text(cfg: dict) -> str:
    proposals = load_pending_signal_proposals(cfg)
    candidates = load_recent_trade_candidates(cfg, limit=5)

    lines = ["Offene Kaufideen:"]
    if not proposals:
        lines.append("Keine offenen Kaufideen in der Uebergabe an Virus Fund.")
    else:
        for idx, proposal in enumerate(proposals[:10], start=1):
            asset = proposal.get("asset") or {}
            name = candidate_name(asset)
            score = format_score(proposal.get("score"))
            signal_strength = str(proposal.get("signal_strength") or "spekulativ")
            lines.append(f"{idx}. {name} | Score {score} | Signalstaerke {signal_strength}")

    lines.extend(["", "Letzte Trade-Kandidaten:"])
    if not candidates:
        lines.append("Noch keine Trade-Kandidaten vorhanden.")
    else:
        for idx, candidate in enumerate(candidates, start=1):
            asset = candidate.get("asset") or {}
            name = candidate_name(asset)
            decision = str(candidate.get("decision") or "").upper()
            actionable = bool(candidate.get("operational_is_actionable", True))
            missing = [str(value).strip() for value in (candidate.get("operational_missing_labels") or []) if str(value).strip()]
            if not actionable:
                state_label = "UNVOLLSTAENDIG"
                if missing:
                    detail = "fehlt: " + ", ".join(missing[:2])
                else:
                    detail = "operative Angaben fehlen"
            elif decision == "PENDING_MARKET_OPEN":
                state_label = "MARKT GESCHLOSSEN"
                detail = (
                    f"{int(float(candidate.get('size_min_eur', 0) or 0))}-"
                    f"{int(float(candidate.get('size_max_eur', 0) or 0))} EUR"
                )
            elif decision == "REDUCED":
                state_label = "OPERATIV REDUZIERT"
                detail = f"{int(float(candidate.get('suggested_eur', 0) or 0))} EUR"
            elif decision == "APPROVED":
                state_label = "OPERATIV"
                detail = (
                    f"{int(float(candidate.get('size_min_eur', 0) or 0))}-"
                    f"{int(float(candidate.get('size_max_eur', 0) or 0))} EUR"
                )
            else:
                state_label = "ABGELEHNT"
                reasons = [str(value).strip() for value in (candidate.get("reasons") or []) if str(value).strip()]
                detail = reasons[0] if reasons else "nicht weiter verfolgen"
            lines.append(f"{idx}. {name} | {state_label} | {detail}")
    return "\n".join(lines)[:1800]


def _recommendation_bucket_text(label: str, latest_recommendations: list[dict], cfg: dict) -> str:
    rows = [row for row in latest_recommendations if classification_label(row.get("classification"), row) == label]
    rows.sort(key=lambda row: float(format_score((row.get("defense_score") or {}).get("defense_score") if label == "RISIKO REDUZIEREN" else (row.get("opportunity_score") or {}).get("total_score"))), reverse=True)
    if not rows:
        return f"{label}\n\nAktuell keine klaren Titel."
    lines = [label, ""]
    for row in rows[:5]:
        score_value = (row.get("defense_score") or {}).get("defense_score") if label == "RISIKO REDUZIEREN" else (row.get("opportunity_score") or {}).get("total_score")
        lines.append(f"- {candidate_name(row)} ({format_score(score_value)})")
    regime = next((market_label(row.get("regime")) for row in rows if row.get("regime")), "neutral")
    lines.extend(["", f"Marktlage: {regime}"])
    return "\n".join(lines)[:1800]


def _settings_quiet_hours_text(cfg: dict) -> str:
    notifications = cfg.get("notifications", {})
    quiet = notifications.get("quiet_hours", {}) if isinstance(notifications.get("quiet_hours"), dict) else {}
    enabled = "aktiv" if quiet.get("enabled", True) else "inaktiv"
    start = str(quiet.get("start", "22:00"))
    end = str(quiet.get("end", "08:30"))
    timezone = str(quiet.get("timezone", cfg.get("app", {}).get("timezone", "Europe/Berlin")))
    return f"Ruhezeiten\n\nStatus: {enabled}\nFenster: {start} bis {end}\nZeitzone: {timezone}"


def _settings_premarket_text(cfg: dict) -> str:
    return "Voreröffnung\n\nDeutschland: 08:45\nUSA: 15:15\n\nDie Vorbereitungsmeldungen kommen vor Handelsbeginn."


def _markets_text(latest_recommendations: list[dict], cfg: dict) -> str:
    regime = market_label(next((row.get("regime") for row in latest_recommendations if row.get("regime")), "neutral"))
    return f"Märkte\n\nAktuelle Marktlage: {regime}\n\nDeutschland und USA werden getrennt vorbereitet."


def _data_sources_text(cfg: dict) -> str:
    return (
        "Datenquellen\n\n"
        "Portfolio: aktiv\n"
        "Marktdaten: aktiv\n"
        "Nachrichten: aktiv\n"
        "Telegram: aktiv\n\n"
        "Details stehen im Systemstatus."
    )


def write_inbox(items: list[dict], cfg: dict) -> None:
    path = _resolve_path(cfg, "inbox_jsonl")
    for item in items:
        append_jsonl(path, item)


def handle_command(cmd: dict, cfg: dict, state: dict | None = None) -> tuple[str, dict]:
    active_state = state if isinstance(state, dict) else {"last_update_id": 0, "ui_context_by_chat": {}}
    text = str(cmd.get("normalized_text") or cmd.get("text") or "")
    chat_id = str(cmd.get("chat_id") or "")
    current_ui_context = _ui_context(active_state, chat_id)
    latest_recommendations = load_latest_recommendations(cfg)
    ticket_action = handle_ticket_action(text, chat_id, cfg, ui_context=current_ui_context)
    if ticket_action:
        return ticket_action

    button_route = route_button(text, current_ui_context)
    if button_route == "ui:main":
        return main_menu_text(cfg), {"action": "ui_main", "reply_keyboard": build_main_menu(), "ui_context": "main_menu"}
    if button_route == "ui:status_menu":
        return status_menu_text(cfg), {"action": "ui_status_menu", "reply_keyboard": build_status_menu(), "ui_context": "status_menu"}
    if button_route == "ui:settings_menu":
        return settings_menu_text(), {"action": "ui_settings_menu", "reply_keyboard": build_settings_menu(), "ui_context": "settings_menu"}
    if button_route == "ui:tickets_menu":
        return ticket_list_menu_text(), {"action": "ui_tickets_menu", "reply_keyboard": build_ticket_list_menu(), "ui_context": "tickets_menu"}
    if button_route == "ui:warnings":
        return render_warning_summary(cfg), {"action": "ui_warnings", "reply_keyboard": build_status_menu(), "ui_context": "status_menu"}
    if button_route == "ui:buy":
        return _recommendation_bucket_text("KAUFEN PRUEFEN", latest_recommendations, cfg), {"action": "ui_buy", "reply_keyboard": build_main_menu(), "ui_context": "main_menu"}
    if button_route == "ui:sell":
        return _recommendation_bucket_text("VERKAUFEN PRUEFEN", latest_recommendations, cfg), {"action": "ui_sell", "reply_keyboard": build_main_menu(), "ui_context": "main_menu"}
    if button_route == "ui:risk":
        return _recommendation_bucket_text("RISIKO REDUZIEREN", latest_recommendations, cfg), {"action": "ui_risk", "reply_keyboard": build_main_menu(), "ui_context": "main_menu"}
    if button_route == "ui:hold":
        return _recommendation_bucket_text("HALTEN", latest_recommendations, cfg), {"action": "ui_hold", "reply_keyboard": build_main_menu(), "ui_context": "main_menu"}
    if button_route == "ui:tickets_open":
        return render_tickets_text(cfg, status_filter="OPEN"), {"action": "ui_tickets_open", "reply_keyboard": build_ticket_list_menu(), "ui_context": "tickets_menu"}
    if button_route == "ui:tickets_partial":
        return render_tickets_text(cfg, status_filter="PARTIALLY_CLOSED"), {"action": "ui_tickets_partial", "reply_keyboard": build_ticket_list_menu(), "ui_context": "tickets_menu"}
    if button_route == "ui:tickets_closed":
        return render_tickets_text(cfg, status_filter="CLOSED"), {"action": "ui_tickets_closed", "reply_keyboard": build_ticket_list_menu(), "ui_context": "tickets_menu"}
    if button_route == "ui:tickets_executed":
        return render_tickets_text(cfg, status_filter="EXECUTED"), {"action": "ui_tickets_executed", "reply_keyboard": build_ticket_list_menu(), "ui_context": "tickets_menu"}
    if button_route == "ui:tickets_rejected":
        return render_tickets_text(cfg, status_filter="REJECTED"), {"action": "ui_tickets_rejected", "reply_keyboard": build_ticket_list_menu(), "ui_context": "tickets_menu"}
    if button_route == "ui:tickets_deferred":
        return render_tickets_text(cfg, status_filter="DEFERRED"), {"action": "ui_tickets_deferred", "reply_keyboard": build_ticket_list_menu(), "ui_context": "tickets_menu"}
    if button_route == "ui:weekly_report":
        return "Wochenreport\n\nDer aktuelle Wochenreport ist im Statusbereich hinterlegt.", {"action": "ui_weekly_report", "reply_keyboard": build_status_menu(), "ui_context": "status_menu"}
    if button_route == "ui:data_sources":
        return _data_sources_text(cfg), {"action": "ui_data_sources", "reply_keyboard": build_status_menu(), "ui_context": "status_menu"}
    if button_route == "ui:quiet_hours":
        return _settings_quiet_hours_text(cfg), {"action": "ui_quiet_hours", "reply_keyboard": build_settings_menu(), "ui_context": "settings_menu"}
    if button_route == "ui:premarket":
        return _settings_premarket_text(cfg), {"action": "ui_premarket", "reply_keyboard": build_settings_menu(), "ui_context": "settings_menu"}
    if button_route == "ui:markets":
        return _markets_text(latest_recommendations, cfg), {"action": "ui_markets", "reply_keyboard": build_settings_menu(), "ui_context": "settings_menu"}
    if button_route == "ui:language":
        return "Sprache\n\nDeutsch ist aktiv.", {"action": "ui_language", "reply_keyboard": build_settings_menu(), "ui_context": "settings_menu"}
    if button_route and button_route.startswith("/"):
        text = button_route

    if text == "/status":
        return status_text(cfg, verbose=False), {"action": "status", "reply_keyboard": build_status_menu(), "ui_context": "status_menu"}
    if text == "/status verbose":
        return status_text(cfg, verbose=True), {"action": "status_verbose", "reply_keyboard": build_status_menu(), "ui_context": "status_menu"}
    if text == "/portfolio":
        return portfolio_text(cfg), {"action": "portfolio", "reply_keyboard": build_status_menu(), "ui_context": "status_menu"}
    if text in {"/alerts", "/alerts show"}:
        return alerts_show_text(cfg), {"action": "alerts_show", "reply_keyboard": build_status_menu(), "ui_context": "status_menu"}
    if text == "/help":
        return render_help_text(latest_recommendations, cfg), {"action": "help", "reply_keyboard": build_main_menu(), "ui_context": "main_menu"}
    if text == "/meaning":
        return render_meaning_text(latest_recommendations, cfg), {"action": "meaning", "reply_keyboard": build_main_menu(), "ui_context": "main_menu"}
    if text == "/top":
        return render_top_text(latest_recommendations, cfg), {"action": "top", "reply_keyboard": build_main_menu(), "ui_context": "main_menu"}
    if text == "/proposals":
        return _proposals_text(cfg), {"action": "proposals", "reply_keyboard": build_main_menu(), "ui_context": "main_menu"}
    if text == "/execution":
        return render_execution_summary(cfg), {"action": "execution", "reply_keyboard": build_status_menu(), "ui_context": "status_menu"}
    if text == "/organism":
        return render_organism_text(cfg), {"action": "organism", "reply_keyboard": build_status_menu(), "ui_context": "status_menu"}
    if text == "/tickets":
        return render_tickets_text(cfg), {"action": "tickets", "reply_keyboard": build_ticket_list_menu(), "ui_context": "tickets_menu"}
    if text == "/ticket":
        return "Bitte: /ticket <ticket_id>", {"action": "ticket_usage"}
    if text.startswith("/ticket "):
        ticket_id = text.split(None, 1)[1].strip()
        set_active_ticket(chat_id, ticket_id, cfg)
        return render_ticket_command_text(ticket_id, cfg)
    if text == "/why":
        return "Bitte: /why <symbol|isin>", {"action": "why_usage"}
    if text.startswith("/why "):
        query = text.split(None, 1)[1].strip()
        return explain_candidate(query, latest_recommendations), {"action": "why", "query": query, "reply_keyboard": build_main_menu(), "ui_context": "main_menu"}

    if text in {"/alerts quiet", "/alerts normal", "/alerts active", "/alerts off", "/alerts balanced"}:
        profile = text.split(" ", 1)[1]
        return handle_alerts_set(profile, cfg), {"action": "alerts_set", "profile": profile, "reply_keyboard": build_settings_menu(), "ui_context": "settings_menu"}

    if text.startswith("/alerts set "):
        profile = text.split(None, 2)[2].strip().lower()
        return handle_alerts_set(profile, cfg), {"action": "alerts_set", "profile": profile, "reply_keyboard": build_settings_menu(), "ui_context": "settings_menu"}

    if text.startswith("/alerts thresholds market "):
        args = text.split()[3:]
        return handle_alerts_thresholds_market(args, cfg), {"action": "alerts_thresholds_market", "args": args, "reply_keyboard": build_settings_menu(), "ui_context": "settings_menu"}

    if text.startswith("/testalert "):
        module_name = text.split(None, 1)[1].strip().lower()
        return testalert_text(module_name), {"action": "testalert", "module": module_name, "reply_keyboard": build_status_menu(), "ui_context": "status_menu"}

    return main_menu_text(cfg), {"action": "ui_main", "reply_keyboard": build_main_menu(), "ui_context": "main_menu"}


def _reply_keyboard(cfg: dict, rows_override: list[list[str]] | None = None) -> dict | None:
    tcfg = cfg.get("telegram_commands", {})
    kcfg = tcfg.get("keyboard", {}) if isinstance(tcfg.get("keyboard"), dict) else {}
    if not kcfg.get("enabled", True) and rows_override is None:
        return None

    raw_rows = rows_override or build_main_menu()
    rows: list[list[str]] = []
    if isinstance(raw_rows, list):
        for row in raw_rows:
            if not isinstance(row, list):
                continue
            cleaned = [str(btn).strip() for btn in row if str(btn).strip()]
            if cleaned:
                rows.append(cleaned)
    if not rows:
        return None

    return {
        "keyboard": rows,
        "resize_keyboard": bool(kcfg.get("resize", True)),
        "one_time_keyboard": False,
        "is_persistent": bool(kcfg.get("persistent", True)),
        "input_field_placeholder": str(kcfg.get("placeholder", "PortWächter Befehle"))[:64],
    }


def send_message_result(token: str, chat_id: str, text: str, cfg: dict, keyboard_rows: list[list[str]] | None = None) -> dict:
    payload_obj = {"chat_id": chat_id, "text": text[:2000]}
    keyboard = _reply_keyboard(cfg, rows_override=keyboard_rows)
    if keyboard:
        payload_obj["reply_markup"] = json.dumps(keyboard, ensure_ascii=False)

    payload = parse.urlencode(payload_obj).encode("utf-8")
    req = request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=payload, method="POST")
    try:
        with request.urlopen(req, timeout=15) as response:
            body = response.read().decode("utf-8", errors="ignore")
        payload = json.loads(body) if body else {}
        result = payload.get("result") if isinstance(payload, dict) else {}
        message_id = result.get("message_id") if isinstance(result, dict) else None
        ok = bool(payload.get("ok")) if isinstance(payload, dict) else False
        if ok:
            return {"ok": True, "message_id": message_id, "reason": "ok"}
        return {"ok": False, "message_id": message_id, "reason": "telegram_not_ok"}
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore") if exc.fp else ""
        log.warning("telegram_send_failed status=%s body=%s", exc.code, body[:240])
        return {"ok": False, "message_id": None, "reason": f"http_{exc.code}"}
    except Exception as exc:
        log.warning("telegram_send_failed error=%s", exc)
        return {"ok": False, "message_id": None, "reason": str(exc)}


def send_message(token: str, chat_id: str, text: str, cfg: dict, keyboard_rows: list[list[str]] | None = None) -> bool:
    return bool(send_message_result(token, chat_id, text, cfg, keyboard_rows=keyboard_rows).get("ok"))


def run(cfg: dict) -> None:
    if not cfg.get("telegram_commands", {}).get("enabled", True):
        return

    token, allowed = _get_token_chat(cfg)
    if not token or not allowed:
        return

    state = _load_state(cfg)
    updates = fetch_updates(token, int(state.get("last_update_id", 0)) + 1)
    if not updates:
        return

    parsed = parse_commands(updates, allowed)
    write_inbox(parsed, cfg)

    actions_path = _resolve_path(cfg, "actions_jsonl")
    for cmd in parsed:
        status = str(cmd.get("status") or "")
        response = ""
        action: dict = {}
        keyboard_rows = None
        if status == "accepted":
            response, action = handle_command(cmd, cfg, state)
            keyboard_rows = action.get("reply_keyboard") if isinstance(action, dict) else None
            context = str(action.get("ui_context") or "").strip() if isinstance(action, dict) else ""
            if context:
                _set_ui_context(state, str(cmd.get("chat_id") or ""), context)
        elif status == "accepted_pdf":
            result = save_pdf_to_inbox(
                token,
                cfg,
                str(cmd.get("file_id") or ""),
                str(cmd.get("file_name") or "upload.pdf"),
                cmd.get("update_id") or "na",
            )
            response = _pdf_ingest_text(result)
            action = {
                "action": "pdf_upload",
                "ok": bool(result.get("ok")),
                "path": result.get("path"),
                "error": result.get("error"),
            }
        elif status == "ignored_chat" and _is_command_text(cmd.get("normalized_text")):
            response, action = _wrong_chat_text(), {"action": "ignored_chat_notice"}
        elif status == "ignored_command":
            pending = handle_pending_ticket_input(str(cmd.get("text") or ""), str(cmd.get("chat_id") or ""), cfg)
            if pending:
                response, action = pending
            else:
                continue
        else:
            continue
        sent = send_message(token, str(cmd.get("chat_id")), response, cfg, keyboard_rows=keyboard_rows)
        append_jsonl(
            actions_path,
            {
                "ts": now_iso_tz(),
                "update_id": cmd.get("update_id"),
                "chat_id": cmd.get("chat_id"),
                "command": cmd.get("text"),
                "action": action,
                "send_ok": sent,
            },
        )

    state["last_update_id"] = max(int(u.get("update_id", 0)) for u in updates)
    _save_state(cfg, state)


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Telegram command poller")
    parser.add_argument("command", choices=["run"])
    args = parser.parse_args()
    if args.command == "run":
        run(load_config())


if __name__ == "__main__":
    _cli()
