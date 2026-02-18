from __future__ import annotations

import os
import logging
from urllib import parse, request
from urllib.error import HTTPError

log = logging.getLogger(__name__)

def _send(text: str, cfg: dict) -> bool:
    tg_cfg = cfg.get("notify", {}).get("telegram", {})
    if not tg_cfg.get("enabled", False):
        return False

    token = os.getenv(tg_cfg.get("bot_token_env", "TG_BOT_TOKEN"))
    chat_id = os.getenv(tg_cfg.get("chat_id_env", "TG_CHAT_ID"))
    if not token or not chat_id:
        return False

    payload = parse.urlencode({"chat_id": chat_id, "text": text[:3400]}).encode("utf-8")
    req = request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=payload, method="POST")
    try:
        with request.urlopen(req, timeout=12):
            return True
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore") if exc.fp else ""
        log.warning("telegram_send_failed status=%s body=%s", exc.code, body[:240])
        return False
    except Exception as exc:
        log.warning("telegram_send_failed error=%s", exc)
        return False


def send_performance_text(text: str, cfg: dict) -> bool:
    return _send(text, cfg)


def send_telegram_performance_summary(report: dict, cfg: dict) -> bool:
    h1 = (report.get("by_horizon") or {}).get("1d", {})
    h3 = (report.get("by_horizon") or {}).get("3d", {})
    lines = [
        f"PortWächter Performance {report.get('week')}",
        f"Events: {(report.get('summary') or {}).get('events_total', 0)}",
        f"1d n={h1.get('n', 0)} win={h1.get('win_rate', 0)} exp={h1.get('expectancy', 0)} conf={h1.get('expectancy_confidence', 'low')}",
        f"3d n={h3.get('n', 0)} win={h3.get('win_rate', 0)} exp={h3.get('expectancy', 0)} conf={h3.get('expectancy_confidence', 'low')}",
    ]
    return _send("\n".join(lines), cfg)
