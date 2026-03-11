from __future__ import annotations

from pathlib import Path

from modules.telegram_commands import poller
from modules.virus_bridge.execution_performance import compute_execution_summary


def _cfg(tmp_path: Path) -> dict:
    return {
        "app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"},
        "notify": {"telegram": {"enabled": True, "bot_token_env": "TG_BOT_TOKEN", "chat_id_env": "TG_CHAT_ID"}},
        "telegram_commands": {"allowed_chat_ids_env": "TG_CHAT_ID"},
    }


def test_execution_summary_computes_totals_and_win_rate(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    positions = [
        {"asset": {"name": "AMD"}, "status": "OPEN", "realized_pnl_eur": 0.0, "realized_pnl_pct": 0.0, "unrealized_pnl_eur": 50.0, "unrealized_pnl_pct": 5.0},
        {"asset": {"name": "Bayer AG"}, "status": "PARTIALLY_CLOSED", "realized_pnl_eur": 20.0, "realized_pnl_pct": 5.0, "unrealized_pnl_eur": -10.0, "unrealized_pnl_pct": -2.0},
        {"asset": {"name": "Arista"}, "status": "CLOSED", "realized_pnl_eur": 100.0, "realized_pnl_pct": 10.0, "unrealized_pnl_eur": None, "unrealized_pnl_pct": None},
        {"asset": {"name": "Alphabet"}, "status": "CLOSED", "realized_pnl_eur": -50.0, "realized_pnl_pct": -5.0, "unrealized_pnl_eur": None, "unrealized_pnl_pct": None},
    ]

    summary = compute_execution_summary(positions, cfg)

    assert summary["executed_total"] == 4
    assert summary["open_total"] == 1
    assert summary["open_positions_count"] == 2
    assert summary["partially_closed_total"] == 1
    assert summary["partial_exit_count"] == 1
    assert summary["closed_total"] == 2
    assert summary["closed_positions_count"] == 2
    assert summary["realized_pnl_eur_total"] == 70.0
    assert summary["unrealized_pnl_eur_total"] == 40.0
    assert summary["total_pnl_eur"] == 110.0
    assert summary["avg_open_pnl_pct"] == 1.5
    assert summary["avg_closed_pnl_pct"] == 2.5
    assert summary["win_rate_closed"] == 50.0
    assert summary["average_win_eur"] == 100.0
    assert summary["average_loss_eur"] == -50.0
    assert summary["best_closed_trade"]["asset"]["name"] == "Arista"
    assert summary["worst_closed_trade"]["asset"]["name"] == "Alphabet"


def test_execution_command_returns_compact_real_trade_summary(tmp_path: Path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    monkeypatch.setenv("TG_CHAT_ID", "123")
    monkeypatch.setattr(poller, "render_execution_summary", lambda cfg: "CB Fund Desk - Ausfuehrungsstand\n\nOffene Positionen: 1")

    text, action = poller.handle_command({"normalized_text": "/execution", "chat_id": "123"}, cfg)

    assert action["action"] == "execution"
    assert "CB Fund Desk - Ausfuehrungsstand" in text
