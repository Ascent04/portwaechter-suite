from __future__ import annotations

from modules.v2.recommendations.render import render_recommendation
from modules.v2.telegram.help import explain_candidate, render_help_text, render_meaning_text, render_top_text
from modules.v2.telegram.notifier import render_watch_bundle


def _rows() -> list[dict]:
    return [
        {
            "name": "Bayer AG",
            "symbol": "BAYN.DE",
            "isin": "DE000BAY0017",
            "classification": "WATCH",
            "regime": "neutral",
            "group": "holding",
            "opportunity_score": {"total_score": 5.5, "confidence": "mittel", "reasons": ["momentum", "relative_strength", "portfolio_priority"]},
            "defense_score": {"defense_score": 1.0, "reasons": []},
        },
        {
            "name": "DEUTZ AG",
            "symbol": "DEZ.DE",
            "isin": "DE0006305006",
            "classification": "DEFENSE",
            "regime": "risk_off",
            "group": "holding",
            "opportunity_score": {"total_score": 0.5, "confidence": "spekulativ", "reasons": []},
            "defense_score": {"defense_score": 6.0, "reasons": ["starker_abverkauf", "grosses_positionsgewicht"]},
        },
    ]


def test_unified_ux_copy_avoids_old_terms() -> None:
    rows = _rows()
    watch_text = render_recommendation(rows[0], "WATCH", {"opportunity": rows[0]["opportunity_score"], "defense": rows[0]["defense_score"], "regime": rows[0]["regime"]})["telegram_text"]
    defense_text = render_recommendation(rows[1], "DEFENSE", {"opportunity": rows[1]["opportunity_score"], "defense": rows[1]["defense_score"], "regime": rows[1]["regime"]})["telegram_text"]
    help_text = render_help_text(rows)
    meaning_text = render_meaning_text(rows)
    top_text = render_top_text(rows)
    why_text = explain_candidate("BAYN.DE", rows)
    bundle_text = render_watch_bundle(rows)

    combined = "\n".join([watch_text, defense_text, help_text, meaning_text, top_text, why_text, bundle_text])

    for old_term in ("WATCH", "ACTION", "DEFENSE", "Confidence", "Regime"):
        assert old_term not in combined
    assert "KAUFEN PRUEFEN" in combined
    assert "HALTEN" in combined
    assert "RISIKO REDUZIEREN" in combined
    assert "VERKAUFEN PRUEFEN" in combined
    assert "Signalstaerke" in combined
    assert "Marktlage" in combined
