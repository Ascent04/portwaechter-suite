from __future__ import annotations

import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from modules.common.runtime_dirs import ensure_runtime_directories
from modules.common.utils import ensure_dir, write_json
from modules.organism.report_render import build_and_write_monthly_evaluation, render_organism_text
from modules.portfolio_status.status import render_portfolio_status
from modules.virus_bridge.execution_report import build_execution_report, render_execution_summary, write_execution_report


DEMO_LABEL = "DEMO_ONLY"
DEMO_NOTE = "Nur fuer lokale Trockenlaeufe und Erstinbetriebnahme. Keine echten Handelsdaten."


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_demo_root() -> Path:
    return _repo_root() / "testdata" / "demo_desk_runtime"


def _guard_target_root(target_root: Path) -> None:
    repo_root = _repo_root().resolve()
    resolved_target = target_root.resolve()
    if resolved_target == repo_root:
        raise ValueError("target_root_must_not_be_repo_root")


def _demo_cfg(target_root: Path) -> dict:
    return {
        "app": {"root_dir": str(target_root), "timezone": "Europe/Berlin"},
        "hedgefund": {"budget_eur": 5000, "max_risk_per_trade_pct": 1.0},
        "integration": {"bridge": {"proposal_dir": "data/integration/signal_proposals", "consumed_dir": "data/integration/consumed"}},
        "v2": {"data_dir": "data/v2"},
        "data_quality": {"max_quote_age_minutes": 30},
        "organism_evaluation": {"monthly_cost_usd": 30.0, "eurusd_rate_assumption": 0.92},
        "paths": {"audit_jsonl": str(target_root / "data" / "audit" / "portfolio_audit.jsonl")},
    }


def _set_mtime(path: Path, when: datetime) -> None:
    ts = when.timestamp()
    os.utime(path, (ts, ts))


def _event(event_type: str, timestamp: str, data: dict) -> dict:
    return {
        "event_type": event_type,
        "timestamp": timestamp,
        "data": dict(data),
        "audit_ref": None,
    }


def bootstrap_demo_runtime(target_root: Path | str | None = None, *, clean: bool = False, period: str | None = None) -> dict:
    root = Path(target_root) if target_root is not None else default_demo_root()
    _guard_target_root(root)
    if clean and root.exists():
        shutil.rmtree(root)

    cfg = _demo_cfg(root)
    ensure_runtime_directories(cfg)
    ensure_dir(root / "data" / "v2")
    ensure_dir(root / "data" / "snapshots")
    ensure_dir(root / "data" / "audit")
    ensure_dir(root / "output")

    now = datetime.now(ZoneInfo("Europe/Berlin")).replace(microsecond=0)
    month_period = str(period or now.strftime("%Y-%m"))
    proposal_ts = (now - timedelta(hours=3)).isoformat()
    ticket_ts = (now - timedelta(hours=2, minutes=45)).isoformat()
    execution_ts = (now - timedelta(hours=2)).isoformat()
    exit_ts = (now - timedelta(hours=1, minutes=15)).isoformat()
    quote_ts = (now - timedelta(minutes=20)).isoformat()
    day_tag = now.strftime("%Y%m%d")
    ticket_id = f"VF-{day_tag}-1900-001"
    proposal_id = f"PWV2-DEMO-{day_tag}-001"

    proposal_path = root / "data" / "integration" / "signal_proposals" / day_tag / f"proposal_{proposal_id}.json"
    proposal_payload = {
        "proposal_id": proposal_id,
        "source": "demo_seed",
        "demo_label": DEMO_LABEL,
        "demo_note": DEMO_NOTE,
        "asset": {"symbol": "AMD", "isin": "US0079031078", "name": "Advanced Micro Devices"},
        "classification": "KAUFIDEE_PRUEFEN",
        "direction": "long",
        "score": 7.1,
        "signal_strength": "hoch",
        "market_regime": "positiv",
        "reasons": ["Momentum", "Relative Staerke"],
        "quote": {"last_price": 100.0, "currency": "USD", "timestamp": proposal_ts},
        "timestamp": proposal_ts,
    }
    write_json(proposal_path, proposal_payload)

    ticket_path = root / "data" / "virus_bridge" / "trade_candidates" / day_tag / f"ticket_{ticket_id}.json"
    ticket_payload = {
        "ticket_id": ticket_id,
        "source_proposal_id": proposal_id,
        "asset": {"symbol": "AMD", "isin": "US0079031078", "name": "Advanced Micro Devices"},
        "direction": "long",
        "last_price": 100.0,
        "currency": "USD",
        "decision": "APPROVED",
        "signal_strength": "hoch",
        "market_regime": "positiv",
        "score": 7.1,
        "reasons": ["Momentum", "Relative Staerke"],
        "tr_verified": True,
        "market_status": {"is_open": True, "market": "NASDAQ", "next_open_hint": "15:30 Uhr"},
        "size_min_eur": 900.0,
        "size_max_eur": 1200.0,
        "suggested_eur": 1000.0,
        "entry_hint": "Einstieg nur bei bestaetigter Staerke beobachten.",
        "stop_loss_hint": "Stop-Loss unter letztem Ruecksetzer pruefen.",
        "stop_hint": "Stop-Loss unter letztem Ruecksetzer pruefen.",
        "stop_method": "fallback",
        "stop_loss_price": 97.0,
        "stop_distance_pct": 3.0,
        "risk_eur": 30.0,
        "quote_age_minutes": 10.0,
        "data_fresh": True,
        "next_step": "Nur handeln, wenn Einstieg, Stop-Loss und Risiko fuer dich sauber passen.",
        "timestamp": ticket_ts,
        "operational_status": "OPERATIV_NUTZBAR",
        "operational_is_actionable": True,
        "operational_missing_fields": [],
        "operational_missing_labels": [],
        "demo_label": DEMO_LABEL,
        "demo_note": DEMO_NOTE,
    }
    write_json(ticket_path, ticket_payload)

    execution_path = root / "data" / "virus_bridge" / "executions" / day_tag / f"execution_{ticket_id}.json"
    execution_payload = {
        "ticket_id": ticket_id,
        "status": "EXECUTED",
        "buy_price": 100.0,
        "size_eur": 1000.0,
        "executed_at": execution_ts,
        "source": "demo_seed",
        "demo_label": DEMO_LABEL,
        "demo_note": DEMO_NOTE,
    }
    write_json(execution_path, execution_payload)

    exit_path = root / "data" / "virus_bridge" / "exits" / day_tag / f"exit_{ticket_id}_{day_tag}T184500_000000.json"
    exit_payload = {
        "ticket_id": ticket_id,
        "exit_type": "FULL",
        "exit_reason": "TARGET_REACHED",
        "exit_price": 112.0,
        "size_eur": 1000.0,
        "exit_quantity": 10.0,
        "entry_price": 100.0,
        "entry_size_eur": 1000.0,
        "remaining_size_eur_before": 1000.0,
        "remaining_size_eur_after": 0.0,
        "direction": "long",
        "exit_note": "DEMO_ONLY: Ziel fuer Trockenlauf erreicht.",
        "closed_fraction": 1.0,
        "realized_pnl_eur": 120.0,
        "realized_pnl_pct": 12.0,
        "timestamp": exit_ts,
        "demo_label": DEMO_LABEL,
        "demo_note": DEMO_NOTE,
    }
    write_json(exit_path, exit_payload)

    state_path = root / "data" / "virus_bridge" / "ticket_state.json"
    state_payload = {
        "tickets": {
            ticket_id: {
                "status": "CLOSED",
                "entry_price": 100.0,
                "entry_size_eur": 1000.0,
                "remaining_size_eur": 0.0,
                "asset_name": "Advanced Micro Devices",
                "last_updated": exit_ts,
                "demo_label": DEMO_LABEL,
            }
        },
        "active_by_chat": {},
        "demo_label": DEMO_LABEL,
    }
    write_json(state_path, state_payload)

    lifecycle_path = root / "data" / "virus_bridge" / "ticket_lifecycle" / f"{ticket_id}.json"
    lifecycle_payload = {
        "ticket_id": ticket_id,
        "source_proposal_id": proposal_id,
        "asset": {"symbol": "AMD", "isin": "US0079031078", "name": "Advanced Micro Devices"},
        "created_at": proposal_ts,
        "events": [
            _event(
                "TRADE_CANDIDATE_CREATED",
                proposal_ts,
                {"ticket_id": ticket_id, "source_proposal_id": proposal_id, "asset": ticket_payload["asset"], "status": "CREATED", "decision": "APPROVED"},
            ),
            _event(
                "TRADE_TICKET_SENT",
                ticket_ts,
                {"ticket_id": ticket_id, "source_proposal_id": proposal_id, "asset": ticket_payload["asset"], "status": "SENT", "decision": "APPROVED"},
            ),
            _event(
                "TRADE_EXECUTED_MANUAL",
                execution_ts,
                {"ticket_id": ticket_id, "source_proposal_id": proposal_id, "asset": ticket_payload["asset"], "status": "EXECUTED", "decision": "APPROVED", "buy_price": 100.0, "size_eur": 1000.0},
            ),
            _event(
                "TRADE_CLOSED_TARGET_REACHED",
                exit_ts,
                {
                    "ticket_id": ticket_id,
                    "source_proposal_id": proposal_id,
                    "asset": ticket_payload["asset"],
                    "status": "CLOSED",
                    "decision": "APPROVED",
                    "size_eur": 1000.0,
                    "exit_price": 112.0,
                    "exit_reason": "TARGET_REACHED",
                    "closed_fraction": 1.0,
                    "realized_pnl_eur": 120.0,
                    "realized_pnl_pct": 12.0,
                },
            ),
        ],
        "current_status": "CLOSED",
        "last_updated": exit_ts,
        "demo_label": DEMO_LABEL,
        "demo_note": DEMO_NOTE,
    }
    write_json(lifecycle_path, lifecycle_payload)

    recommendations_path = root / "data" / "v2" / f"recommendations_{day_tag}_0900.json"
    recommendations_payload = {
        "generated_at": quote_ts,
        "recommendations": [
            {
                "symbol": "AMD",
                "isin": "US0079031078",
                "name": "Advanced Micro Devices",
                "classification": "KAUFEN PRUEFEN",
                "regime": "positiv",
                "opportunity_score": {"total_score": 7.1},
                "demo_label": DEMO_LABEL,
            }
        ],
    }
    write_json(recommendations_path, recommendations_payload)

    candidates_path = root / "data" / "v2" / f"candidates_{day_tag}_2100.json"
    candidates_payload = {
        "generated_at": quote_ts,
        "candidates": [
            {
                "symbol": "AMD",
                "isin": "US0079031078",
                "quote": {"price": 112.0, "currency": "USD", "timestamp": quote_ts},
                "demo_label": DEMO_LABEL,
            }
        ],
    }
    write_json(candidates_path, candidates_payload)

    snapshot_path = root / "data" / "snapshots" / f"portfolio_{day_tag}_demo.json"
    snapshot_payload = {
        "asof": now.strftime("%d.%m.%Y"),
        "computed_total_eur": 15250.0,
        "cash_eur": 4250.0,
        "validation_status": "demo_seed",
        "run_id": f"demo-{day_tag}",
        "positions": [
            {"isin": "DE000BAY0017", "symbol": "BAYN.DE", "name": "Bayer AG", "quantity": 20, "price_eur": 25.0, "market_value_eur": 500.0},
            {"isin": "DE000ENER6Y0", "symbol": "ENR.DE", "name": "Siemens Energy", "quantity": 30, "price_eur": 35.0, "market_value_eur": 1050.0},
        ],
        "demo_label": DEMO_LABEL,
        "demo_note": DEMO_NOTE,
    }
    write_json(snapshot_path, snapshot_payload)
    _set_mtime(snapshot_path, now - timedelta(minutes=10))

    execution_report = build_execution_report(cfg)
    execution_report_path = write_execution_report(execution_report, cfg)
    monthly = build_and_write_monthly_evaluation(cfg, month_period)

    portfolio_text = render_portfolio_status(cfg)
    execution_text = render_execution_summary(cfg)
    organism_text = render_organism_text(cfg, month_period)
    summary_path = root / "output" / "demo_summary.txt"
    summary_path.write_text(
        "\n\n".join(
            [
                f"{DEMO_LABEL}\n{DEMO_NOTE}",
                "PORTFOLIO\n" + portfolio_text,
                "EXECUTION\n" + execution_text,
                "ORGANISM\n" + organism_text,
            ]
        ),
        encoding="utf-8",
    )

    info_path = root / "DEMO_README.md"
    info_path.write_text(
        "\n".join(
            [
                f"# {DEMO_LABEL}",
                "",
                DEMO_NOTE,
                "",
                "Diese Demo-Root ist vom aktiven Produktivpfad getrennt.",
                "Sie dient nur fuer lokale Trockenlaeufe und erste Operator-Checks.",
                "",
                "Wichtige Dateien:",
                f"- Proposal: `{proposal_path.relative_to(root)}`",
                f"- Execution: `{execution_path.relative_to(root)}`",
                f"- Exit: `{exit_path.relative_to(root)}`",
                f"- Portfolio-Snapshot: `{snapshot_path.relative_to(root)}`",
                f"- Execution-Report: `{Path(execution_report_path).relative_to(root)}`",
                f"- Monatsreport: `{Path(monthly['path']).relative_to(root)}`",
                f"- Text-Summary: `{summary_path.relative_to(root)}`",
            ]
        ),
        encoding="utf-8",
    )

    return {
        "demo_label": DEMO_LABEL,
        "target_root": str(root),
        "period": month_period,
        "ticket_id": ticket_id,
        "proposal_id": proposal_id,
        "paths": {
            "proposal": str(proposal_path),
            "trade_candidate": str(ticket_path),
            "execution": str(execution_path),
            "exit": str(exit_path),
            "ticket_state": str(state_path),
            "ticket_lifecycle": str(lifecycle_path),
            "portfolio_snapshot": str(snapshot_path),
            "execution_report": str(execution_report_path),
            "monthly_report": str(monthly["path"]),
            "summary_text": str(summary_path),
            "demo_readme": str(info_path),
        },
        "texts": {
            "portfolio": portfolio_text,
            "execution": execution_text,
            "organism": organism_text,
        },
    }
