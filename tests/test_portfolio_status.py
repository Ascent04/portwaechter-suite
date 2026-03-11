from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

from modules.common.utils import write_json
from modules.portfolio_status.status import build_portfolio_status, render_portfolio_status
from modules.telegram_commands import poller


def _cfg(tmp_path: Path) -> dict:
    return {
        "app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"},
        "hedgefund": {"budget_eur": 5000},
        "notify": {"telegram": {"enabled": True, "bot_token_env": "TG_BOT_TOKEN", "chat_id_env": "TG_CHAT_ID"}},
        "telegram_commands": {"allowed_chat_ids_env": "TG_CHAT_ID"},
        "v2": {"data_dir": "data/v2"},
        "data_quality": {"max_quote_age_minutes": 30},
    }


def _touch(path: Path, dt: datetime) -> None:
    ts = dt.timestamp()
    os.utime(path, (ts, ts))


def _snapshot(tmp_path: Path, dt: datetime, total: float = 12840.0, cash_eur: float | None = None) -> Path:
    path = tmp_path / "data" / "snapshots" / "portfolio_test.json"
    payload = {
        "asof": dt.strftime("%d.%m.%Y"),
        "computed_total_eur": total,
        "validation_status": "ok",
        "run_id": "snap-1",
        "positions": [
            {"isin": "DE000BAY0017", "name": "Bayer AG", "quantity": 10, "price_eur": 25.0, "market_value_eur": 250.0},
            {"isin": "DE000ENER6Y0", "name": "Siemens Energy", "quantity": 20, "price_eur": 30.0, "market_value_eur": 600.0},
        ],
    }
    if cash_eur is not None:
        payload["cash_eur"] = cash_eur
    write_json(path, payload)
    _touch(path, dt)
    return path


def _manual_position(
    tmp_path: Path,
    ticket_id: str,
    asset_name: str = "Advanced Micro Devices",
    executed_at: str = "2026-03-10T19:00:00+01:00",
    buy_price: float = 100.0,
    size_eur: float = 500.0,
    remaining_size_eur: float = 500.0,
    status: str = "EXECUTED",
) -> None:
    write_json(
        tmp_path / "data" / "virus_bridge" / "executions" / "20260310" / f"execution_{ticket_id}.json",
        {
            "ticket_id": ticket_id,
            "status": "EXECUTED",
            "buy_price": buy_price,
            "size_eur": size_eur,
            "executed_at": executed_at,
            "source": "telegram_manual",
        },
    )
    write_json(
        tmp_path / "data" / "virus_bridge" / "ticket_state.json",
        {
            "tickets": {
                ticket_id: {
                    "status": status,
                    "entry_price": buy_price,
                    "entry_size_eur": size_eur,
                    "remaining_size_eur": remaining_size_eur,
                    "asset_name": asset_name,
                    "last_updated": executed_at,
                }
            }
        },
    )


def test_confirmed_snapshot_renders_depotauszug_with_high_confidence(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _snapshot(tmp_path, datetime.now() - timedelta(hours=2), total=35370.34, cash_eur=1250.0)

    status = build_portfolio_status(cfg)
    text = render_portfolio_status(cfg)

    assert status["source_type"] == "DEPOTAUSZUG"
    assert status["freshness_status"] == "AKTUELL"
    assert status["confidence_status"] == "HOCH"
    assert status["positions_count"] == 2
    assert status["gross_value_eur"] == 35370.34
    assert status["free_budget_eur"] == 1250.0
    assert "DEPOTAUSZUG" in text
    assert "AKTUELL" in text
    assert "HOCH" in text
    assert "35.370,34 EUR" in text


def test_snapshot_plus_newer_manual_execution_becomes_gemischt(tmp_path: Path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    snapshot_dt = datetime.now() - timedelta(hours=4)
    _snapshot(tmp_path, snapshot_dt, total=10000.0)
    _manual_position(tmp_path, "VF-1", executed_at=(snapshot_dt + timedelta(hours=3)).isoformat())
    monkeypatch.setenv("TG_CHAT_ID", "123")

    status = build_portfolio_status(cfg)
    text, action = poller.handle_command({"normalized_text": "/portfolio", "text": "/portfolio", "chat_id": "123"}, cfg)

    assert status["source_type"] == "GEMISCHT"
    assert status["freshness_status"] == "TEILWEISE_AKTUELL"
    assert status["confidence_status"] == "MITTEL"
    assert status["positions_count"] == 3
    assert status["gross_value_eur"] == 10500.0
    assert status["free_budget_eur"] == 4500.0
    assert "Quelle:\nGEMISCHT" in text
    assert "TEILWEISE AKTUELL" in text
    assert "Warnlage:\n- VERALTET: Portfolio-Stand nur teilweise aktuell.\n- UNVOLLSTAENDIG: Stand enthaelt zusaetzliche manuelle Ausfuehrungen." in text
    assert "Einzelne Ausfuehrungen wurden zusaetzlich aus dem Lifecycle uebernommen." in text
    assert action["action"] == "portfolio"


def test_manual_only_uses_telegram_executions_with_limited_confidence(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _manual_position(tmp_path, "VF-2", executed_at=datetime.now().isoformat(), size_eur=600.0, remaining_size_eur=600.0)

    status = build_portfolio_status(cfg)
    text = render_portfolio_status(cfg)

    assert status["source_type"] == "TELEGRAM_AUSFUEHRUNGEN"
    assert status["confidence_status"] == "MITTEL"
    assert status["gross_value_eur"] == 600.0
    assert status["free_budget_eur"] == 4400.0
    assert "TELEGRAM AUSFUEHRUNGEN" in text
    assert "Warnlage:\n- VERALTET: Portfolio-Stand nur teilweise aktuell.\n- NOCH NICHT BEWERTBAR: Kein bestaetigter Depotauszug vorhanden." in text
    assert "HOCH" not in text
    assert "600,00 EUR" in text


def test_old_snapshot_is_marked_as_veraltet_and_low_confidence(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _snapshot(tmp_path, datetime.now() - timedelta(days=10), total=9000.0)

    status = build_portfolio_status(cfg)
    text = render_portfolio_status(cfg)

    assert status["freshness_status"] == "VERALTET"
    assert status["confidence_status"] == "NIEDRIG"
    assert "Warnlage:\n- VERALTET: Portfolio-Stand veraltet.\n- VERALTET: Datenqualitaet niedrig." in text
    assert "VERALTET" in text
    assert "NIEDRIG" in text


def test_free_budget_is_not_fabricated_when_not_reliably_available(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _snapshot(tmp_path, datetime.now() - timedelta(hours=1), total=12840.0)

    status = build_portfolio_status(cfg)
    text = render_portfolio_status(cfg)

    assert status["free_budget_eur"] is None
    assert "Freies Budget:\nnicht belastbar verfuegbar" in text
