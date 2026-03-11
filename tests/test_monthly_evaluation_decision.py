from __future__ import annotations

from modules.organism.monthly_evaluation import evaluate_organism


def _cfg() -> dict:
    return {
        "organism_evaluation": {"monthly_cost_usd": 29, "eurusd_rate_assumption": 0.92},
        "api_governor": {"minute_limit_hard": 55},
    }


def test_monthly_decision_without_real_trades_but_stable_ops_is_ueberpruefen() -> None:
    report = {
        "activity": {"kaufen_pruefen_total": 12, "verkaufen_pruefen_total": 3, "executed_total": 0},
        "performance": {"realized_pnl_eur_total": 0.0, "win_rate_closed": None},
        "api": {"blocked_runs_total": 0, "degraded_runs_total": 0, "max_calls_in_minute_seen": 18.0},
        "economics": {"realized_pnl_minus_cost_eur": -26.68},
    }

    evaluation = evaluate_organism(report, _cfg())

    assert evaluation["organism_status"] == "UEBERPRUEFEN"
    assert "Keine echten manuellen Echtgeld-Ausfuehrungen" in evaluation["reasons"][0]
    assert "eingeschraenkte Leistungsbewertung" in evaluation["summary"]
    assert "Technik und Prozess" in evaluation["summary"]


def test_monthly_decision_uses_real_execution_count_from_economics_when_available() -> None:
    report = {
        "activity": {"kaufen_pruefen_total": 6, "verkaufen_pruefen_total": 2, "executed_total": 0},
        "performance": {"realized_pnl_eur_total": -10.0, "win_rate_closed": 0.0},
        "api": {"blocked_runs_total": 0, "degraded_runs_total": 0, "max_calls_in_minute_seen": 20.0},
        "economics": {"executed_entries_count": 1, "realized_pnl_minus_cost_eur": -36.68},
    }

    evaluation = evaluate_organism(report, _cfg())

    assert evaluation["organism_status"] == "GEDROSSELT_FUEHREN"


def test_monthly_decision_without_real_trades_but_with_api_stress_is_gedrosselt() -> None:
    report = {
        "activity": {"kaufen_pruefen_total": 20, "verkaufen_pruefen_total": 4, "executed_total": 0},
        "performance": {"realized_pnl_eur_total": 0.0, "win_rate_closed": None},
        "api": {"blocked_runs_total": 1, "degraded_runs_total": 3, "max_calls_in_minute_seen": 105.0},
        "economics": {"realized_pnl_minus_cost_eur": -26.68},
    }

    evaluation = evaluate_organism(report, _cfg())

    assert evaluation["organism_status"] == "GEDROSSELT_FUEHREN"
    assert any("API-Druck" in reason or "budgetkritische" in reason for reason in evaluation["reasons"])
    assert "API-Druck" in evaluation["summary"]


def test_monthly_decision_with_real_trades_and_weak_performance_is_gedrosselt() -> None:
    report = {
        "activity": {"kaufen_pruefen_total": 4, "verkaufen_pruefen_total": 2, "executed_total": 1},
        "performance": {"realized_pnl_eur_total": -10.0, "win_rate_closed": 0.0},
        "api": {"blocked_runs_total": 0, "degraded_runs_total": 0, "max_calls_in_minute_seen": 20.0},
        "economics": {"realized_pnl_minus_cost_eur": -36.68},
    }

    evaluation = evaluate_organism(report, _cfg())

    assert evaluation["organism_status"] == "GEDROSSELT_FUEHREN"
    assert any("Performance" in reason or "Ausfuehrungen" in reason for reason in evaluation["reasons"])
    assert "Real-Performance" in evaluation["summary"]


def test_monthly_decision_marks_high_quality_month_as_ausbauen() -> None:
    report = {
        "activity": {"kaufen_pruefen_total": 5, "verkaufen_pruefen_total": 2, "executed_total": 3},
        "performance": {"realized_pnl_eur_total": 180.0, "win_rate_closed": 66.0},
        "api": {"blocked_runs_total": 0, "degraded_runs_total": 1, "max_calls_in_minute_seen": 25.0},
        "economics": {"realized_pnl_minus_cost_eur": 153.32, "cost_coverage_status": "KOSTEN_GEDECKT"},
    }

    evaluation = evaluate_organism(report, _cfg())

    assert evaluation["organism_status"] == "AUSBAUEN"
    assert "Positive realisierte Performance" in evaluation["reasons"]
