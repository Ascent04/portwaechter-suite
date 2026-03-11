from __future__ import annotations

from pathlib import Path

from modules.common.utils import read_json
from modules.organism import report_render
from modules.telegram_commands import poller


def _cfg(tmp_path: Path) -> dict:
    return {
        "app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"},
        "notify": {"telegram": {"enabled": True, "bot_token_env": "TG_BOT_TOKEN", "chat_id_env": "TG_CHAT_ID"}},
        "telegram_commands": {"allowed_chat_ids_env": "TG_CHAT_ID"},
    }


def _report() -> dict:
    return {
        "period": "2026-03",
        "generated_at": "2026-03-10T19:00:00+01:00",
        "activity": {"kaufen_pruefen_total": 6, "verkaufen_pruefen_total": 2, "executed_total": 2, "closed_total": 1},
        "performance": {
            "realized_pnl_eur_total": 75.0,
            "unrealized_pnl_eur_total": 20.0,
            "win_rate_closed": 50.0,
            "best_trade": {"name": "AMD", "pnl_pct": 8.0},
            "worst_trade": {"name": "Bayer AG", "pnl_pct": -4.0},
        },
        "api": {"api_calls_total": 32.0, "degraded_runs_total": 1},
        "economics": {
            "monthly_cost_eur_estimate": 26.68,
            "realized_pnl_before_costs": 75.0,
            "realized_pnl_minus_cost_eur": 48.32,
            "cost_coverage_status": "KOSTEN_GEDECKT",
            "realized_pnl_complete": True,
            "executed_entries_count": 2,
            "realized_exit_count": 1,
        },
        "cost_status": {"cost_coverage_status": "KOSTEN_GEDECKT"},
        "evaluation": {"organism_status": "WEITER_FUEHREN", "summary": "Der Desk arbeitet stabil genug und kann im naechsten Monat normal weitergefuehrt werden."},
    }


def test_monthly_report_is_written_and_rendered(tmp_path: Path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    monkeypatch.setattr(report_render, "build_monthly_evaluation", lambda cfg, period=None: _report())

    result = report_render.build_and_write_monthly_evaluation(cfg)
    saved = read_json(result["path"])
    text = report_render.render_organism_text(cfg)

    assert Path(result["path"]).exists()
    assert saved["period"] == "2026-03"
    assert "CB Fund Desk - Monatsbewertung" in text
    assert "Bewertung:\nWEITER_FUEHREN" in text
    assert "Ergebnis nach Kosten: 48,32 EUR" in text
    assert "Kostenstatus: KOSTEN_GEDECKT" in text
    assert "Echte Ausfuehrungen: 2" in text
    assert "Geschlossen: 1" in text
    assert "Bewertbare Exits: 1" in text


def test_organism_command_returns_compact_monthly_text(tmp_path: Path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    monkeypatch.setenv("TG_CHAT_ID", "123")
    monkeypatch.setattr(poller, "render_organism_text", lambda cfg: "CB Fund Desk - Monatsbewertung\n\nMonat: 2026-03")

    text, action = poller.handle_command({"normalized_text": "/organism", "chat_id": "123"}, cfg)

    assert action["action"] == "organism"
    assert "Monat: 2026-03" in text


def test_monthly_report_surfaces_operator_warnings(tmp_path: Path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)

    def _warning_report() -> dict:
        report = _report()
        report["activity"]["executed_total"] = 1
        report["api"]["degraded_runs_total"] = 2
        report["economics"]["executed_entries_count"] = 1
        report["economics"]["realized_exit_count"] = 0
        report["economics"]["realized_pnl_complete"] = False
        report["economics"]["cost_coverage_status"] = "NICHT_GEDECKT"
        report["evaluation"]["organism_status"] = "GEDROSSELT_FUEHREN"
        return report

    monkeypatch.setattr(report_render, "build_monthly_evaluation", lambda cfg, period=None: _warning_report())

    text = report_render.render_organism_text(cfg)

    assert "Warnlage:" in text
    assert "UNVOLLSTAENDIG: Mindestens ein echter Exit ist nicht voll erfasst." in text
    assert "KOSTEN NICHT GEDECKT: Die laufende Kostenhuerde ist nicht gedeckt." in text
    assert "API-DRUCK / BETRIEBSSTRESS: Der Betrieb wurde im Zeitraum mindestens einmal gedrosselt." in text
