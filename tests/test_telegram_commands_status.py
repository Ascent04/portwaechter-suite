from __future__ import annotations

import json
from pathlib import Path

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
    monkeypatch.setattr(poller, "send_message", lambda token, chat, text: sent.append(text) or True)

    poller.run(cfg)

    assert sent
    assert "PortWächter Status" in sent[0]

    inbox = sorted((tmp_path / "data" / "telegram").glob("inbox_*.jsonl"))[-1]
    rows = [json.loads(line) for line in inbox.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(row.get("status") == "ignored_chat" for row in rows)
    assert any(row.get("status") == "accepted" for row in rows)
