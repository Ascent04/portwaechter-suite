from __future__ import annotations

from modules.virus_bridge.entry_stop import derive_entry_hint, derive_stop_hint


def test_entry_and_stop_hints_with_price_and_momentum() -> None:
    proposal = {"direction": "long", "score": 7.4}
    quote = {"last_price": 302.25, "currency": "USD", "percent_change": 1.2}

    assert derive_entry_hint(proposal, quote, {}) == "Einstieg nur bei weiter bestaetigter Staerke beobachten"
    assert derive_stop_hint(proposal, quote, {}) == "Unter letztem markanten Ruecksetzer beobachten"


def test_entry_and_stop_hints_do_not_crash_without_quote() -> None:
    proposal = {"direction": "long", "score": 5.8}

    assert derive_entry_hint(proposal, None, {}) == "Nur bei bestaetigter Staerke beobachten"
    assert derive_stop_hint(proposal, None, {}) == "Stop-Idee manuell pruefen"
