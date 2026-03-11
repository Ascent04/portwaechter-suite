from __future__ import annotations

import logging
from pathlib import Path

from modules.common.utils import read_json, write_json
from modules.virus_bridge import main as vb_main


def _cfg(tmp_path: Path) -> dict:
    return {
        "app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"},
        "notifications": {"quiet_hours": {"enabled": False}},
        "notify": {"telegram": {"enabled": True, "bot_token_env": "TG_BOT_TOKEN", "chat_id_env": "TG_CHAT_ID"}},
        "integration": {"bridge": {"proposal_dir": "data/integration/signal_proposals", "consumed_dir": "data/integration/consumed"}},
        "virus_bridge": {"tr_universe_path": "config/universe_tr_verified.json"},
        "hedgefund": {
            "budget_eur": 5000,
            "max_positions": 3,
            "max_risk_per_trade_pct": 1.0,
            "max_total_exposure_pct": 60,
            "sizing": {
                "high_conf_min_eur": 1000,
                "high_conf_max_eur": 1500,
                "medium_conf_min_eur": 750,
                "medium_conf_max_eur": 1000,
                "speculative_min_eur": 0,
                "speculative_max_eur": 500,
            },
        },
    }


def _proposal(score: float, proposal_id: str) -> dict:
    return {
        "proposal_id": proposal_id,
        "source": "portwaechter_v2",
        "asset": {"symbol": "AMD", "isin": "US0079031078", "name": "Advanced Micro Devices"},
        "classification": "KAUFIDEE_PRUEFEN",
        "direction": "long",
        "quote": {"last_price": 197.69, "currency": "USD", "percent_change": 2.7, "timestamp": "2026-03-09T21:10:00+01:00"},
        "score": score,
        "signal_strength": "hoch",
        "market_regime": "positiv",
        "reasons": ["Momentum", "Ungewoehnlich hohes Volumen"],
        "portfolio_context": {"is_holding": False, "weight_pct": 0.0},
        "budget_context": {"budget_eur": 5000},
        "timestamp": "2026-03-09T21:10:00+01:00",
    }


def test_virus_bridge_main_runs_and_consumes_proposals(tmp_path: Path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    sent: list[dict] = []
    write_json(
        tmp_path / "config" / "universe_tr_verified.json",
        {
            "US0079031078": {
                "symbol": "AMD",
                "name": "Advanced Micro Devices",
                "tr_verified": True,
                "asset_type": "stock",
                "market": "NASDAQ",
                "currency": "USD",
            }
        },
    )
    write_json(tmp_path / "data" / "integration" / "signal_proposals" / "20260309" / "proposal_PWV2-20260309-2110-001.json", _proposal(7.2, "PWV2-20260309-2110-001"))
    write_json(tmp_path / "data" / "integration" / "signal_proposals" / "20260309" / "proposal_PWV2-20260309-2111-001.json", _proposal(6.8, "PWV2-20260309-2111-001"))
    monkeypatch.setenv("TG_BOT_TOKEN", "token")
    monkeypatch.setenv("TG_CHAT_ID", "-123")

    monkeypatch.setattr(
        vb_main,
        "send_message_result",
        lambda token, chat_id, text, cfg, keyboard_rows=None: sent.append({"text": text, "rows": keyboard_rows}) or {"ok": True, "message_id": 42, "reason": "ok"},
    )

    result = vb_main.run(cfg)

    assert result["status"] == "ok"
    assert result["summary"]["loaded"] == 2
    assert result["summary"]["deduped"] == 1
    assert result["written_paths"]
    assert sent
    trade_candidate = read_json(Path(result["written_paths"][0]))
    assert trade_candidate["decision"] == "APPROVED"
    assert trade_candidate["last_price"] == 197.69
    assert trade_candidate["currency"] == "USD"
    assert trade_candidate["entry_hint"] == "Einstieg nur bei weiter bestaetigter Staerke beobachten"
    assert trade_candidate["stop_loss_hint"] == "Stop-Loss unterhalb des letzten Ruecksetzers pruefen"
    assert trade_candidate["stop_loss_price"] == 191.76
    assert trade_candidate["risk_eur"] == 37.5
    assert "Letzter Kurs:\n197.69 USD" in sent[0]["text"]
    assert sent[0]["rows"][0] == ["✅ Gekauft", "❌ Nicht gekauft"]
    ticket_state = read_json(tmp_path / "data" / "virus_bridge" / "ticket_state.json")
    stored = ticket_state["tickets"][trade_candidate["ticket_id"]]
    assert stored["status"] == "OPEN"
    assert stored["asset_name"] == "Advanced Micro Devices"
    assert (tmp_path / "data" / "integration" / "consumed" / "20260309" / "proposal_PWV2-20260309-2110-001.json").exists() or (
        tmp_path / "data" / "integration" / "consumed" / "20260309" / "proposal_PWV2-20260309-2111-001.json"
    ).exists()


def test_virus_bridge_send_logs_quiet_hours_suppression(tmp_path: Path, monkeypatch, caplog) -> None:
    cfg = _cfg(tmp_path)
    cfg["notifications"]["quiet_hours"] = {"enabled": True, "start": "00:00", "end": "23:59", "timezone": "Europe/Berlin"}
    write_json(
        tmp_path / "config" / "universe_tr_verified.json",
        {
            "US0079031078": {
                "symbol": "AMD",
                "name": "Advanced Micro Devices",
                "tr_verified": True,
                "asset_type": "stock",
                "market": "NASDAQ",
                "currency": "USD",
            }
        },
    )
    write_json(tmp_path / "data" / "integration" / "signal_proposals" / "20260309" / "proposal_PWV2-20260309-2110-001.json", _proposal(7.2, "PWV2-20260309-2110-001"))
    monkeypatch.setenv("TG_BOT_TOKEN", "token")
    monkeypatch.setenv("TG_CHAT_ID", "-123")

    with caplog.at_level(logging.WARNING):
        vb_main.run(cfg)

    messages = [record.getMessage() for record in caplog.records]
    assert any("virus_bridge_send_attempt:" in message for message in messages)
    assert any("virus_bridge_send_result:" in message and "status=suppressed" in message and "reason=quiet_hours" in message for message in messages)
