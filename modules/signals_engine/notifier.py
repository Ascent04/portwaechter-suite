from __future__ import annotations

import os
from pathlib import Path
from urllib import parse, request

from modules.common.state import load_state, mark_sent, save_state, should_send
from modules.common.utils import now_iso_tz


def _state_path(cfg: dict) -> Path:
    root_dir = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    return root_dir / "data" / "state" / "notify_state.json"


def _send_telegram(text: str, cfg: dict) -> bool:
    tg_cfg = cfg.get("notify", {}).get("telegram", {})
    if not tg_cfg.get("enabled", False):
        return False

    token = os.getenv(tg_cfg.get("bot_token_env", "TG_BOT_TOKEN"))
    chat_id = os.getenv(tg_cfg.get("chat_id_env", "TG_CHAT_ID"))
    if not token or not chat_id:
        return False

    payload = parse.urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
    req = request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=payload, method="POST")
    try:
        with request.urlopen(req, timeout=10):
            return True
    except Exception:
        return False


def send_signals(signals: list[dict], cfg: dict) -> None:
    if not signals:
        return

    tz = cfg.get("app", {}).get("timezone", "Europe/Berlin")
    now_iso = now_iso_tz(tz)
    cooldown = int(cfg.get("notify", {}).get("telegram", {}).get("cooldown_min", 30))

    state_path = _state_path(cfg)
    state = load_state(state_path)

    pending: list[tuple[str, dict]] = []
    for signal in signals:
        key = f"signal:{signal.get('id')}:{signal.get('key')}"
        if should_send(key, now_iso, cooldown, state):
            pending.append((key, signal))

    if not pending:
        return

    lines = ["PortWächter Signals"]
    for _, signal in pending[:8]:
        lines.append(f"- {signal.get('message')}")
        if signal.get("link"):
            lines.append(f"  {signal.get('link')}")

    if not _send_telegram("\n".join(lines), cfg):
        return

    for key, _ in pending:
        mark_sent(key, now_iso, state)
    save_state(state_path, state)
