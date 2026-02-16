from __future__ import annotations

import hashlib
import os
from pathlib import Path
from urllib import parse, request

from modules.common.state import load_state, mark_sent, save_state, should_send
from modules.common.utils import now_iso_tz


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


def send_radar_top(top_items: list[dict], cfg: dict) -> None:
    if not top_items:
        return

    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    state_path = root / "data" / "state" / "notify_state.json"
    state = load_state(state_path)

    ids = "|".join(str(item.get("id")) for item in top_items[:10])
    digest = hashlib.sha256(ids.encode("utf-8")).hexdigest()[:16]
    key = f"radar:top10:{digest}"

    now_iso = now_iso_tz(cfg.get("app", {}).get("timezone", "Europe/Berlin"))
    cooldown = int(cfg.get("notify", {}).get("telegram", {}).get("cooldown_min", 30))
    if not should_send(key, now_iso, cooldown, state):
        return

    lines = ["PortWächter Radar Top 10"]
    for item in top_items[:5]:
        lines.append(f"- {item.get('title')} ({item.get('score')})")
        if item.get("link"):
            lines.append(f"  {item.get('link')}")

    if not _send_telegram("\n".join(lines), cfg):
        return

    mark_sent(key, now_iso, state)
    save_state(state_path, state)
