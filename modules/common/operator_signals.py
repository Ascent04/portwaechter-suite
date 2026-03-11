from __future__ import annotations

from typing import Iterable


BUY_FIELD_LABELS = {
    "display_name": "Titel",
    "signal_strength": "Signalstaerke",
    "market_regime": "Marktlage",
    "market_status": "Marktstatus",
    "market_open": "Markt aktuell offen",
    "data_fresh": "Frische Kursdaten",
    "decision": "Ticket-Reife",
    "last_price": "Letzter Kurs",
    "entry_hint": "Einstieg",
    "stop_hint": "Stop-Hinweis",
    "stop_method": "Stop-Methode",
    "stop_loss_price": "Stop-Kurs",
    "stop_distance_pct": "Stop-Abstand",
    "risk_eur": "Maximales Risiko",
    "position_size": "Positionsgroesse",
    "reasons": "Begruendung",
    "next_step": "Naechster Schritt",
}

EXIT_FIELD_LABELS = {
    "display_name": "Titel",
    "signal_strength": "Signalstaerke",
    "market_regime": "Marktlage",
    "market_status": "Marktstatus",
    "last_price": "Letzter Kurs",
    "exit_hint": "Exit-Hinweis",
    "position_hint": "Positionshinweis",
    "reasons": "Begruendung",
    "next_step": "Naechster Schritt",
}

PLACEHOLDER_FRAGMENTS = {
    "manuell pruefen",
    "noch unvollstaendig",
    "unvollstaendig",
    "unbekannt",
}


def _asset(candidate: dict) -> dict:
    value = candidate.get("asset")
    return value if isinstance(value, dict) else {}


def _text(value: object) -> str:
    return str(value or "").strip()


def _text_ok(value: object) -> bool:
    text = _text(value)
    if not text:
        return False
    lowered = text.lower()
    return not any(fragment in lowered for fragment in PLACEHOLDER_FRAGMENTS)


def _number(value: object) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _reasons(values: Iterable[object]) -> list[str]:
    return [_text(value) for value in values if _text(value)]


def display_name(candidate: dict) -> str:
    asset = _asset(candidate)
    return _text(asset.get("name") or candidate.get("name") or asset.get("symbol") or candidate.get("symbol") or asset.get("isin") or candidate.get("isin"))


def symbol(candidate: dict) -> str:
    asset = _asset(candidate)
    return _text(asset.get("symbol") or candidate.get("symbol") or asset.get("isin") or candidate.get("isin"))


def market_status_label(candidate: dict) -> str:
    status = candidate.get("market_status")
    if isinstance(status, dict) and "is_open" in status:
        return "offen" if bool(status.get("is_open")) else "geschlossen"
    return _text(candidate.get("market_status_text"))


def market_status_detail(candidate: dict) -> str:
    status = candidate.get("market_status")
    if not isinstance(status, dict) or "is_open" not in status:
        return market_status_label(candidate)
    lines = ["offen" if bool(status.get("is_open")) else "geschlossen"]
    hint = _text(status.get("next_open_hint"))
    if hint and not bool(status.get("is_open")):
        lines.append(f"Naechste Handelsmoeglichkeit: {hint}")
    return "\n".join(lines)


def last_price_value(candidate: dict) -> float | None:
    quote = candidate.get("quote")
    if isinstance(quote, dict):
        for key in ("price", "last_price"):
            value = _number(quote.get(key))
            if value is not None:
                return value
    for key in ("last_price", "price"):
        value = _number(candidate.get(key))
        if value is not None:
            return value
    return None


def position_size_values(candidate: dict) -> tuple[float | None, float | None, float | None]:
    size_min = _number(candidate.get("size_min_eur") or candidate.get("suggested_size_min_eur"))
    size_max = _number(candidate.get("size_max_eur") or candidate.get("suggested_size_max_eur"))
    suggested = _number(candidate.get("suggested_eur"))
    return size_min, size_max, suggested


def has_position_size(candidate: dict) -> bool:
    size_min, size_max, suggested = position_size_values(candidate)
    return any(value is not None for value in (size_min, size_max, suggested))


def validate_buy_signal(candidate: dict) -> dict:
    market_status = candidate.get("market_status")
    decision = _text(candidate.get("decision")).upper()
    fields = {
        "display_name": display_name(candidate) or symbol(candidate),
        "signal_strength": _text(candidate.get("signal_strength")),
        "market_regime": _text(candidate.get("market_regime") or candidate.get("regime")),
        "market_status": market_status_label(candidate),
        "last_price": last_price_value(candidate),
        "entry_hint": _text(candidate.get("entry_hint") or candidate.get("entry")),
        "stop_hint": _text(candidate.get("stop_hint") or candidate.get("stop_loss_hint") or candidate.get("stop_loss") or candidate.get("stop")),
        "stop_method": _text(candidate.get("stop_method")),
        "stop_loss_price": _number(candidate.get("stop_loss_price")),
        "stop_distance_pct": _number(candidate.get("stop_distance_pct")),
        "risk_eur": _number(candidate.get("risk_eur")),
        "reasons": _reasons(candidate.get("reasons") or []),
        "next_step": _text(candidate.get("next_step")),
    }
    missing: list[str] = []
    if not _text_ok(fields["display_name"]):
        missing.append("display_name")
    if not _text_ok(fields["signal_strength"]):
        missing.append("signal_strength")
    if not _text_ok(fields["market_regime"]):
        missing.append("market_regime")
    if not _text_ok(fields["market_status"]):
        missing.append("market_status")
    if isinstance(market_status, dict) and market_status.get("is_open") is False:
        missing.append("market_open")
    if candidate.get("data_fresh") is False:
        missing.append("data_fresh")
    if decision and decision != "APPROVED":
        missing.append("decision")
    if fields["last_price"] is None:
        missing.append("last_price")
    if not _text_ok(fields["entry_hint"]):
        missing.append("entry_hint")
    if not _text_ok(fields["stop_hint"]):
        missing.append("stop_hint")
    if not _text_ok(fields["stop_method"]):
        missing.append("stop_method")
    if fields["stop_loss_price"] is None:
        missing.append("stop_loss_price")
    if fields["stop_distance_pct"] is None:
        missing.append("stop_distance_pct")
    if fields["risk_eur"] is None:
        missing.append("risk_eur")
    if not has_position_size(candidate):
        missing.append("position_size")
    if not fields["reasons"]:
        missing.append("reasons")
    if not _text_ok(fields["next_step"]):
        missing.append("next_step")
    return {
        "signal_kind": "buy",
        "status": "OPERATIV_NUTZBAR" if not missing else "UNVOLLSTAENDIG",
        "is_operational": not missing,
        "missing_fields": missing,
        "missing_labels": [BUY_FIELD_LABELS[key] for key in missing],
        "fields": fields,
    }


def validate_exit_signal(
    candidate: dict,
    *,
    exit_hint: object,
    position_hint: object,
    reasons: Iterable[object],
    next_step: object,
) -> dict:
    fields = {
        "display_name": display_name(candidate) or symbol(candidate),
        "signal_strength": _text(candidate.get("signal_strength")),
        "market_regime": _text(candidate.get("market_regime") or candidate.get("regime")),
        "market_status": market_status_label(candidate),
        "last_price": last_price_value(candidate),
        "exit_hint": _text(exit_hint),
        "position_hint": _text(position_hint),
        "reasons": _reasons(reasons),
        "next_step": _text(next_step),
    }
    missing: list[str] = []
    if not _text_ok(fields["display_name"]):
        missing.append("display_name")
    if not _text_ok(fields["signal_strength"]):
        missing.append("signal_strength")
    if not _text_ok(fields["market_regime"]):
        missing.append("market_regime")
    if not _text_ok(fields["market_status"]):
        missing.append("market_status")
    if fields["last_price"] is None:
        missing.append("last_price")
    if not _text_ok(fields["exit_hint"]):
        missing.append("exit_hint")
    if not _text_ok(fields["position_hint"]):
        missing.append("position_hint")
    if not fields["reasons"]:
        missing.append("reasons")
    if not _text_ok(fields["next_step"]):
        missing.append("next_step")
    return {
        "signal_kind": "exit",
        "status": "OPERATIV_NUTZBAR" if not missing else "UNVOLLSTAENDIG",
        "is_operational": not missing,
        "missing_fields": missing,
        "missing_labels": [EXIT_FIELD_LABELS[key] for key in missing],
        "fields": fields,
    }
