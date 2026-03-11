from __future__ import annotations

from pathlib import Path

from modules.common.utils import write_json
from modules.integration.virus_inbox import build_trade_candidate_input, load_pending_signal_proposals, mark_proposal_consumed
from modules.telegram_commands import poller


def _cfg(tmp_path: Path) -> dict:
    return {
        "app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"},
        "integration": {"bridge": {"proposal_dir": "data/integration/signal_proposals", "consumed_dir": "data/integration/consumed"}},
        "v2": {"data_dir": "data/v2"},
        "telegram_commands": {},
    }


def _proposal() -> dict:
    return {
        "proposal_id": "PWV2-20260309-2030-001",
        "source": "portwaechter_v2",
        "asset": {"symbol": "AMD", "isin": "US0079031078", "name": "Advanced Micro Devices"},
        "classification": "KAUFIDEE_PRUEFEN",
        "direction": "long",
        "score": 7.2,
        "signal_strength": "hoch",
        "market_regime": "positiv",
        "reasons": ["Momentum", "Ungewoehnlich hohes Volumen"],
        "portfolio_context": {"is_holding": False, "weight_pct": 0.0},
        "budget_context": {"budget_eur": 5000, "suggested_size_min_eur": 2500, "suggested_size_max_eur": 5000},
        "timestamp": "2026-03-09T20:30:00+01:00",
    }


def test_bridge_queue_load_mark_consumed_and_build_input(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    proposal = _proposal()
    write_json(tmp_path / "data" / "integration" / "signal_proposals" / "20260309" / "proposal_PWV2-20260309-2030-001.json", proposal)

    pending = load_pending_signal_proposals(cfg)
    trade_input = build_trade_candidate_input(pending[0])

    assert len(pending) == 1
    assert pending[0]["proposal_id"] == proposal["proposal_id"]
    assert trade_input["symbol"] == "AMD"
    assert trade_input["classification"] == "KAUFIDEE_PRUEFEN"
    assert trade_input["budget_eur"] == 5000

    assert mark_proposal_consumed(proposal["proposal_id"], cfg) is True
    assert load_pending_signal_proposals(cfg) == []
    assert (tmp_path / "data" / "integration" / "consumed" / "20260309" / "proposal_PWV2-20260309-2030-001.json").exists()


def test_proposals_command_lists_open_items(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    write_json(tmp_path / "data" / "integration" / "signal_proposals" / "20260309" / "proposal_PWV2-20260309-2030-001.json", _proposal())
    write_json(
        tmp_path / "data" / "virus_bridge" / "trade_candidates" / "20260309" / "ticket_VF-20260309-2035-001.json",
        {
            "ticket_id": "VF-20260309-2035-001",
            "asset": {"name": "Advanced Micro Devices"},
            "decision": "APPROVED",
            "size_min_eur": 1000,
            "size_max_eur": 1500,
            "suggested_eur": 1250,
            "timestamp": "2026-03-09T20:35:00+01:00",
        },
    )

    text, action = poller.handle_command({"normalized_text": "/proposals", "text": "/proposals"}, cfg)

    assert action["action"] == "proposals"
    assert "Offene Kaufideen:" in text
    assert "1. Advanced Micro Devices | Score 7.2 | Signalstaerke hoch" in text
    assert "Letzte Trade-Kandidaten:" in text
    assert "1. Advanced Micro Devices | OPERATIV | 1000-1500 EUR" in text

    assert mark_proposal_consumed("PWV2-20260309-2030-001", cfg) is True
    empty_text, _ = poller.handle_command({"normalized_text": "/proposals", "text": "/proposals"}, cfg)
    assert "Keine offenen Kaufideen in der Uebergabe an Virus Fund." in empty_text


def test_proposals_command_marks_incomplete_trade_candidate_honestly(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    write_json(
        tmp_path / "data" / "virus_bridge" / "trade_candidates" / "20260309" / "ticket_VF-20260309-2035-002.json",
        {
            "ticket_id": "VF-20260309-2035-002",
            "asset": {"name": "Advanced Micro Devices"},
            "decision": "APPROVED",
            "operational_is_actionable": False,
            "operational_missing_labels": ["Stop-Kurs", "Maximales Risiko", "Positionsgroesse"],
            "timestamp": "2026-03-09T20:36:00+01:00",
        },
    )

    text, action = poller.handle_command({"normalized_text": "/proposals", "text": "/proposals"}, cfg)

    assert action["action"] == "proposals"
    assert "UNVOLLSTAENDIG" in text
    assert "fehlt: Stop-Kurs, Maximales Risiko" in text
