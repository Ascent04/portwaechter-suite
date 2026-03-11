from __future__ import annotations

from modules.common.utils import write_json
from modules.virus_bridge.risk_eval import evaluate_proposal


def _cfg(tmp_path) -> dict:
    return {
        "app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"},
        "virus_bridge": {"tr_universe_path": "config/universe_tr_verified.json"},
        "data_quality": {"max_quote_age_minutes": 15},
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


def _proposal(**overrides) -> dict:
    base = {
        "classification": "KAUFIDEE_PRUEFEN",
        "asset": {"symbol": "AMD", "isin": "US0079031078", "name": "Advanced Micro Devices"},
        "score": 7.2,
        "signal_strength": "hoch",
        "market_regime": "positiv",
        "reasons": ["Momentum"],
        "timestamp": "2026-03-10T16:00:00+01:00",
        "quote": {"last_price": 197.69, "currency": "USD", "timestamp": "2026-03-10T16:00:00+01:00"},
    }
    base.update(overrides)
    return base


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


def test_strong_proposal_is_approved(tmp_path) -> None:
    _write_universe(tmp_path)
    result = evaluate_proposal(_proposal(), _cfg(tmp_path))

    assert result["decision"] == "APPROVED"
    assert result["suggested_eur"] >= 1000
    assert result["stop_loss_price"] == 191.76
    assert result["stop_distance_pct"] == 3.0
    assert result["risk_eur"] == 37.5
    assert result["data_fresh"] is True


def test_structure_based_stop_is_used_when_explicitly_available(tmp_path) -> None:
    _write_universe(tmp_path)
    result = evaluate_proposal(_proposal(structure_stop_price=190.0), _cfg(tmp_path))

    assert result["decision"] == "APPROVED"
    assert result["stop_loss_price"] == 190.0
    assert result["stop_method"] == "structure"
    assert result["stop_distance_pct"] == 3.89
    assert result["risk_eur"] == 48.63


def test_implausibly_wide_structure_stop_falls_back(tmp_path) -> None:
    _write_universe(tmp_path)
    result = evaluate_proposal(_proposal(last_swing_low=150.0), _cfg(tmp_path))

    assert result["decision"] == "APPROVED"
    assert result["stop_method"] == "fallback"
    assert result["stop_loss_price"] == 191.76
    assert result["stop_distance_pct"] == 3.0
    assert result["risk_eur"] == 37.5


def test_speculative_weak_proposal_is_rejected(tmp_path) -> None:
    _write_universe(tmp_path)
    result = evaluate_proposal(_proposal(signal_strength="spekulativ", score=5.5), _cfg(tmp_path))

    assert result["decision"] == "REJECTED"
    assert "Spekulatives Signal unter Mindestscore" in result["reasons"]


def test_defensive_market_reduces_proposal(tmp_path) -> None:
    _write_universe(tmp_path)
    result = evaluate_proposal(_proposal(signal_strength="mittel", score=6.4, market_regime="defensiv"), _cfg(tmp_path))

    assert result["decision"] == "REDUCED"
    assert "Defensive Marktlage" in result["reasons"]


def test_stale_quote_blocks_approved(tmp_path) -> None:
    _write_universe(tmp_path)
    result = evaluate_proposal(
        _proposal(
            quote={"last_price": 197.69, "currency": "USD", "timestamp": "2026-03-10T15:20:00+01:00"},
            timestamp="2026-03-10T16:00:00+01:00",
        ),
        _cfg(tmp_path),
    )

    assert result["decision"] == "REDUCED"
    assert result["data_fresh"] is False
    assert "Kursdaten nicht frisch" in result["reasons"]
    assert result["suggested_eur"] == 937.5


def test_borderline_score_is_reduced_for_quality_control(tmp_path) -> None:
    _write_universe(tmp_path)
    result = evaluate_proposal(_proposal(score=6.4, signal_strength="hoch"), _cfg(tmp_path))

    assert result["decision"] == "REDUCED"
    assert "Score nur im Grenzbereich" in result["reasons"]
    assert result["suggested_eur"] == 1062.5


def test_risk_budget_caps_suggested_size_when_stop_is_wider(tmp_path) -> None:
    _write_universe(tmp_path)
    result = evaluate_proposal(_proposal(score=8.4, structure_stop_price=190.0), _cfg(tmp_path))

    assert result["decision"] == "APPROVED"
    assert "Groesse an das Risikobudget angepasst" in result["reasons"]
    assert result["suggested_eur"] == 1285.35
    assert result["risk_eur"] == 50.0


def test_stale_wider_stop_does_not_apply_extra_risk_cap_after_size_reduction(tmp_path) -> None:
    _write_universe(tmp_path)
    result = evaluate_proposal(
        _proposal(
            score=8.4,
            structure_stop_price=190.0,
            quote={"last_price": 197.69, "currency": "USD", "timestamp": "2026-03-10T15:20:00+01:00"},
            timestamp="2026-03-10T16:00:00+01:00",
        ),
        _cfg(tmp_path),
    )

    assert result["decision"] == "REDUCED"
    assert "Kursdaten nicht frisch" in result["reasons"]
    assert "Groesse an das Risikobudget angepasst" not in result["reasons"]
    assert result["suggested_eur"] == 1031.25
    assert result["risk_eur"] == 40.12


def test_too_small_suggested_size_is_rejected(tmp_path) -> None:
    _write_universe(tmp_path)
    result = evaluate_proposal(_proposal(signal_strength="spekulativ", score=6.2), _cfg(tmp_path))

    assert result["decision"] == "REJECTED"
    assert "Vorgeschlagene Groesse zu klein fuer ein operatives Ticket" in result["reasons"]


def test_closed_market_moves_signal_to_pending_market_open(tmp_path) -> None:
    _write_universe(tmp_path)
    result = evaluate_proposal(
        _proposal(timestamp="2026-03-10T22:05:00+01:00", quote={"last_price": 197.69, "currency": "USD", "timestamp": "2026-03-10T22:05:00+01:00"}),
        _cfg(tmp_path),
    )

    assert result["decision"] == "PENDING_MARKET_OPEN"
    assert "Markt aktuell geschlossen" in result["reasons"]


def test_max_positions_and_exposure_can_block_proposal(tmp_path) -> None:
    _write_universe(tmp_path)
    write_json(
        tmp_path / "data" / "virus_bridge" / "open_positions.json",
        {
            "positions": [
                {"suggested_eur": 1200},
                {"suggested_eur": 1200},
                {"suggested_eur": 900},
            ]
        },
    )

    result = evaluate_proposal(_proposal(signal_strength="mittel", score=6.8), _cfg(tmp_path))

    assert result["decision"] == "REJECTED"
    assert "Maximale Positionszahl erreicht" in result["reasons"]
