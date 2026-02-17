from __future__ import annotations

from modules.risk.position_sizing import adjust_position_size, compute_volatility, recommended_position_multiplier


def test_high_volatility_reduces_multiplier() -> None:
    outcomes = [{"r_pct": 3.0}, {"r_pct": -2.5}, {"r_pct": 2.9}, {"r_pct": -3.2}]
    vol = compute_volatility(outcomes)
    mult = recommended_position_multiplier(vol, "neutral")
    assert vol > 1.5
    assert mult < 1.0


def test_risk_off_reduces_multiplier() -> None:
    mult = recommended_position_multiplier(0.5, "risk_off")
    assert mult == 0.6


def test_clamp_and_adjust_position_size() -> None:
    m_low = recommended_position_multiplier(999, "risk_off")
    m_high = recommended_position_multiplier(-1, "risk_on")
    assert 0.4 <= m_low <= 1.2
    assert 0.4 <= m_high <= 1.2
    assert adjust_position_size(1000, m_low) == round(1000 * m_low, 6)
