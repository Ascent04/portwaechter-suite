from __future__ import annotations

from pathlib import Path

from modules.telegram_commands import nightly_handoff


def _cfg(tmp_path: Path) -> dict:
    return {
        "app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"},
        "notify": {"telegram": {"enabled": True, "bot_token_env": "TG_BOT_TOKEN", "chat_id_env": "TG_CHAT_ID"}},
    }


def _write_ready_handoff(tmp_path: Path) -> None:
    (tmp_path / "SYSTEM_OVERVIEW.md").write_text("# SYSTEM_OVERVIEW\n", encoding="utf-8")
    (tmp_path / "NIGHTLY_HANDOFF.md").write_text(
        "\n".join(
            [
                "# NIGHTLY_HANDOFF",
                "",
                "Stand: 2026-03-11",
                "Aktiver Produktivpfad: `/opt/portwaechter`",
                "",
                "## 1. Was in dieser Nacht umgesetzt wurde",
                "",
                "- Kernstand aktualisiert",
                "- Ticket-/Execution-Pfad gehaertet",
                "",
                "## 2. Welche Dateien geaendert wurden",
                "",
                "- modules/virus_bridge/execution_report.py",
                "",
                "## 3. Welche Tests gelaufen sind",
                "",
                "```bash",
                "pytest -q tests/test_execution_report.py",
                "```",
                "",
                "## 4. Welche Ergebnisse gruen sind",
                "",
                "- Execution-Block: `20 passed`",
                "- Warn-/Operator-Checks: `11 passed`",
                "- Demo-Bootstrap: `2 passed`",
                "",
                "## 5. Welche Restrisiken oder offenen Punkte bleiben",
                "",
                "- keine echten Execution-Dateien im Produktivpfad",
                "- offene PnL haengt an belastbaren Quotes",
                "- Monatsreport muss nach Realbetrieb neu erzeugt werden",
                "",
                "## 6. Was als naechstes empfohlen wird",
                "",
                "1. Ersten Realtrade durchlaufen",
            ]
        ),
        encoding="utf-8",
    )


def test_notify_nightly_handoff_sends_once_and_updates_state(tmp_path: Path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    _write_ready_handoff(tmp_path)
    monkeypatch.setenv("TG_BOT_TOKEN", "token")
    monkeypatch.setenv("TG_CHAT_ID", "-123")
    sent: list[str] = []
    monkeypatch.setattr(
        nightly_handoff,
        "send_message_result",
        lambda token, chat_id, text, cfg, keyboard_rows=None: sent.append(text) or {"ok": True, "message_id": 77, "reason": "ok"},
    )

    result = nightly_handoff.notify_nightly_handoff(cfg)
    second = nightly_handoff.notify_nightly_handoff(cfg)
    handoff_text = (tmp_path / "NIGHTLY_HANDOFF.md").read_text(encoding="utf-8")

    assert result["status"] == "sent"
    assert "CB FUND DESK - NACHTLAUF FERTIG" in sent[0]
    assert "/opt/portwaechter/NIGHTLY_HANDOFF.md" not in sent[0] or "NIGHTLY_HANDOFF.md" in sent[0]
    assert "NIGHTLY_HANDOFF.md" in sent[0]
    assert second["status"] == "dedupe_skip"
    assert "## Telegram-Abschlussversand" in handoff_text
    assert "Status: GESENDET" in handoff_text


def test_notify_nightly_handoff_skips_when_handoff_not_ready(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    (tmp_path / "NIGHTLY_HANDOFF.md").write_text("# NIGHTLY_HANDOFF\n\nStand: 2026-03-11\n", encoding="utf-8")

    result = nightly_handoff.notify_nightly_handoff(cfg)

    assert result["status"] == "skipped_not_ready"
    assert result["reason"] in {"handoff_sections_missing", "system_overview_missing"}


def test_notify_nightly_handoff_failure_is_written_to_handoff(tmp_path: Path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    _write_ready_handoff(tmp_path)
    monkeypatch.setenv("TG_BOT_TOKEN", "token")
    monkeypatch.setenv("TG_CHAT_ID", "-123")
    monkeypatch.setattr(
        nightly_handoff,
        "send_message_result",
        lambda token, chat_id, text, cfg, keyboard_rows=None: {"ok": False, "message_id": None, "reason": "telegram_not_ok"},
    )

    result = nightly_handoff.notify_nightly_handoff(cfg)
    handoff_text = (tmp_path / "NIGHTLY_HANDOFF.md").read_text(encoding="utf-8")

    assert result["status"] == "error"
    assert result["reason"] == "telegram_not_ok"
    assert "## Telegram-Abschlussversand" in handoff_text
    assert "Status: FEHLGESCHLAGEN" in handoff_text
    assert "Telegram-Versand fehlgeschlagen: telegram_not_ok" in handoff_text
