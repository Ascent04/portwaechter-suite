from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
from urllib import error, parse, request

from modules.common.config import load_config
from modules.common.utils import append_jsonl, now_iso_tz, read_json, write_json
from modules.telegram_commands.handlers import (
    alerts_show_text,
    handle_alerts_set,
    handle_alerts_thresholds_market,
    help_text,
    status_text,
    testalert_text,
)

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
        return {"last_update_id": 0}
    data = read_json(path)
    return data if isinstance(data, dict) else {"last_update_id": 0}


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
        text in {"/status", "/status verbose", "/alerts", "/alerts show", "/help"}
        or text.startswith("/alerts set ")
        or text.startswith("/alerts thresholds market ")
        or text.startswith("/testalert ")
        or text in {"/alerts quiet", "/alerts normal", "/alerts active", "/alerts off", "/alerts balanced"}
    )


def parse_commands(updates: list[dict], allowed_chat_ids: set[str]) -> list[dict]:
    out: list[dict] = []
    for upd in updates:
        msg = upd.get("message") or {}
        chat_id = str((msg.get("chat") or {}).get("id") or "")
        text = str(msg.get("text") or "").strip()
        row = {"update_id": upd.get("update_id"), "chat_id": chat_id, "text": text, "ts": now_iso_tz()}
        if chat_id not in allowed_chat_ids:
            row["status"] = "ignored_chat"
        elif _is_supported(text):
            row["status"] = "accepted"
        else:
            row["status"] = "ignored_command"
        out.append(row)
    return out


def write_inbox(items: list[dict], cfg: dict) -> None:
    path = _resolve_path(cfg, "inbox_jsonl")
    for item in items:
        append_jsonl(path, item)


def handle_command(cmd: dict, cfg: dict) -> tuple[str, dict]:
    text = str(cmd.get("text") or "")
    if text == "/status":
        return status_text(cfg, verbose=False), {"action": "status"}
    if text == "/status verbose":
        return status_text(cfg, verbose=True), {"action": "status_verbose"}
    if text in {"/alerts", "/alerts show"}:
        return alerts_show_text(cfg), {"action": "alerts_show"}

    if text in {"/alerts quiet", "/alerts normal", "/alerts active", "/alerts off", "/alerts balanced"}:
        profile = text.split(" ", 1)[1]
        return handle_alerts_set(profile, cfg), {"action": "alerts_set", "profile": profile}

    if text.startswith("/alerts set "):
        profile = text.split(None, 2)[2].strip().lower()
        return handle_alerts_set(profile, cfg), {"action": "alerts_set", "profile": profile}

    if text.startswith("/alerts thresholds market "):
        args = text.split()[3:]
        return handle_alerts_thresholds_market(args, cfg), {"action": "alerts_thresholds_market", "args": args}

    if text.startswith("/testalert "):
        module_name = text.split(None, 1)[1].strip().lower()
        return testalert_text(module_name), {"action": "testalert", "module": module_name}

    return help_text(), {"action": "help"}


def _reply_keyboard(cfg: dict) -> dict | None:
    tcfg = cfg.get("telegram_commands", {})
    kcfg = tcfg.get("keyboard", {}) if isinstance(tcfg.get("keyboard"), dict) else {}
    if not kcfg.get("enabled", True):
        return None

    raw_rows = kcfg.get(
        "rows",
        [
            ["/status", "/alerts show"],
            ["/alerts set active", "/alerts set normal"],
            ["/alerts set quiet", "/alerts set off"],
            ["/status verbose", "/testalert market"],
        ],
    )
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


def send_message(token: str, chat_id: str, text: str, cfg: dict) -> bool:
    payload_obj = {"chat_id": chat_id, "text": text[:2000]}
    keyboard = _reply_keyboard(cfg)
    if keyboard:
        payload_obj["reply_markup"] = json.dumps(keyboard, ensure_ascii=False)

    payload = parse.urlencode(payload_obj).encode("utf-8")
    req = request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=payload, method="POST")
    try:
        with request.urlopen(req, timeout=15):
            return True
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore") if exc.fp else ""
        log.warning("telegram_send_failed status=%s body=%s", exc.code, body[:240])
        return False
    except Exception as exc:
        log.warning("telegram_send_failed error=%s", exc)
        return False


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
        if cmd.get("status") != "accepted":
            continue
        response, action = handle_command(cmd, cfg)
        sent = send_message(token, str(cmd.get("chat_id")), response, cfg)
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
