from __future__ import annotations

import json
from pathlib import Path

from modules.common.utils import write_json
from modules.v2 import main as v2_main


def _cfg(tmp_path: Path) -> dict:
    return {
        "app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"},
        "notify": {"telegram": {"enabled": False, "bot_token_env": "TG_BOT_TOKEN", "chat_id_env": "TG_CHAT_ID"}},
        "v2": {
            "data_dir": "data/v2",
            "symbol_map_path": "config/symbol_map_v2.json",
            "scanner_universe_path": "config/scanner_universe_v2.json",
            "watchlist_path": "data/watchlist/watchlist.json",
            "marketdata": {"batch_size": 4, "timeout_sec": 5, "max_live_fallback_symbols": 0},
            "telegram": {"watch_max_per_day": 10, "action_max_per_day": 3, "defense_max_per_day": 5, "cooldown_minutes": 1},
            "quiet_hours": {"start": "22:00", "end": "07:00"},
        },
    }


def _seed_files(tmp_path: Path) -> None:
    write_json(
        tmp_path / "config" / "symbol_map_v2.json",
        {
            "DE000BASF111": {"symbol": "BAS.DE", "provider": "twelvedata", "name": "BASF SE", "sector": "materials", "country": "DE"},
        },
    )
    write_json(
        tmp_path / "config" / "scanner_universe_v2.json",
        {
            "items": [
                {"symbol": "BAS.DE", "name": "BASF SE", "country": "DE", "sector": "materials", "group": "scanner"},
                {"symbol": "SAP.DE", "name": "SAP SE", "country": "DE", "sector": "technology", "group": "scanner"},
            ]
        },
    )
    write_json(
        tmp_path / "data" / "snapshots" / "portfolio_test.json",
        {
            "positions": [
                {"isin": "DE000BASF111", "name": "BASF SE", "market_value_eur": 5000},
            ]
        },
    )
    write_json(tmp_path / "data" / "briefings" / "morning_20260309.json", {"regime": {"regime": "risk_on"}})
    write_json(
        tmp_path / "data" / "news" / "top_opportunities_20260309.json",
        {
            "top": [
                {"title": "BASF earnings guidance raised", "summary": "IR outlook improved", "source": "IR"},
            ]
        },
    )
    (tmp_path / "data" / "news" / "items_translated_20260309.jsonl").write_text("", encoding="utf-8")
    write_json(tmp_path / "data" / "marketdata" / "volume_baseline.json", {"DE000BASF111": {"median_rolling": 100000, "count": 20}})
    write_json(
        tmp_path / "data" / "performance" / "reports" / "weekly_2026W08.json",
        {
            "score_calibration": {"factor_score>=4": {"3d": {"expectancy": 0.8, "expectancy_confidence": "high"}}},
            "by_regime": {"risk_on": {"3d": {"expectancy": 0.4, "expectancy_confidence": "medium"}}},
        },
    )


def test_v2_main_smoke_and_provider_failure(tmp_path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    _seed_files(tmp_path)
    sent: list[str] = []

    monkeypatch.setattr(
        v2_main,
        "fetch_quotes_for_instruments",
        lambda instruments, cfg, api_key=None: [
            {
                "symbol": "BAS.DE",
                "isin": "DE000BASF111",
                "name": "BASF SE",
                "group": "holding",
                "quote": {
                    "symbol": "BAS.DE",
                    "price": 53.2,
                    "percent_change": 2.6,
                    "volume": 320000,
                    "timestamp": "2026-03-09T10:00:00+01:00",
                    "status": "ok",
                    "provider": "twelvedata",
                },
            },
            {
                "symbol": "SAP.DE",
                "isin": None,
                "name": "SAP SE",
                "group": "scanner",
                "quote": {
                    "symbol": "SAP.DE",
                    "price": None,
                    "percent_change": None,
                    "volume": None,
                    "timestamp": None,
                    "status": "error",
                    "provider": "none",
                },
            },
        ],
    )
    monkeypatch.setattr(v2_main, "send_action", lambda candidate, text, cfg: sent.append(text) or True)
    monkeypatch.setattr(v2_main, "send_watch_bundle", lambda candidates, cfg: sent.append("watch_bundle") or True)
    monkeypatch.setattr(v2_main, "send_defense", lambda candidate, text, cfg: sent.append(text) or True)

    result = v2_main.run(cfg)

    assert result["status"] == "ok"
    assert any(row["classification"] == "ACTION" for row in result["recommendations"])
    assert any(row["classification"] == "IGNORE" for row in result["recommendations"])
    assert result["bridge_exported"]
    assert sent

    candidates_path = Path(result["persisted"]["candidates_path"])
    recommendations_path = Path(result["persisted"]["recommendations_path"])
    proposal_path = Path(result["bridge_exported"][0])
    assert candidates_path.exists()
    assert recommendations_path.exists()
    assert proposal_path.exists()

    payload = json.loads(recommendations_path.read_text(encoding="utf-8"))
    assert payload["recommendations"][0]["classification"] in {"ACTION", "WATCH", "DEFENSE", "IGNORE"}
