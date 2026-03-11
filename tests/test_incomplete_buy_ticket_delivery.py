from __future__ import annotations

from pathlib import Path

from modules.common.utils import read_json, write_json
from modules.virus_bridge import main as vb_main


def _cfg(tmp_path: Path) -> dict:
    return {
        "app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"},
        "notifications": {"quiet_hours": {"enabled": False}},
        "notify": {"telegram": {"enabled": True, "bot_token_env": "TG_BOT_TOKEN", "chat_id_env": "TG_CHAT_ID"}},
        "integration": {"bridge": {"proposal_dir": "data/integration/signal_proposals", "consumed_dir": "data/integration/consumed"}},
        "paths": {"audit_jsonl": str(tmp_path / "data" / "audit" / "portfolio_audit.jsonl")},
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


def test_incomplete_buy_signal_is_sent_without_full_ticket_lifecycle(tmp_path: Path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    sent: list[dict] = []
    write_json(
        tmp_path / "config" / "universe_tr_verified.json",
        {
            "DE000BAY0017": {
                "symbol": "BAYN.DE",
                "name": "Bayer AG",
                "tr_verified": True,
                "asset_type": "stock",
                "market": "XETRA",
                "currency": "EUR",
            }
        },
    )
    write_json(
        tmp_path / "data" / "integration" / "signal_proposals" / "20260310" / "proposal_PWV2-20260310-0900-001.json",
        {
            "proposal_id": "PWV2-20260310-0900-001",
            "source": "portwaechter_v2",
            "asset": {"symbol": "BAYN.DE", "isin": "DE000BAY0017", "name": "Bayer AG"},
            "classification": "KAUFIDEE_PRUEFEN",
            "direction": "long",
            "quote": {"currency": "EUR", "timestamp": "2026-03-10T09:00:00+01:00"},
            "score": 6.1,
            "signal_strength": "mittel",
            "market_regime": "neutral",
            "reasons": ["Momentum"],
            "timestamp": "2026-03-10T09:00:00+01:00",
        },
    )
    monkeypatch.setenv("TG_BOT_TOKEN", "token")
    monkeypatch.setenv("TG_CHAT_ID", "-123")
    monkeypatch.setattr(
        vb_main,
        "send_message_result",
        lambda token, chat_id, text, cfg, keyboard_rows=None: sent.append({"text": text, "rows": keyboard_rows}) or {"ok": True, "message_id": 42, "reason": "ok"},
    )

    result = vb_main.run(cfg)

    ticket_id = read_json(Path(result["written_paths"][0]))["ticket_id"]
    lifecycle = read_json(tmp_path / "data" / "virus_bridge" / "ticket_lifecycle" / f"{ticket_id}.json")

    assert sent
    assert sent[0]["rows"] is None
    assert sent[0]["text"].startswith("KAUFIDEE UEBERPRUEFEN: Bayer AG")
    assert [row["event_type"] for row in lifecycle["events"]] == ["TRADE_CANDIDATE_CREATED"]
    assert not (tmp_path / "data" / "virus_bridge" / "ticket_state.json").exists()
