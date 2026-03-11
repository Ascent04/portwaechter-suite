from __future__ import annotations

from modules.virus_bridge.exit_flow import compute_realized_pnl


def test_compute_realized_pnl_for_long_position() -> None:
    result = compute_realized_pnl(100.0, 110.0, 500.0, direction="long")
    assert result["realized_pnl_pct"] == 10.0
    assert result["realized_pnl_eur"] == 50.0


def test_compute_realized_pnl_handles_missing_values() -> None:
    result = compute_realized_pnl(None, 110.0, 500.0, direction="long")
    assert result["realized_pnl_pct"] is None
    assert result["realized_pnl_eur"] is None
