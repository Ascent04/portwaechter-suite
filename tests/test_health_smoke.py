from __future__ import annotations

from pathlib import Path

from modules.health.report import collect_health_report


def test_health_report_handles_missing_inputs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TG_BOT_TOKEN", "")
    monkeypatch.setenv("TG_CHAT_ID", "")

    cfg = {
        "app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"},
        "notify": {
            "telegram": {
                "enabled": True,
                "bot_token_env": "TG_BOT_TOKEN",
                "chat_id_env": "TG_CHAT_ID",
            }
        },
        "news": {"feed_sources": []},
    }

    (tmp_path / "data").mkdir(parents=True, exist_ok=True)

    report = collect_health_report(cfg=cfg, root_dir=tmp_path)

    assert report["overall_status"] in {"ok", "failed"}
    checks = report["checks"]

    assert checks["portfolio_ingest"] in {"ok", "skipped_no_pdf", "fail"}
    assert checks["marketdata"] in {"ok", "missing_mapping_only", "permission_fail"}
    assert checks["news"] in {"ok", "no_feeds", "parse_fail"}
    assert checks["signals"] in {"ok", "0_signals", "input_missing"}
    assert checks["telegram"] in {"ok", "cooldown", "missing_env"}
    assert checks["systemd"] in {"ok", "failed", "start-limit-hit"}
    assert checks["permissions"] in {"ok", "root_owned_files"}
