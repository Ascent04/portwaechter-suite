from __future__ import annotations

from pathlib import Path

from modules.common.utils import write_json
from modules.marketdata_watcher.grouping import classify_isin, load_holdings_isins


def test_holdings_detected_from_snapshot(tmp_path: Path) -> None:
    cfg = {"app": {"root_dir": str(tmp_path)}}
    write_json(
        tmp_path / "data" / "snapshots" / "portfolio_20260218.json",
        {"positions": [{"isin": "DE000BASF111"}, {"isin": "DE000BAY0017"}]},
    )

    out = load_holdings_isins(cfg)

    assert "DE000BASF111" in out
    assert classify_isin("DE000BASF111", out) == "holdings"


def test_missing_snapshot_defaults_to_radar(tmp_path: Path) -> None:
    cfg = {"app": {"root_dir": str(tmp_path)}}
    out = load_holdings_isins(cfg)

    assert out == set()
    assert classify_isin("DE000ENER6Y0", out) == "radar"
