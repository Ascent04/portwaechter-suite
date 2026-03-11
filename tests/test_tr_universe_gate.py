from __future__ import annotations

from modules.common.utils import write_json
from modules.virus_bridge.risk_eval import evaluate_proposal
from modules.virus_bridge.tr_universe import get_tr_asset_meta, is_tr_verified, load_tr_universe


def _cfg(tmp_path) -> dict:
    return {
        "app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"},
        "virus_bridge": {"tr_universe_path": "config/universe_tr_verified.json"},
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
        },
    }


def _write_universe(tmp_path) -> None:
    write_json(
        tmp_path / "config" / "universe_tr_verified.json",
        {
            "US0079031078": {
                "symbol": "AMD",
                "name": "Advanced Micro Devices",
                "tr_verified": True,
                "asset_type": "stock",
                "market": "NASDAQ",
                "currency": "USD",
            }
        },
    )


def test_tr_universe_lookup_and_verification(tmp_path) -> None:
    _write_universe(tmp_path)
    cfg = _cfg(tmp_path)

    universe = load_tr_universe(cfg)
    meta = get_tr_asset_meta("US0079031078", cfg)

    assert "US0079031078" in universe
    assert meta["market"] == "NASDAQ"
    assert is_tr_verified("US0079031078", None, cfg) is True
    assert is_tr_verified("", "AMD", cfg) is True
    assert is_tr_verified("DE0000000000", "FOO", cfg) is False


def test_unverified_asset_is_rejected(tmp_path) -> None:
    _write_universe(tmp_path)
    cfg = _cfg(tmp_path)

    result = evaluate_proposal(
        {
            "classification": "KAUFIDEE_PRUEFEN",
            "asset": {"symbol": "FOO", "isin": "DE0000000000", "name": "Foo AG"},
            "score": 7.4,
            "signal_strength": "hoch",
            "market_regime": "positiv",
            "reasons": ["Momentum"],
            "timestamp": "2026-03-10T10:30:00+01:00",
        },
        cfg,
    )

    assert result["decision"] == "REJECTED"
    assert result["tr_verified"] is False
    assert "Nicht bei Trade Republic verifiziert" in result["reasons"]
