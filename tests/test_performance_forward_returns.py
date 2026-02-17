from __future__ import annotations

from modules.performance.forward_returns import compute_forward_returns_for_event


def test_forward_returns_up_and_down() -> None:
    idx = {
        "DE000ENER6Y0": [
            {"date": "2026-02-17", "close": 100.0},
            {"date": "2026-02-18", "close": 102.0},
            {"date": "2026-02-19", "close": 103.0},
            {"date": "2026-02-20", "close": 99.0},
            {"date": "2026-02-21", "close": 101.0},
            {"date": "2026-02-24", "close": 104.0},
        ]
    }
    ev_up = {"ts": "2026-02-17T10:00:00+01:00", "isin": "DE000ENER6Y0", "direction": "up"}
    ev_dn = {"ts": "2026-02-17T10:00:00+01:00", "isin": "DE000ENER6Y0", "direction": "down"}

    up = compute_forward_returns_for_event(ev_up, idx, [1, 3, 5])
    dn = compute_forward_returns_for_event(ev_dn, idx, [1])

    assert up["1d"]["status"] == "ok"
    assert up["1d"]["r_pct"] == 2.0
    assert up["3d"]["r_pct"] == -1.0
    assert up["5d"]["r_pct"] == 4.0
    assert dn["1d"]["r_pct"] == -2.0


def test_forward_returns_unavailable_when_missing_prices() -> None:
    idx = {"US000": [{"date": "2026-02-17", "close": None}]}
    ev = {"ts": "2026-02-17T09:00:00+01:00", "isin": "US000", "direction": "up"}
    out = compute_forward_returns_for_event(ev, idx, [1, 3])
    assert out["1d"]["status"] == "unavailable"
    assert out["3d"]["status"] == "unavailable"
