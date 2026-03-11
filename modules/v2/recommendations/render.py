from __future__ import annotations

from modules.common.operator_signals import market_status_detail, position_size_values, validate_buy_signal, validate_exit_signal
from modules.v2.telegram.copy import (
    candidate_name,
    classification_label,
    last_price_text,
    market_label,
    reason_lines,
    normalize_confidence,
    sell_exit_hint,
    sell_size_hint,
)


def _defense_signal_strength(defense: dict) -> str:
    score = float(max(defense.get("sell_score", 0) or 0, defense.get("risk_reduce_score", 0) or 0, defense.get("defense_score", 0) or 0))
    if score >= 7:
        return "hoch"
    if score >= 5:
        return "mittel"
    return "spekulativ"


def _defense_lines(defense: dict, label: str) -> str:
    if label == "VERKAUFEN PRUEFEN":
        return reason_lines(defense.get("sell_reasons", []) or defense.get("reasons", []))
    return reason_lines(defense.get("risk_reduce_reasons", []) or defense.get("reasons", []), limit=2)


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


def _buy_stop_block(candidate: dict) -> str:
    lines = [str(candidate.get("stop_hint") or candidate.get("stop_loss_hint") or "Stop-Loss manuell pruefen").strip()]
    stop_price = candidate.get("stop_loss_price")
    if stop_price not in (None, ""):
        lines.append(f"Stop-Kurs: {float(stop_price):.2f}")
    stop_method = str(candidate.get("stop_method") or "").strip()
    if stop_method:
        lines.append(f"Stop-Methode: {stop_method}")
    stop_distance = candidate.get("stop_distance_pct")
    if stop_distance not in (None, ""):
        lines.append(f"Stop-Abstand: {float(stop_distance):.2f} %")
    return "\n".join(lines)


def _position_size_block(candidate: dict, signal_strength: str) -> str:
    size_min, size_max, suggested = position_size_values(candidate)
    if signal_strength == "hoch":
        base = "Mittlere bis groessere Positionsgroesse pruefen."
    elif signal_strength == "mittel":
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


def _missing_block(validation: dict) -> str:
    labels = [str(value or "").strip() for value in validation.get("missing_labels") or [] if str(value or "").strip()]
    return "\n".join(f"- {label}" for label in labels) or "- Operative Pflichtfelder fehlen"


def _notes_text(candidate: dict) -> str:
    value = candidate.get("hinweise") or candidate.get("notes") or candidate.get("hint")
    if isinstance(value, list):
        return ", ".join(str(item).strip() for item in value if str(item).strip())
    return str(value or "").strip()


def _incomplete_buy_text(candidate: dict, signal_strength: str, market: str, why_now: str, validation: dict) -> str:
    return (
        f"KAUFIDEE UEBERPRUEFEN: {candidate_name(candidate)}\n\n"
        "Status:\n"
        "UNVOLLSTAENDIG\n\n"
        "Signalstaerke:\n"
        f"{signal_strength}\n\n"
        "Marktlage:\n"
        f"{market}\n\n"
        "Marktstatus:\n"
        f"{market_status_detail(candidate)}\n\n"
        "Warum jetzt interessant:\n"
        f"{why_now}\n\n"
        "Letzter Kurs:\n"
        f"{last_price_text(candidate)}\n\n"
        "Operative Luecken:\n"
        f"{_missing_block(validation)}\n\n"
        "Naechster Schritt:\n"
        "Operative Pflichtfelder zuerst vervollstaendigen. Noch kein handlungsfaehiges Signal."
    )


def _incomplete_exit_text(header: str, candidate: dict, signal_strength: str, market: str, reasons_text: str, validation: dict) -> str:
    return (
        f"{header}: {candidate_name(candidate)}\n\n"
        "Status:\n"
        "UNVOLLSTAENDIG\n\n"
        "Signalstaerke:\n"
        f"{signal_strength}\n\n"
        "Marktlage:\n"
        f"{market}\n\n"
        "Marktstatus:\n"
        f"{market_status_detail(candidate)}\n\n"
        "Warum:\n"
        f"{reasons_text}\n\n"
        "Letzter Kurs:\n"
        f"{last_price_text(candidate)}\n\n"
        "Operative Luecken:\n"
        f"{_missing_block(validation)}\n\n"
        "Naechster Schritt:\n"
        "Signal erst mit sauberem Exit-Hinweis und Positionshinweis weiterverwenden."
    )


def render_recommendation(candidate: dict, classification: str, scores: dict, cfg: dict | None = None) -> dict:
    del cfg
    opp = scores.get("opportunity", {})
    defense = scores.get("defense", {})
    market = market_label(scores.get("regime") or candidate.get("regime"))
    signal_strength = normalize_confidence(opp.get("confidence"))
    why_now = reason_lines(opp.get("reasons", []))
    label = classification_label(classification, {**candidate, "defense_score": defense})
    notes_text = _notes_text(candidate)
    notes_block = f"\n\nHinweise:\n{notes_text}" if notes_text else ""

    if label == "KAUFEN PRUEFEN":
        next_step = "Nur handeln, wenn Einstieg, Stop-Loss und Risiko fuer dich sauber passen."
        enriched = {
            **candidate,
            "signal_strength": signal_strength,
            "market_regime": market,
            "reasons": opp.get("reasons", []),
            "next_step": next_step,
        }
        validation = validate_buy_signal(enriched)
        if validation["is_operational"]:
            text = (
                f"{label}: {candidate_name(candidate)}\n\n"
                "Signalstaerke:\n"
                f"{signal_strength}\n\n"
                "Marktlage:\n"
                f"{market}\n\n"
                "Marktstatus:\n"
                f"{market_status_detail(enriched)}\n\n"
                "Warum jetzt interessant:\n"
                f"{why_now}\n\n"
                "Letzter Kurs:\n"
                f"{last_price_text(candidate)}\n\n"
                "Einstieg:\n"
                f"{str(candidate.get('entry_hint') or candidate.get('entry') or 'Einstieg manuell pruefen').strip()}\n\n"
                "Stop-Loss:\n"
                f"{_buy_stop_block(candidate)}\n\n"
                "Maximales Risiko:\n"
                f"{_money(candidate.get('risk_eur'))}\n\n"
                "Positionsgroesse:\n"
                f"{_position_size_block(candidate, signal_strength)}"
                f"{notes_block}\n\n"
                "Naechster Schritt:\n"
                f"{next_step}"
            )
        else:
            text = _incomplete_buy_text(enriched, signal_strength, market, why_now, validation)
    elif label == "VERKAUFEN PRUEFEN":
        signal_strength = _defense_signal_strength(defense)
        exit_hint = sell_exit_hint(defense)
        position_hint = sell_size_hint(defense, market)
        reasons_text = _defense_lines(defense, label)
        next_step = "Verkauf oder Teilverkauf nur dann umsetzen, wenn Schwaeche und Depotkontext fuer dich sauber passen."
        enriched = {**candidate, "signal_strength": signal_strength, "market_regime": market}
        validation = validate_exit_signal(enriched, exit_hint=exit_hint, position_hint=position_hint, reasons=defense.get("sell_reasons", []) or defense.get("reasons", []), next_step=next_step)
        if validation["is_operational"]:
            text = (
                f"{label}: {candidate_name(candidate)}\n\n"
                "Signalstaerke:\n"
                f"{signal_strength}\n\n"
                "Marktlage:\n"
                f"{market}\n\n"
                "Marktstatus:\n"
                f"{market_status_detail(enriched)}\n\n"
                "Warum:\n"
                f"{reasons_text}\n\n"
                "Letzter Kurs:\n"
                f"{last_price_text(candidate)}\n\n"
                "Exit-Hinweis:\n"
                f"{exit_hint}\n\n"
                "Positionshinweis:\n"
                f"{position_hint}"
                f"{notes_block}\n\n"
                "Naechster Schritt:\n"
                f"{next_step}"
            )
        else:
            text = _incomplete_exit_text(label, enriched, signal_strength, market, reasons_text, validation)
    elif label == "RISIKO REDUZIEREN":
        signal_strength = _defense_signal_strength(defense)
        reasons_text = _defense_lines(defense, label)
        exit_hint = "Schwaeche bestaetigen und Reduktionsniveau manuell festlegen."
        position_hint = "Positionsgroesse reduzieren pruefen."
        next_step = "Risiko nur dann reduzieren, wenn Marktbild und Depotkontext fuer dich sauber passen."
        enriched = {**candidate, "signal_strength": signal_strength, "market_regime": market}
        validation = validate_exit_signal(enriched, exit_hint=exit_hint, position_hint=position_hint, reasons=defense.get("risk_reduce_reasons", []) or defense.get("reasons", []), next_step=next_step)
        if validation["is_operational"]:
            text = (
                f"{label}: {candidate_name(candidate)}\n\n"
                "Signalstaerke:\n"
                f"{signal_strength}\n\n"
                "Marktlage:\n"
                f"{market}\n\n"
                "Marktstatus:\n"
                f"{market_status_detail(enriched)}\n\n"
                "Warum:\n"
                f"{reasons_text}\n\n"
                "Letzter Kurs:\n"
                f"{last_price_text(candidate)}\n\n"
                "Exit-Hinweis:\n"
                f"{exit_hint}\n\n"
                "Positionshinweis:\n"
                f"{position_hint}"
                f"{notes_block}\n\n"
                "Naechster Schritt:\n"
                f"{next_step}"
            )
        else:
            text = _incomplete_exit_text(label, enriched, signal_strength, market, reasons_text, validation)
    elif label == "HALTEN":
        text = (
            f"{label}: {candidate_name(candidate)}\n\n"
            "Signalstaerke:\n"
            f"{signal_strength}\n\n"
            "Marktlage:\n"
            f"{market}\n\n"
            "Marktstatus:\n"
            f"{market_status_detail(candidate)}\n\n"
            "Warum:\n"
            f"{why_now}\n\n"
            f"{notes_text + chr(10) * 2 if notes_text else ''}"
            "Empfehlung:\n"
            "Position halten. Kein neuer Eingriff noetig."
        )
    else:
        text = ""

    buy_validation = validate_buy_signal({**candidate, "signal_strength": signal_strength, "market_regime": market, "reasons": opp.get("reasons", []), "next_step": "Nur handeln, wenn Einstieg, Stop-Loss und Risiko fuer dich sauber passen."}) if label == "KAUFEN PRUEFEN" else None
    exit_validation = None
    if label == "VERKAUFEN PRUEFEN":
        exit_validation = validate_exit_signal(
            {**candidate, "signal_strength": _defense_signal_strength(defense), "market_regime": market},
            exit_hint=sell_exit_hint(defense),
            position_hint=sell_size_hint(defense, market),
            reasons=defense.get("sell_reasons", []) or defense.get("reasons", []),
            next_step="Verkauf oder Teilverkauf nur dann umsetzen, wenn Schwaeche und Depotkontext fuer dich sauber passen.",
        )
    elif label == "RISIKO REDUZIEREN":
        exit_validation = validate_exit_signal(
            {**candidate, "signal_strength": _defense_signal_strength(defense), "market_regime": market},
            exit_hint="Schwaeche bestaetigen und Reduktionsniveau manuell festlegen.",
            position_hint="Positionsgroesse reduzieren pruefen.",
            reasons=defense.get("risk_reduce_reasons", []) or defense.get("reasons", []),
            next_step="Risiko nur dann reduzieren, wenn Marktbild und Depotkontext fuer dich sauber passen.",
        )
    operational = buy_validation or exit_validation
    payload = {
        "symbol": candidate.get("symbol"),
        "isin": candidate.get("isin"),
        "name": candidate.get("name"),
        "classification": classification,
        "opportunity_score": opp,
        "defense_score": defense,
        "group": candidate.get("group"),
        "weight_pct": candidate.get("weight_pct"),
        "country": candidate.get("country"),
        "provider": candidate.get("provider"),
        "regime": scores.get("regime") or candidate.get("regime") or "neutral",
        "quote": candidate.get("quote"),
        "user_classification": label,
        "market_status": candidate.get("market_status"),
        "entry_hint": candidate.get("entry_hint") or candidate.get("entry"),
        "stop_hint": candidate.get("stop_hint") or candidate.get("stop_loss_hint") or candidate.get("stop"),
        "stop_method": candidate.get("stop_method"),
        "stop_loss_price": candidate.get("stop_loss_price"),
        "stop_distance_pct": candidate.get("stop_distance_pct"),
        "risk_eur": candidate.get("risk_eur"),
        "size_min_eur": candidate.get("size_min_eur"),
        "size_max_eur": candidate.get("size_max_eur"),
        "suggested_eur": candidate.get("suggested_eur"),
        "operational_status": operational["status"] if operational else None,
        "operational_is_actionable": operational["is_operational"] if operational else None,
        "operational_missing_fields": operational["missing_fields"] if operational else [],
    }
    return {"classification": classification, "telegram_text": text[:900], "json": payload}
