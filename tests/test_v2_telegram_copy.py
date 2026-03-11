from __future__ import annotations

from modules.common.utils import write_json
from modules.telegram_commands.handlers import status_text
from modules.v2.recommendations.render import render_recommendation


def _candidate() -> dict:
    return {
        "name": "Bayer AG",
        "symbol": "BAYN.DE",
        "isin": "DE000BAY0017",
        "group": "holding",
        "provider": "twelvedata",
        "quote": {"symbol": "BAYN.DE", "timestamp": "2026-03-09"},
    }


def test_final_telegram_copy_uses_human_german() -> None:
    candidate = _candidate()
    watch = render_recommendation(
        candidate,
        "WATCH",
        {"opportunity": {"total_score": 5.5, "confidence": "mittel", "reasons": ["momentum", "relative_strength", "portfolio_priority"]}, "defense": {"defense_score": 1}, "regime": "neutral"},
    )
    defense = render_recommendation(
        candidate,
        "DEFENSE",
        {
            "opportunity": {"total_score": 1.2, "confidence": "spekulativ", "reasons": []},
            "defense": {"defense_score": 6.0, "sell_score": 4.5, "risk_reduce_score": 6.0, "risk_reduce_reasons": ["news_burden", "high_weight"]},
            "regime": "neutral",
        },
    )

    assert "HALTEN: Bayer AG" in watch["telegram_text"]
    assert "Signalstaerke:\nmittel" in watch["telegram_text"]
    assert "Marktlage:\nneutral" in watch["telegram_text"]
    assert "Warum:\n- Momentum\n- Relative Staerke\n- Depotrelevanz" in watch["telegram_text"]
    assert "portfolio priority" not in watch["telegram_text"].lower()
    assert "relative strength" not in watch["telegram_text"].lower()
    assert "None" not in watch["telegram_text"]
    assert "WATCH" not in watch["telegram_text"]
    assert "Beobachten" not in watch["telegram_text"]

    assert "RISIKO REDUZIEREN: Bayer AG" in defense["telegram_text"]
    assert "Signalstaerke:\nmittel" in defense["telegram_text"]
    assert "Warum:\n- Nachrichtenlage belastend\n- Grosses Positionsgewicht" in defense["telegram_text"]
    assert "Status:\nUNVOLLSTAENDIG" in defense["telegram_text"]
    assert "Signal erst mit sauberem Exit-Hinweis und Positionshinweis weiterverwenden." in defense["telegram_text"]
    assert len(watch["telegram_text"]) < 900
    assert len(defense["telegram_text"]) < 900


def test_status_text_is_translated_for_users(tmp_path, monkeypatch) -> None:
    cfg = {"app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"}}
    write_json(tmp_path / "data" / "briefings" / "morning_20260309.json", {"regime": {"regime": "neutral"}})
    write_json(tmp_path / "data" / "performance" / "reports" / "weekly_2026W10.json", {"ok": True})

    monkeypatch.setattr(
        "modules.telegram_commands.handlers.collect_health_report",
        lambda cfg: {
            "overall_status": "ok",
            "checks": {
                "portfolio_ingest": "ok",
                "marketdata": "missing_mapping_only",
                "news": "ok",
                "signals": "ok",
                "telegram": "ok",
            },
        },
    )

    text = status_text(cfg)

    assert text.startswith("CB Fund Desk - Status")
    assert "Systemlage:\nOK" in text
    assert "Kernbereiche:" in text
    assert "- Portfolio: OK" in text
    assert "- Marktdaten: OK" in text
    assert "Dateien:" in text
    assert "- Morgenbriefing: OK" in text
    assert "- Wochenbericht: OK" in text
    assert "Fehlende Mappings sind aktuell toleriert." in text
    assert "PortWächter" not in text
    assert "overall=" not in text
    assert "missing_mapping_only" not in text
