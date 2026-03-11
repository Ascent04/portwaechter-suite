from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from modules.common.utils import ensure_dir, write_json
from modules.organism import monthly_evaluation as me


def _cfg(tmp_path: Path) -> dict:
    return {
        "app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"},
        "organism_evaluation": {"monthly_cost_usd": 29, "eurusd_rate_assumption": 0.92},
    }


def _touch(path: Path, dt: datetime) -> None:
    ts = dt.timestamp()
    os.utime(path, (ts, ts))


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    ensure_dir(path.parent)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _lifecycle(ticket_id: str, events: list[tuple[str, str]]) -> dict:
    return {
        "ticket_id": ticket_id,
        "source_proposal_id": f"PW-{ticket_id}",
        "asset": {"name": ticket_id},
        "created_at": events[0][1],
        "events": [
            {"event_type": event_type, "timestamp": timestamp, "data": {"ticket_id": ticket_id}}
            for event_type, timestamp in events
        ],
        "current_status": "OPEN",
        "last_updated": events[-1][1],
    }


def test_monthly_metrics_aggregate_activity_performance_risk_and_api(tmp_path: Path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    rec_1 = tmp_path / "data" / "v2" / "recommendations_20260310_1000.json"
    rec_2 = tmp_path / "data" / "v2" / "recommendations_20260311_1000.json"
    write_json(
        rec_1,
        {
            "generated_at": "2026-03-10T10:00:00+01:00",
            "recommendations": [
                {"name": "AMD", "classification": "KAUFEN PRUEFEN"},
                {"name": "Bayer AG", "classification": "VERKAUFEN PRUEFEN"},
                {"name": "Siemens Energy", "classification": "HALTEN"},
            ],
        },
    )
    write_json(
        rec_2,
        {
            "generated_at": "2026-03-11T10:00:00+01:00",
            "recommendations": [
                {"name": "Alphabet", "classification": "KAUFEN PRUEFEN"},
                {"name": "DEUTZ", "classification": "RISIKO REDUZIEREN"},
            ],
        },
    )
    _touch(rec_1, datetime(2026, 3, 10, 10, 0))
    _touch(rec_2, datetime(2026, 3, 11, 10, 0))

    tc_1 = tmp_path / "data" / "virus_bridge" / "trade_candidates" / "20260310" / "ticket_VF-1.json"
    tc_2 = tmp_path / "data" / "virus_bridge" / "trade_candidates" / "20260311" / "ticket_VF-2.json"
    write_json(tc_1, {"ticket_id": "VF-1"})
    write_json(tc_2, {"ticket_id": "VF-2"})
    _touch(tc_1, datetime(2026, 3, 10, 11, 0))
    _touch(tc_2, datetime(2026, 3, 11, 11, 0))

    write_json(
        tmp_path / "data" / "virus_bridge" / "ticket_lifecycle" / "VF-1.json",
        _lifecycle(
            "VF-1",
            [
                ("TRADE_CANDIDATE_CREATED", "2026-03-10T09:00:00+01:00"),
                ("TRADE_EXECUTED_MANUAL", "2026-03-10T09:10:00+01:00"),
                ("TRADE_PARTIAL_EXIT", "2026-03-12T10:00:00+01:00"),
                ("TRADE_CLOSED_TARGET_REACHED", "2026-03-15T10:00:00+01:00"),
            ],
        ),
    )
    write_json(
        tmp_path / "data" / "virus_bridge" / "ticket_lifecycle" / "VF-2.json",
        _lifecycle(
            "VF-2",
            [
                ("TRADE_CANDIDATE_CREATED", "2026-03-11T09:00:00+01:00"),
                ("TRADE_EXECUTED_MANUAL", "2026-03-11T09:10:00+01:00"),
            ],
        ),
    )
    write_json(
        tmp_path / "data" / "virus_bridge" / "executions" / "20260310" / "execution_VF-1.json",
        {"ticket_id": "VF-1", "status": "EXECUTED", "buy_price": 100.0, "size_eur": 1000.0, "executed_at": "2026-03-10T09:10:00+01:00"},
    )
    write_json(
        tmp_path / "data" / "virus_bridge" / "executions" / "20260311" / "execution_VF-2.json",
        {"ticket_id": "VF-2", "status": "EXECUTED", "buy_price": 100.0, "size_eur": 600.0, "executed_at": "2026-03-11T09:10:00+01:00"},
    )
    write_json(
        tmp_path / "data" / "virus_bridge" / "ticket_state.json",
        {
            "tickets": {
                "VF-1": {"status": "CLOSED", "entry_price": 100.0, "entry_size_eur": 1000.0, "remaining_size_eur": 0.0},
                "VF-2": {"status": "EXECUTED", "entry_price": 100.0, "entry_size_eur": 600.0, "remaining_size_eur": 600.0},
            }
        },
    )
    write_json(
        tmp_path / "data" / "virus_bridge" / "exits" / "20260315" / "exit_VF-1_20260315T100000.json",
        {"ticket_id": "VF-1", "exit_type": "FULL", "exit_reason": "TARGET_REACHED", "exit_price": 110.0, "size_eur": 1000.0, "realized_pnl_eur": 50.0, "timestamp": "2026-03-15T10:00:00+01:00"},
    )

    _write_jsonl(
        tmp_path / "data" / "api_governor" / "usage_20260310.jsonl",
        [
            {"timestamp": "2026-03-10T10:00:00+01:00", "cost": 1, "mode": "normal"},
            {"timestamp": "2026-03-10T10:00:30+01:00", "cost": 1, "mode": "degraded"},
            {"timestamp": "2026-03-10T10:01:00+01:00", "cost": 1, "mode": "blocked"},
        ],
    )

    monkeypatch.setattr(
        me,
        "_build_all_positions",
        lambda cfg: [
            {
                "ticket_id": "VF-1",
                "asset": {"name": "AMD"},
                "status": "CLOSED",
                "realized_pnl_eur": 50.0,
                "realized_pnl_pct": 10.0,
                "latest_exit_timestamp": "2026-03-15T10:00:00+01:00",
            },
            {
                "ticket_id": "VF-2",
                "asset": {"name": "Alphabet"},
                "status": "OPEN",
                "remaining_size_eur": 600.0,
                "unrealized_pnl_eur": 24.0,
                "unrealized_pnl_pct": 4.0,
            },
            {
                "ticket_id": "VF-3",
                "asset": {"name": "Bayer AG"},
                "status": "PARTIALLY_CLOSED",
                "remaining_size_eur": 300.0,
                "unrealized_pnl_eur": -6.0,
                "unrealized_pnl_pct": -2.0,
            },
        ],
    )
    monkeypatch.setattr(
        me,
        "load_exit_records",
        lambda cfg: [
            {"ticket_id": "VF-1", "timestamp": "2026-03-15T10:00:00+01:00", "realized_pnl_eur": 50.0},
            {"ticket_id": "VF-9", "timestamp": "2026-02-28T10:00:00+01:00", "realized_pnl_eur": 99.0},
        ],
    )
    monkeypatch.setattr(me, "load_trade_candidate", lambda ticket_id, cfg: {"risk_eur": {"VF-2": 18.0, "VF-3": 42.0}.get(ticket_id)})

    report = me.build_monthly_evaluation(cfg, "2026-03")

    assert report["activity"]["scanner_runs"] == 2
    assert report["activity"]["recommendations_total"] == 5
    assert report["activity"]["kaufen_pruefen_total"] == 2
    assert report["activity"]["verkaufen_pruefen_total"] == 1
    assert report["activity"]["risiko_reduzieren_total"] == 1
    assert report["activity"]["halten_total"] == 1
    assert report["activity"]["trade_candidates_total"] == 2
    assert report["activity"]["executed_total"] == 2
    assert report["activity"]["partial_exits_total"] == 1
    assert report["activity"]["closed_total"] == 1
    assert report["performance"]["realized_pnl_eur_total"] == 50.0
    assert report["performance"]["unrealized_pnl_eur_total"] == 18.0
    assert report["performance"]["avg_closed_pnl_pct"] == 10.0
    assert report["performance"]["win_rate_closed"] == 100.0
    assert report["risk"]["open_positions_total"] == 1
    assert report["risk"]["partially_closed_total"] == 1
    assert report["risk"]["total_open_exposure_eur"] == 900.0
    assert report["risk"]["largest_open_position_eur"] == 600.0
    assert report["risk"]["largest_open_risk_eur"] == 42.0
    assert report["api"]["api_calls_total"] == 3.0
    assert report["api"]["avg_calls_per_day"] == 3.0
    assert report["api"]["max_calls_in_minute_seen"] == 2.0
    assert report["api"]["blocked_runs_total"] == 1
    assert report["api"]["degraded_runs_total"] == 1
    assert report["economics"]["monthly_cost_eur_estimate"] == 26.68
    assert report["economics"]["realized_pnl_before_costs"] == 50.0
    assert report["economics"]["realized_pnl_minus_cost_eur"] == 23.32
    assert report["economics"]["cost_coverage_status"] == "KOSTEN_GEDECKT"
    assert report["cost_status"]["cost_coverage_status"] == "KOSTEN_GEDECKT"
