from __future__ import annotations


def _direction(signal_proposal: dict) -> str:
    return str(signal_proposal.get("direction") or "long").strip().lower()


def _score(signal_proposal: dict) -> float:
    return float(signal_proposal.get("score", 0) or 0)


def _percent_change(quote: dict | None) -> float | None:
    if not isinstance(quote, dict):
        return None
    value = quote.get("percent_change")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def derive_entry_hint(signal_proposal, quote, cfg) -> str:
    direction = _direction(signal_proposal)
    score = _score(signal_proposal)
    pct_change = _percent_change(quote)

    if direction == "short":
        if score >= 7 and pct_change is not None and pct_change < 0:
            return "Short nur bei weiter bestaetigter Schwaeche beobachten"
        return "Short nur bei bestaetigter Schwaeche beobachten"

    if score >= 7 and pct_change is not None and pct_change > 0:
        return "Einstieg nur bei weiter bestaetigter Staerke beobachten"
    return "Nur bei bestaetigter Staerke beobachten"


def derive_stop_hint(signal_proposal, quote, cfg) -> str:
    if not isinstance(quote, dict) or quote.get("last_price") in (None, ""):
        return "Stop-Idee manuell pruefen"

    if _direction(signal_proposal) == "short":
        return "Ueber letztem Gegenlauf beobachten"
    return "Unter letztem markanten Ruecksetzer beobachten"
