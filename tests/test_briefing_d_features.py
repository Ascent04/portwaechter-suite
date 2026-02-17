from __future__ import annotations

from pathlib import Path

from modules.briefing.delta import compute_delta, find_previous_briefing, load_previous_briefing
from modules.briefing.helpers import briefing_text
from modules.briefing.regime import compute_market_regime
from modules.briefing.volume_lights import compute_volume_light, load_volume_baseline
def test_delta_no_previous_briefing(tmp_path: Path) -> None:
    prev = find_previous_briefing(tmp_path, 7)
    assert prev is None
    curr = {"positions": [], "top_opportunities": []}
    delta = compute_delta(load_previous_briefing(prev), curr)
    assert delta["status"] == "no_previous_briefing"


def test_volume_light_gray_when_baseline_missing() -> None:
    baseline = load_volume_baseline("/tmp/does-not-exist-volume-baseline.json")
    light = compute_volume_light("DE000BASF111", 1000.0, baseline, {"min_volume_points": 20})
    assert light["light"] == "gray"


def test_volume_light_ratio_with_baseline() -> None:
    baseline = {"DE000BASF111": {"volumes_last_n": [100, 100, 100, 100, 100]}}
    light = compute_volume_light(
        "DE000BASF111",
        180.0,
        baseline,
        {"green_ratio": 2.0, "yellow_ratio": 1.3, "min_volume_points": 3},
    )
    assert light["light"] == "yellow"
    assert light["ratio"] == 1.8


def test_regime_switches() -> None:
    positions = [{"isin": "A", "pnl_pct": 1.0}, {"isin": "B", "pnl_pct": 2.0}, {"isin": "C", "pnl_pct": -1.0}]
    cfg = {"briefing": {"morning": {"regime": {"risk_on_min": 2, "risk_off_min": 2}}}}
    risk_on = compute_market_regime(positions, [{"direction": "up"}, {"direction": "up"}], cfg)
    risk_off = compute_market_regime(positions, [{"direction": "down"}, {"direction": "down"}], cfg)
    neutral = compute_market_regime(positions, [], cfg)
    assert risk_on["regime"] == "risk_on"
    assert risk_off["regime"] == "risk_off"
    assert neutral["regime"] == "neutral"


def test_telegram_text_contains_new_blocks_and_limit(tmp_path: Path) -> None:
    briefing = {
        "holdings_block": {"top_winners": [{"name": "BASF", "pnl_pct": 2.5}], "top_losers": [{"name": "Bayer", "pnl_pct": -1.8}], "total_pnl_pct": 0.3},
        "holdings_signals": [],
        "top_opportunities": [{"name": "Deutz", "reason": "Volumenauffälligkeit", "opportunity_score": 7, "confidence": "hoch"}],
        "delta": {"status": "no_previous_briefing", "positions_delta": {}, "radar_delta": {}},
        "regime": {"regime": "neutral", "facts": {"up_strong": 1, "down_strong": 0, "pct_up": 0.57}},
        "volume_lights": {"holdings": [{"light": "green", "ratio": 2.3}]},
    }
    text = briefing_text(briefing)
    assert "Volumen:" in text
    assert "Delta" in text
    assert "Regime" in text
    assert len(text) < 3500
