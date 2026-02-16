from modules.optimizer_engine.heuristics import propose_rebalance


def test_propose_rebalance_returns_actions() -> None:
    snapshot = {
        "computed_total_eur": 1000,
        "positions": [
            {
                "isin": "DE000TEST001",
                "name": "Alpha AG",
                "market_value_eur": 600,
                "instrument_type": "stock",
            },
            {
                "isin": "DE000TEST002",
                "name": "Beta AG",
                "market_value_eur": 300,
                "instrument_type": "stock",
            },
            {
                "isin": "DE000TEST003",
                "name": "Gamma Derivative",
                "market_value_eur": 100,
                "instrument_type": "derivative",
            },
        ],
    }

    analysis = {
        "concentration": {
            "top3_pct": 100,
        }
    }

    cfg = {
        "optimizer": {
            "rebalance": {
                "max_position_weight_pct": 20,
                "max_top3_weight_pct": 45,
            }
        }
    }

    proposal = propose_rebalance(snapshot, analysis, cfg)

    assert proposal["actions"]
    assert any(action["type"] == "reduce" for action in proposal["actions"])
