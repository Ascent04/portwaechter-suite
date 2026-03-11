from __future__ import annotations

import hashlib
import logging
import os
import re
from pathlib import Path

from modules.common.utils import ensure_dir, now_iso_tz, read_json, write_json
from modules.telegram_commands.poller import send_message_result

log = logging.getLogger(__name__)

STATUS_BEGIN = "<!-- NIGHTLY_HANDOFF_NOTIFY_STATUS:BEGIN -->"
STATUS_END = "<!-- NIGHTLY_HANDOFF_NOTIFY_STATUS:END -->"
REQUIRED_SECTION_FRAGMENTS = (
    "## 1. Was in dieser Nacht umgesetzt wurde",
    "## 3. Welche Tests gelaufen sind",
    "## 4. Welche Ergebnisse gruen sind",
    "## 5. Welche Restrisiken oder offenen Punkte bleiben",
)


def _root_dir(cfg: dict) -> Path:
    return Path(cfg.get("app", {}).get("root_dir", Path.cwd()))


def handoff_path(cfg: dict) -> Path:
    return _root_dir(cfg) / "NIGHTLY_HANDOFF.md"


def _state_path(cfg: dict) -> Path:
    return _root_dir(cfg) / "data" / "state" / "nightly_handoff_notify.json"


def _load_state(cfg: dict) -> dict:
    path = _state_path(cfg)
    if not path.exists():
        return {}
    try:
        data = read_json(path)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _save_state(cfg: dict, state: dict) -> None:
    path = _state_path(cfg)
    ensure_dir(path.parent)
    write_json(path, state)


def _strip_status_block(text: str) -> str:
    pattern = re.compile(rf"{re.escape(STATUS_BEGIN)}.*?{re.escape(STATUS_END)}\n?", re.DOTALL)
    return re.sub(pattern, "", text)


def _handoff_hash(path: Path) -> str:
    text = _strip_status_block(path.read_text(encoding="utf-8")).rstrip() + "\n"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _upsert_status_block(path: Path, *, status: str, detail: str) -> None:
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    base = _strip_status_block(original).rstrip()
    block = (
        f"{STATUS_BEGIN}\n"
        "## Telegram-Abschlussversand\n\n"
        f"- Status: {status}\n"
        f"- Zeit: {now_iso_tz()}\n"
        f"- Detail: {detail}\n"
        f"{STATUS_END}\n"
    )
    content = (base + "\n\n" + block).rstrip() + "\n"
    path.write_text(content, encoding="utf-8")


def _extract_section(text: str, title: str) -> str:
    lines = text.splitlines()
    inside = False
    collected: list[str] = []
    for line in lines:
        if line.strip() == title:
            inside = True
            continue
        if inside and line.startswith("## "):
            break
        if inside:
            collected.append(line)
    return "\n".join(collected).strip()


def _bullet_lines(section: str, limit: int = 3) -> list[str]:
    rows: list[str] = []
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            rows.append(stripped)
        if len(rows) >= limit:
            break
    return rows


def readiness_check(cfg: dict) -> dict:
    path = handoff_path(cfg)
    if not path.exists():
        return {"ready": False, "reason": "handoff_missing", "path": str(path)}
    text = path.read_text(encoding="utf-8")
    missing_sections = [section for section in REQUIRED_SECTION_FRAGMENTS if section not in text]
    if missing_sections:
        return {"ready": False, "reason": "handoff_sections_missing", "path": str(path), "missing_sections": missing_sections}
    if "passed" not in text:
        return {"ready": False, "reason": "handoff_tests_missing", "path": str(path)}
    if "SYSTEM_OVERVIEW.md" not in text and not (_root_dir(cfg) / "SYSTEM_OVERVIEW.md").exists():
        return {"ready": False, "reason": "system_overview_missing", "path": str(path)}
    return {"ready": True, "reason": "ready", "path": str(path), "hash": _handoff_hash(path)}


def build_completion_text(cfg: dict) -> str:
    path = handoff_path(cfg)
    text = _strip_status_block(path.read_text(encoding="utf-8"))
    lines = text.splitlines()
    stand = next((line.strip() for line in lines if line.startswith("Stand: ")), "Stand: unbekannt")
    active = next((line.strip() for line in lines if line.startswith("Aktiver Produktivpfad: ")), "Aktiver Produktivpfad: /opt/portwaechter")
    green = _bullet_lines(_extract_section(text, "## 4. Welche Ergebnisse gruen sind"), limit=3)
    risks = _bullet_lines(_extract_section(text, "## 5. Welche Restrisiken oder offenen Punkte bleiben"), limit=3)
    body = [
        "CB FUND DESK - NACHTLAUF FERTIG",
        "",
        "Der aktuelle Nachtstand ist abgeschlossen.",
        "Die Uebergabe liegt in:",
        str(path),
        "",
        "Wichtige Punkte:",
        "- Kernstand aktualisiert",
        "- Tests/Smoke-Checks gelaufen",
        "- offene Restpunkte im Handoff dokumentiert",
        "",
        stand,
        active,
    ]
    if green:
        body.extend(["", "Gruene Checks:"] + green)
    if risks:
        body.extend(["", "Restrisiken:"] + risks)
    return "\n".join(body)[:1900]


def notify_nightly_handoff(cfg: dict, *, force: bool = False) -> dict:
    readiness = readiness_check(cfg)
    path = Path(readiness.get("path") or handoff_path(cfg))
    if not readiness.get("ready"):
        log.info("nightly_handoff_notify_skipped reason=%s path=%s", readiness.get("reason"), path)
        return {"status": "skipped_not_ready", **readiness}

    handoff_hash = str(readiness.get("hash") or "")
    state = _load_state(cfg)
    if not force and handoff_hash and handoff_hash == str(state.get("last_sent_hash") or ""):
        return {
            "status": "dedupe_skip",
            "reason": "already_sent_for_current_handoff",
            "path": str(path),
            "hash": handoff_hash,
            "sent_at": state.get("last_sent_at"),
        }

    tg_cfg = cfg.get("notify", {}).get("telegram", {})
    token = os.getenv(tg_cfg.get("bot_token_env", "TG_BOT_TOKEN"))
    chat_id = os.getenv(tg_cfg.get("chat_id_env", "TG_CHAT_ID"))
    if not token or not chat_id:
        detail = "Telegram-Zugangsdaten fehlen."
        log.warning("nightly_handoff_notify_failed reason=missing_token_or_chat path=%s", path)
        _upsert_status_block(path, status="FEHLGESCHLAGEN", detail=detail)
        state.update({"last_failed_hash": handoff_hash, "last_failed_at": now_iso_tz(), "last_error": "missing_token_or_chat"})
        _save_state(cfg, state)
        return {"status": "error", "reason": "missing_token_or_chat", "path": str(path), "hash": handoff_hash}

    text = build_completion_text(cfg)
    send_result = send_message_result(token, chat_id, text, cfg, keyboard_rows=None)
    if not send_result.get("ok"):
        reason = str(send_result.get("reason") or "send_error")
        detail = f"Telegram-Versand fehlgeschlagen: {reason}"
        log.warning("nightly_handoff_notify_failed reason=%s path=%s", reason, path)
        _upsert_status_block(path, status="FEHLGESCHLAGEN", detail=detail)
        state.update({"last_failed_hash": handoff_hash, "last_failed_at": now_iso_tz(), "last_error": reason})
        _save_state(cfg, state)
        return {"status": "error", "reason": reason, "path": str(path), "hash": handoff_hash}

    _upsert_status_block(path, status="GESENDET", detail="Telegram-Abschlussmeldung erfolgreich versendet.")
    state.update(
        {
            "last_sent_hash": handoff_hash,
            "last_sent_at": now_iso_tz(),
            "last_message_id": send_result.get("message_id"),
            "last_failed_hash": None,
            "last_error": None,
        }
    )
    _save_state(cfg, state)
    log.info("nightly_handoff_notify_sent path=%s message_id=%s", path, send_result.get("message_id"))
    return {"status": "sent", "path": str(path), "hash": handoff_hash, "message_id": send_result.get("message_id"), "text": text}
