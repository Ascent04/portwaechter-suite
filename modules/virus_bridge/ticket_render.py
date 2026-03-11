from __future__ import annotations

from modules.common.operator_warnings import warning_lines
from modules.common.operator_signals import display_name, market_status_detail, position_size_values, validate_buy_signal
from modules.v2.telegram.copy import normalize_confidence


def _asset_name(trade_candidate: dict) -> str:
    return display_name(trade_candidate) or "Unbekannter Titel"


def _reasons(trade_candidate: dict, limit: int = 3) -> str:
    reasons = [str(value or "").strip() for value in (trade_candidate.get("reasons") or []) if str(value or "").strip()]
    return "\n".join(f"- {reason}" for reason in reasons[:limit]) or "- Keine tragfaehigen Gruende"


def _money(value: object, suffix: str = "EUR") -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "nicht belastbar verfuegbar"
    sign = "-" if number < 0 else ""
    absolute = abs(number)
    if absolute.is_integer():
        text = f"{absolute:,.0f}"
    else:
        text = f"{absolute:,.2f}"
    text = text.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{sign}{text} {suffix}".strip()


def _price_line(trade_candidate: dict) -> str:
    price = trade_candidate.get("last_price")
    if price in (None, ""):
        return "manuell pruefen"
    try:
        value = f"{float(price):.2f}"
    except (TypeError, ValueError):
        return "manuell pruefen"
    currency = str(trade_candidate.get("currency") or "").strip().upper()
    suffix = f" {currency}" if currency else ""
    return f"{value}{suffix}"


def _position_size_block(trade_candidate: dict) -> str:
    size_min, size_max, suggested = position_size_values(trade_candidate)
    strength = normalize_confidence(trade_candidate.get("signal_strength"))
    if strength == "hoch":
        base = "Mittlere bis groessere Positionsgroesse pruefen."
    elif strength == "mittel":
        base = "Kleine bis mittlere Positionsgroesse pruefen."
    else:
        base = "Nur kleine Testgroesse pruefen."
    if size_min is not None and size_max is not None:
        start = _money(size_min).replace(",00 EUR", "").replace(" EUR", "")
        end = _money(size_max).replace(",00 EUR", " EUR")
        return f"{base} Vorschlag: {start} bis {end}."
    if suggested is not None:
        return f"{base} Vorschlag: {_money(suggested).replace(',00 EUR', ' EUR')}."
    if size_max is not None:
        return f"{base} Vorschlag: bis {_money(size_max).replace(',00 EUR', ' EUR')}."
    return "Noch unvollstaendig."


def _stop_loss_block(trade_candidate: dict) -> str:
    hint = str(trade_candidate.get("stop_loss_hint") or trade_candidate.get("stop_hint") or "Stop-Loss manuell pruefen").strip()
    lines = [hint]
    stop_price = trade_candidate.get("stop_loss_price")
    if stop_price not in (None, ""):
        lines.append(f"Stop-Kurs: {float(stop_price):.2f}")
    stop_method = str(trade_candidate.get("stop_method") or "").strip()
    if stop_method:
        lines.append(f"Stop-Methode: {stop_method}")
    stop_distance = trade_candidate.get("stop_distance_pct")
    if stop_distance not in (None, ""):
        lines.append(f"Stop-Abstand: {float(stop_distance):.2f} %")
    return "\n".join(lines)


def _missing_block(validation: dict) -> str:
    labels = [str(value or "").strip() for value in validation.get("missing_labels") or [] if str(value or "").strip()]
    return "\n".join(f"- {label}" for label in labels) or "- Operative Pflichtfelder fehlen"


def _warning_block(trade_candidate: dict, decision: str, validation: dict) -> str:
    market_status = trade_candidate.get("market_status")
    warnings: list[tuple[str, str]] = []
    if not validation.get("is_operational"):
        warnings.append(("UNVOLLSTAENDIG", "Operative Pflichtfelder fehlen"))
    if isinstance(market_status, dict) and market_status.get("is_open") is False:
        warnings.append(("MARKT_GESCHLOSSEN", "Der Markt ist aktuell geschlossen"))
    if trade_candidate.get("data_fresh") is False:
        warnings.append(("VERALTET", "Kursdaten sind nicht frisch"))
    if decision != "APPROVED":
        warnings.append(("NOCH_NICHT_BEWERTBAR", "Ticket ist noch nicht operativ freigegeben"))
    items = warning_lines(warnings)
    return "\n".join(f"- {item}" for item in items) or "- UNVOLLSTAENDIG: Operative Pflichtfelder fehlen."


def _default_next_step(decision: str) -> str:
    if decision == "PENDING_MARKET_OPEN":
        return "Kauf erst pruefen, wenn der Markt wieder offen ist."
    return "Nur handeln, wenn Einstieg, Stop-Loss und Risiko fuer dich sauber passen."


def render_ticket_text(trade_candidate: dict) -> str:
    decision = str(trade_candidate.get("decision") or "REJECTED").upper()
    signal_strength = normalize_confidence(trade_candidate.get("signal_strength"))
    market_regime = str(trade_candidate.get("market_regime") or "neutral")
    name = _asset_name(trade_candidate)
    price_line = _price_line(trade_candidate)
    entry_hint = str(trade_candidate.get("entry_hint") or "Einstieg manuell pruefen").strip()
    market_status = trade_candidate.get("market_status") or {}
    tr_verified = bool(trade_candidate.get("tr_verified", True))
    stop_loss_block = _stop_loss_block(trade_candidate)
    next_step = str(trade_candidate.get("next_step") or _default_next_step(decision)).strip()
    validation = validate_buy_signal({**trade_candidate, "next_step": next_step})

    if not tr_verified:
        return (
            f"TRADE-KANDIDAT ABGELEHNT: {name}\n\n"
            "Grund:\n"
            "- Nicht bei Trade Republic verifiziert\n\n"
            "Naechster Schritt:\n"
            "Nicht weiter verfolgen."
        )[:1400]

    if decision not in {"APPROVED", "REDUCED", "PENDING_MARKET_OPEN"}:
        return (
            f"TRADE-KANDIDAT ABGELEHNT: {name}\n\n"
            "Grund:\n"
            f"{_reasons(trade_candidate, limit=2)}\n\n"
            "Naechster Schritt:\n"
            "Nicht weiter verfolgen."
        )[:1500]

    if not validation["is_operational"]:
        return (
            f"KAUFIDEE UEBERPRUEFEN: {name}\n\n"
            "Status:\n"
            "UNVOLLSTAENDIG\n\n"
            "Signalstaerke:\n"
            f"{signal_strength}\n\n"
            "Marktlage:\n"
            f"{market_regime}\n\n"
            "Marktstatus:\n"
            f"{market_status_detail(trade_candidate)}\n\n"
            "Warum jetzt interessant:\n"
            f"{_reasons(trade_candidate, limit=3)}\n\n"
            "Letzter Kurs:\n"
            f"{price_line}\n\n"
            "Warnlage:\n"
            f"{_warning_block(trade_candidate, decision, validation)}\n\n"
            "Operative Luecken:\n"
            f"{_missing_block(validation)}\n\n"
            "Naechster Schritt:\n"
            "Operative Pflichtfelder zuerst vervollstaendigen. Noch kein handlungsfaehiges Ticket."
        )[:1500]

    text = (
        f"KAUFEN PRUEFEN: {name}\n\n"
        "Signalstaerke:\n"
        f"{signal_strength}\n\n"
        "Marktlage:\n"
        f"{market_regime}\n\n"
        "Marktstatus:\n"
        f"{market_status_detail(trade_candidate)}\n\n"
        "Warum jetzt interessant:\n"
        f"{_reasons(trade_candidate, limit=3)}\n\n"
        "Letzter Kurs:\n"
        f"{price_line}\n\n"
        "Einstieg:\n"
        f"{entry_hint}\n\n"
        "Stop-Loss:\n"
        f"{stop_loss_block}\n\n"
        "Maximales Risiko:\n"
        f"{_money(trade_candidate.get('risk_eur'))}\n\n"
        "Positionsgroesse:\n"
        f"{_position_size_block(trade_candidate)}\n\n"
        "Naechster Schritt:\n"
        f"{next_step}"
    )
    return text[:1500]
