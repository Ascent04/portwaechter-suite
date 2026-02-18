from __future__ import annotations

import os
import logging
from urllib import parse, request
from urllib.error import HTTPError

log = logging.getLogger(__name__)


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
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore") if exc.fp else ""
        log.warning("telegram_send_failed status=%s body=%s", exc.code, body[:240])
        return
    except Exception as exc:
        log.warning("telegram_send_failed error=%s", exc)
        return


def send_market_alerts(alerts: list[dict], cfg: dict) -> None:
    if not alerts:
        return

    lines = ["PortWächter Marketdata Alerts"]
    for alert in alerts[:5]:
        fallback = f"{alert.get('name')} ({alert.get('isin')}): {alert.get('move_pct')}%"
        lines.append(f"- {alert.get('message') or fallback}")

    _send_telegram("\n".join(lines), cfg)
