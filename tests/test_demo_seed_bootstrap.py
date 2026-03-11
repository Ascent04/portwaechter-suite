from __future__ import annotations

from pathlib import Path

import pytest

from modules.common.demo_seed import bootstrap_demo_runtime
from modules.organism.report_render import render_organism_text
from modules.portfolio_status.status import render_portfolio_status
from modules.virus_bridge.execution_report import render_execution_summary


def test_demo_seed_bootstrap_builds_separate_runtime_and_reports(tmp_path: Path) -> None:
    demo_root = tmp_path / "demo_runtime"

    result = bootstrap_demo_runtime(demo_root, clean=True)

    assert result["demo_label"] == "DEMO_ONLY"
    assert Path(result["paths"]["proposal"]).exists()
    assert Path(result["paths"]["execution"]).exists()
    assert Path(result["paths"]["exit"]).exists()
    assert Path(result["paths"]["ticket_lifecycle"]).exists()
    assert Path(result["paths"]["execution_report"]).exists()
    assert Path(result["paths"]["monthly_report"]).exists()
    assert Path(result["paths"]["summary_text"]).exists()

    cfg = {
        "app": {"root_dir": str(demo_root), "timezone": "Europe/Berlin"},
        "hedgefund": {"budget_eur": 5000, "max_risk_per_trade_pct": 1.0},
        "integration": {"bridge": {"proposal_dir": "data/integration/signal_proposals", "consumed_dir": "data/integration/consumed"}},
        "v2": {"data_dir": "data/v2"},
        "data_quality": {"max_quote_age_minutes": 30},
        "organism_evaluation": {"monthly_cost_usd": 30.0, "eurusd_rate_assumption": 0.92},
        "paths": {"audit_jsonl": str(demo_root / "data" / "audit" / "portfolio_audit.jsonl")},
    }

    execution_text = render_execution_summary(cfg)
    portfolio_text = render_portfolio_status(cfg)
    organism_text = render_organism_text(cfg, result["period"])

    assert "Echte Ausfuehrungen:\n1" in execution_text
    assert "Geschlossene Trades:\n1" in execution_text
    assert "KOSTENSTATUS:\nKOSTEN_GEDECKT" in execution_text
    assert "DEPOTAUSZUG" in portfolio_text
    assert "Echte Ausfuehrungen: 1" in organism_text
    assert "Bewertbare Exits: 1" in organism_text


def test_demo_seed_bootstrap_rejects_repo_root_target() -> None:
    with pytest.raises(ValueError, match="target_root_must_not_be_repo_root"):
        bootstrap_demo_runtime("/opt/portwaechter", clean=False)
