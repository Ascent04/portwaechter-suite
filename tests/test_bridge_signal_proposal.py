from __future__ import annotations

from pathlib import Path

from modules.integration.pw_to_virus import build_signal_proposal, export_action_candidates_to_bridge
from modules.common.utils import read_json


def _cfg(tmp_path: Path) -> dict:
    return {
        "app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"},
        "integration": {"bridge": {"proposal_dir": "data/integration/signal_proposals", "consumed_dir": "data/integration/consumed", "default_budget_eur": 5000}},
    }


def _action_candidate() -> dict:
    return {
        "symbol": "AMD",
        "isin": "US0079031078",
        "name": "Advanced Micro Devices",
        "classification": "ACTION",
        "group": "scanner",
        "regime": "risk_on",
        "weight_pct": 0.0,
        "opportunity_score": {
            "total_score": 7.2,
            "confidence": "hoch",
            "reasons": ["momentum", "volume", "positive_setup_expectancy"],
        },
    }


def test_action_candidate_is_translated_to_signal_proposal(tmp_path: Path) -> None:
    proposal = build_signal_proposal(_action_candidate(), _cfg(tmp_path))

    assert proposal["proposal_id"].startswith("PWV2-")
    assert proposal["source"] == "portwaechter_v2"
    assert proposal["classification"] == "KAUFIDEE_PRUEFEN"
    assert proposal["direction"] == "long"
    assert proposal["asset"]["symbol"] == "AMD"
    assert proposal["score"] == 7.2
    assert proposal["signal_strength"] == "hoch"
    assert proposal["market_regime"] == "positiv"
    assert proposal["reasons"] == ["Momentum", "Ungewoehnlich hohes Volumen", "Positive Setup-Historie"]
    assert proposal["budget_context"]["budget_eur"] == 5000.0


def test_only_action_candidates_are_exported(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    written = export_action_candidates_to_bridge(
        [
            _action_candidate(),
            {"classification": "WATCH", "symbol": "BAYN.DE", "name": "Bayer AG"},
            {"classification": "DEFENSE", "symbol": "DEZ.DE", "name": "DEUTZ AG"},
        ],
        cfg,
    )

    assert len(written) == 1
    proposal_path = Path(written[0])
    assert proposal_path.exists()
    payload = read_json(proposal_path)
    assert payload["classification"] == "KAUFIDEE_PRUEFEN"
