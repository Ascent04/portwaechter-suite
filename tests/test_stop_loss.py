from __future__ import annotations

from modules.virus_bridge.stop_loss import compute_risk_eur, compute_stop_distance_pct, derive_stop_loss


def test_stop_loss_for_long_quote() -> None:
    result = derive_stop_loss({"direction": "long"}, {"last_price": 100.0}, {})
    assert result == {
        "stop_loss_hint": "Stop-Loss unterhalb des letzten Ruecksetzers pruefen",
        "stop_loss_price": 97.0,
        "stop_method": "fallback",
    }


def test_stop_distance_and_risk_eur() -> None:
    assert compute_stop_distance_pct(100.0, 97.0) == 3.0
    assert compute_risk_eur(875.0, 3.0) == 26.25


def test_stop_loss_uses_explicit_structure_price() -> None:
    result = derive_stop_loss(
        {"direction": "long", "structure_stop_price": 94.25},
        {"last_price": 100.0},
        {},
    )
    assert result == {
        "stop_loss_hint": "Stop-Loss an explizitem Struktur-Niveau pruefen",
        "stop_loss_price": 94.25,
        "stop_method": "structure",
    }


def test_stop_loss_uses_pullback_level_from_nested_details() -> None:
    result = derive_stop_loss(
        {"direction": "long", "details": {"technical": {"last_pullback_low": 96.4}}},
        {"price": 100.0},
        {},
    )
    assert result == {
        "stop_loss_hint": "Stop-Loss unter letztem Ruecksetzer pruefen",
        "stop_loss_price": 96.4,
        "stop_method": "structure",
    }


def test_stop_loss_ignores_invalid_structure_level_and_falls_back() -> None:
    result = derive_stop_loss(
        {"direction": "long", "last_pullback_low": 101.0},
        {"last_price": 100.0},
        {},
    )
    assert result == {
        "stop_loss_hint": "Stop-Loss unterhalb des letzten Ruecksetzers pruefen",
        "stop_loss_price": 97.0,
        "stop_method": "fallback",
    }


def test_stop_loss_too_tight_structure_falls_back() -> None:
    result = derive_stop_loss(
        {"direction": "long", "last_swing_low": 99.6},
        {"last_price": 100.0},
        {},
    )
    assert result == {
        "stop_loss_hint": "Stop-Loss unterhalb des letzten Ruecksetzers pruefen",
        "stop_loss_price": 97.0,
        "stop_method": "fallback",
    }


def test_stop_loss_too_wide_structure_falls_back() -> None:
    result = derive_stop_loss(
        {"direction": "long", "last_swing_low": 88.0},
        {"last_price": 100.0},
        {},
    )
    assert result == {
        "stop_loss_hint": "Stop-Loss unterhalb des letzten Ruecksetzers pruefen",
        "stop_loss_price": 97.0,
        "stop_method": "fallback",
    }


def test_stop_loss_borderline_tight_structure_falls_back_with_defensive_default() -> None:
    result = derive_stop_loss(
        {"direction": "long", "last_swing_low": 98.7},
        {"last_price": 100.0},
        {},
    )
    assert result == {
        "stop_loss_hint": "Stop-Loss unterhalb des letzten Ruecksetzers pruefen",
        "stop_loss_price": 97.0,
        "stop_method": "fallback",
    }


def test_stop_loss_borderline_wide_structure_falls_back_with_defensive_default() -> None:
    result = derive_stop_loss(
        {"direction": "long", "last_swing_low": 93.6},
        {"last_price": 100.0},
        {},
    )
    assert result == {
        "stop_loss_hint": "Stop-Loss unterhalb des letzten Ruecksetzers pruefen",
        "stop_loss_price": 97.0,
        "stop_method": "fallback",
    }


def test_stop_loss_for_short_can_use_structure_high() -> None:
    result = derive_stop_loss(
        {"direction": "short", "structure": {"short": {"last_swing_high": 103.2}}},
        {"last_price": 100.0},
        {},
    )
    assert result == {
        "stop_loss_hint": "Stop-Loss ueber letztem Swing-Hoch pruefen",
        "stop_loss_price": 103.2,
        "stop_method": "structure",
    }


def test_stop_loss_handles_missing_quote() -> None:
    result = derive_stop_loss({"direction": "long"}, None, {})
    assert result["stop_loss_price"] is None
    assert result["stop_loss_hint"] == "Stop-Loss manuell pruefen"
    assert result["stop_method"] == "manual"
