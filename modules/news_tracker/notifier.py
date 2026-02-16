from __future__ import annotations

import os
from urllib import parse, request


def _send_telegram(text: str, cfg: dict) -> None:
    tg_cfg = cfg.get("notify", {}).get("telegram", {})
    if not tg_cfg.get("enabled", False):
        return

    token = os.getenv(tg_cfg.get("bot_token_env", "TG_BOT_TOKEN"))
    chat_id = os.getenv(tg_cfg.get("chat_id_env", "TG_CHAT_ID"))
    if not token or not chat_id:
        return

    payload = parse.urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
    req = request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=payload, method="POST")
    try:
        with request.urlopen(req, timeout=10):
            return
    except Exception:
        return


def send_top_opportunities(top_items: list[dict], cfg: dict) -> None:
    if not top_items:
        return

    lines = ["PortWächter News Top Chancen"]
    for item in top_items[:5]:
        lines.append(f"- {item.get('title_de') or item.get('title')} | {item.get('link')}")

    _send_telegram("\n".join(lines), cfg)
