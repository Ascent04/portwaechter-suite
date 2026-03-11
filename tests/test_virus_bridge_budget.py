from __future__ import annotations

from modules.virus_bridge.budget import get_budget_context, suggest_position_size


def _cfg() -> dict:
    return {
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
        }
    }


def test_budget_context_and_sizing_ranges() -> None:
    ctx = get_budget_context(_cfg())
    high = suggest_position_size({"classification": "KAUFIDEE_PRUEFEN", "signal_strength": "hoch", "score": 8.4}, _cfg())
    medium = suggest_position_size({"classification": "KAUFIDEE_PRUEFEN", "signal_strength": "mittel", "score": 6.5}, _cfg())
    speculative = suggest_position_size({"classification": "KAUFIDEE_PRUEFEN", "signal_strength": "spekulativ", "score": 4.5}, _cfg())

    assert ctx["budget_eur"] == 5000.0
    assert ctx["max_positions"] == 3
    assert high == {"size_min_eur": 1000.0, "size_max_eur": 1500.0, "suggested_eur": 1375.0}
    assert medium == {"size_min_eur": 750.0, "size_max_eur": 1000.0, "suggested_eur": 875.0}
    assert speculative == {"size_min_eur": 0.0, "size_max_eur": 500.0, "suggested_eur": 125.0}
