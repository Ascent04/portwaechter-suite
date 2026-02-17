from __future__ import annotations

from modules.setup_engine.planner import build_setup, handle_approval_command, risk_budget


def test_risk_budget_with_placeholders_uses_defaults() -> None:
    cfg = {"decision": {"max_risk_per_trade_pct": "{{MAX_RISK_PER_TRADE_PCT}}", "portfolio_value_eur": "{{PORTFOLIO_VALUE_EUR}}"}}
    budget = risk_budget(cfg)
    assert budget["risk_pct"] == 0.75
    assert budget["risk_eur"] is None


def test_build_setup_manual_when_marketdata_missing() -> None:
    cfg = {"app": {"timezone": "Europe/Berlin"}, "decision": {}}
    candidate = {"isin": "DE000BASF111", "name": "BASF", "direction": "up", "score": 7, "bucket": "SETUP"}
    setup = build_setup(candidate, {}, cfg)
    assert setup["entry_zone"] == "manual_required"
    assert setup["status"] == "pending_approval"


def test_handle_approval_invalid_command() -> None:
    cfg = {"app": {"root_dir": "/tmp"}}
    out = handle_approval_command("HELLO", cfg)
    assert out["status"] == "ignored"
