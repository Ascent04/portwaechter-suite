from __future__ import annotations

import json
from pathlib import Path

from modules.telegram_commands import handlers
from modules.telegram_commands import poller


def _cfg(tmp_path: Path) -> dict:
    return {
        "app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"},
        "notify": {"telegram": {"enabled": True, "bot_token_env": "TG_BOT_TOKEN", "chat_id_env": "TG_CHAT_ID"}},
        "telegram_commands": {
            "enabled": True,
            "allowed_chat_ids_env": "TG_CHAT_ID",
            "state_file": "data/telegram/command_state.json",
            "inbox_jsonl": "data/telegram/inbox_YYYYMMDD.jsonl",
            "actions_jsonl": "data/telegram/actions_YYYYMMDD.jsonl",
        },
        "alert_profiles": {"current": "balanced", "profiles": {"balanced": {"watch_alerts": {}, "marketdata_alerts": {}}}},
    }


def test_status_response_and_reject_wrong_chat(tmp_path: Path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    monkeypatch.setenv("TG_BOT_TOKEN", "token")
    monkeypatch.setenv("TG_CHAT_ID", "123")

    updates = [
        {"update_id": 10, "message": {"chat": {"id": 999}, "text": "/status"}},
        {"update_id": 11, "message": {"chat": {"id": 123}, "text": "/status"}},
    ]
    sent: list[str] = []

    monkeypatch.setattr(poller, "fetch_updates", lambda token, offset: updates)
    monkeypatch.setattr(poller, "send_message", lambda token, chat, text, cfg, keyboard_rows=None: sent.append(text) or True)

    poller.run(cfg)

    assert sent
    assert any("CB Fund Desk - Status" in msg for msg in sent)
    assert any("Gruppenchat" in msg for msg in sent)

    inbox = sorted((tmp_path / "data" / "telegram").glob("inbox_*.jsonl"))[-1]
    rows = [json.loads(line) for line in inbox.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(row.get("status") == "ignored_chat" for row in rows)
    assert any(row.get("status") == "accepted" for row in rows)


def test_wrong_chat_gets_group_notice(tmp_path: Path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    monkeypatch.setenv("TG_BOT_TOKEN", "token")
    monkeypatch.setenv("TG_CHAT_ID", "-5258138897")

    updates = [{"update_id": 77, "message": {"chat": {"id": 86077475}, "text": "/status"}}]
    sent: list[str] = []

    monkeypatch.setattr(poller, "fetch_updates", lambda token, offset: updates)
    monkeypatch.setattr(poller, "send_message", lambda token, chat, text, cfg, keyboard_rows=None: sent.append(text) or True)

    poller.run(cfg)

    assert len(sent) == 1
    assert "Gruppenchat" in sent[0]


def test_status_with_bot_mention_is_accepted(tmp_path: Path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    monkeypatch.setenv("TG_BOT_TOKEN", "token")
    monkeypatch.setenv("TG_CHAT_ID", "-5258138897")

    updates = [
        {"update_id": 12, "message": {"chat": {"id": -5258138897}, "text": "/status@portwaechter_bot"}},
    ]
    sent: list[str] = []

    monkeypatch.setattr(poller, "fetch_updates", lambda token, offset: updates)
    monkeypatch.setattr(poller, "send_message", lambda token, chat, text, cfg, keyboard_rows=None: sent.append(text) or True)

    poller.run(cfg)

    assert len(sent) == 1
    assert "CB Fund Desk - Status" in sent[0]


def test_status_warns_on_api_pressure(tmp_path: Path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    monkeypatch.setattr(
        handlers,
        "status_snapshot",
        lambda cfg: {
            "enabled": True,
            "minute_used": 55,
            "minute_limit_hard": 55,
            "mode": "blocked",
            "scanner_throttled": True,
        },
    )

    text = handlers.status_text(cfg, verbose=False)

    assert "Warnlage:" in text
    assert "API-DRUCK / BETRIEBSSTRESS: API-Budget ist aktuell blockiert." in text


def test_warning_button_opens_compact_warning_view(tmp_path: Path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    monkeypatch.setattr(
        poller,
        "render_warning_summary",
        lambda cfg: "CB Fund Desk - Warnlagen\n\nKurzstand:\n🟡 2 pruefen",
    )

    text, action = poller.handle_command({"text": "⚠ Warnlagen", "chat_id": "123"}, cfg, state={"ui_context_by_chat": {"123": "main_menu"}})

    assert "CB Fund Desk - Warnlagen" in text
    assert action["action"] == "ui_warnings"
    assert action["reply_keyboard"][0] == ["📊 Status", "💼 Portfolio"]
    assert action["ui_context"] == "status_menu"


def test_pdf_upload_is_processed(tmp_path: Path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    monkeypatch.setenv("TG_BOT_TOKEN", "token")
    monkeypatch.setenv("TG_CHAT_ID", "-5258138897")

    updates = [
        {
            "update_id": 88,
            "message": {
                "chat": {"id": -5258138897},
                "document": {
                    "file_id": "abc123",
                    "file_name": "Depotauszug.pdf",
                    "mime_type": "application/pdf",
                },
            },
        }
    ]
    sent: list[str] = []

    monkeypatch.setattr(poller, "fetch_updates", lambda token, offset: updates)
    monkeypatch.setattr(
        poller,
        "save_pdf_to_inbox",
        lambda token, cfg, file_id, file_name, update_id: {"ok": True, "path": "/tmp/tg_88_Depotauszug.pdf"},
    )
    monkeypatch.setattr(poller, "send_message", lambda token, chat, text, cfg, keyboard_rows=None: sent.append(text) or True)

    poller.run(cfg)

    assert len(sent) == 1
    assert "PDF empfangen" in sent[0]
