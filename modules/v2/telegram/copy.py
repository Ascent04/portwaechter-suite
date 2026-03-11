from __future__ import annotations

from typing import Iterable

SCORE_FALLBACK = "0.0"
CONFIDENCE_VALUES = {"hoch", "mittel", "spekulativ"}
MAX_REASON_COUNT = 3
PREMARKET_SECTION_ORDER = ("VERKAUFEN PRUEFEN", "RISIKO REDUZIEREN", "KAUFEN PRUEFEN")
PREMARKET_SECTION_TITLES = {
    "VERKAUFEN PRUEFEN": "Verkaufen prüfen",
    "RISIKO REDUZIEREN": "Risiko reduzieren",
    "KAUFEN PRUEFEN": "Kaufen prüfen",
}

REASON_LABELS = {
    "momentum": "Momentum",
    "relative_strength": "Relative Staerke",
    "portfolio_priority": "Depotrelevanz",
    "volume": "Ungewoehnlich hohes Volumen",
    "volume_spike": "Ungewoehnlich hohes Volumen",
    "news": "Nachrichtenlage",
    "news_impact": "Nachrichtenimpuls",
    "positive_setup_expectancy": "Positive Setup-Historie",
    "negative_setup_expectancy": "Schwache Setup-Historie",
    "strong_selloff": "Starker Abverkauf",
    "starker_abverkauf": "Starker Abverkauf",
    "negative_momentum_strong": "Starker Abverkauf",
    "negative_momentum_medium": "Negativer Kursimpuls",
    "negative_momentum_light": "Leichte Schwaeche",
    "risk_concentration": "Hohe Depotkonzentration",
    "news_burden": "Nachrichtenlage belastend",
    "negativer_move": "Negativer Kursimpuls",
    "schwacher_tag": "Schwacher Handelstag",
    "negative_news": "Negative Nachrichtenlage",
    "high_weight": "Grosses Positionsgewicht",
    "very_high_weight": "Sehr grosses Positionsgewicht",
    "relevant_weight": "Relevantes Positionsgewicht",
    "grosses_positionsgewicht": "Grosses Positionsgewicht",
    "relevantes_positionsgewicht": "Relevantes Positionsgewicht",
    "risk_on_regime": "Marktumfeld positiv",
    "positive_regime_expectancy": "Passendes Marktumfeld",
    "regime_risk_on": "Marktumfeld positiv",
    "risk_off_regime": "Marktumfeld defensiv",
    "risk_off_penalty": "Marktumfeld defensiv",
    "regime_risk_off": "Marktumfeld defensiv",
    "uncertain_regime": "Marktlage unsicher",
}

REASON_PRIORITY = {
    "momentum": 1,
    "volume": 2,
    "volume_spike": 2,
    "news": 3,
    "news_impact": 3,
    "positive_setup_expectancy": 4,
    "relative_strength": 5,
    "portfolio_priority": 6,
    "positive_regime_expectancy": 7,
    "risk_on_regime": 8,
    "regime_risk_on": 8,
    "strong_selloff": 1,
    "starker_abverkauf": 1,
    "negative_momentum_strong": 1,
    "negativer_move": 2,
    "negative_momentum_medium": 2,
    "negative_news": 3,
    "news_burden": 3,
    "high_weight": 4,
    "very_high_weight": 4,
    "relevant_weight": 5,
    "grosses_positionsgewicht": 4,
    "relevantes_positionsgewicht": 5,
    "risk_off_regime": 6,
    "risk_off_penalty": 6,
    "regime_risk_off": 6,
    "uncertain_regime": 6,
    "risk_concentration": 7,
    "schwacher_tag": 8,
    "negative_momentum_light": 9,
}


def _normalize_reason(value: object) -> str:
    text = str(value or "").strip().lower()
    return text.replace("-", "_").replace(" ", "_")


def _reason_keys(values: Iterable[object]) -> set[str]:
    return {key for key in (_normalize_reason(value) for value in values) if key}


def format_score(value: object) -> str:
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return SCORE_FALLBACK


def normalize_confidence(value: object) -> str:
    text = str(value or "").strip().lower()
    return text if text in CONFIDENCE_VALUES else "spekulativ"


def normalize_regime(value: object) -> str:
    text = str(value or "").strip()
    return text or "neutral"


def display_name(cfg: dict | None = None) -> str:
    if isinstance(cfg, dict):
        value = str(((cfg.get("bot_identity") or {}).get("display_name")) or "").strip()
        if value:
            return value
    return "CB Fund Desk"


def _is_holding(candidate: dict | None) -> bool:
    if not isinstance(candidate, dict):
        return False
    if str(candidate.get("group") or "").strip().lower() == "holding":
        return True
    try:
        return float(candidate.get("weight_pct", 0) or 0) > 0
    except (TypeError, ValueError):
        return False


def classification_label(value: object, candidate: dict | None = None) -> str:
    raw = str(value or "").strip().upper().replace(" ", "_")
    if raw in {"KAUFEN_PRUEFEN", "ACTION", "KAUFIDEE_PRUEFEN"}:
        return "KAUFEN PRUEFEN"
    if raw in {"HALTEN", "WATCH"}:
        return "HALTEN"
    if raw in {"VERKAUFEN_PRUEFEN"}:
        return "VERKAUFEN PRUEFEN"
    if raw in {"RISIKO_REDUZIEREN"}:
        return "RISIKO REDUZIEREN"
    if raw in {"DEFENSE", "RISIKO_PRUEFEN"}:
        if isinstance(candidate, dict):
            defense = candidate.get("defense_score") or {}
            sell_score = float((defense.get("sell_score") or defense.get("defense_score") or 0) or 0)
            risk_reduce_score = float((defense.get("risk_reduce_score") or defense.get("defense_score") or 0) or 0)
            if sell_score >= max(6.0, risk_reduce_score):
                return "VERKAUFEN PRUEFEN"
        return "RISIKO REDUZIEREN"
    return str(value or "HALTEN").strip().replace("_", " ")


def market_label(value: object) -> str:
    mapping = {
        "risk_on": "positiv",
        "neutral": "neutral",
        "risk_off": "defensiv",
        "positiv": "positiv",
        "defensiv": "defensiv",
    }
    return mapping.get(str(value or "").strip().lower(), "neutral")


def premarket_priority(value: object, candidate: dict | None = None) -> int:
    label = classification_label(value, candidate)
    try:
        return PREMARKET_SECTION_ORDER.index(label)
    except ValueError:
        return 99


def premarket_section_title(value: object, candidate: dict | None = None) -> str:
    label = classification_label(value, candidate)
    return PREMARKET_SECTION_TITLES.get(label, label.title())


def candidate_name(candidate: dict) -> str:
    return str(candidate.get("name") or candidate.get("symbol") or candidate.get("isin") or "Unbekannter Titel")


def candidate_identifier(candidate: dict) -> str:
    return str(candidate.get("symbol") or candidate.get("isin") or candidate_name(candidate))


def candidate_label(candidate: dict) -> str:
    return f"{candidate_name(candidate)} ({candidate_identifier(candidate)})"


def short_name(candidate: dict, max_len: int = 42) -> str:
    name = candidate_name(candidate)
    return name if len(name) <= max_len else f"{name[: max_len - 3].rstrip()}..."


def human_reason(value: object) -> str:
    key = _normalize_reason(value)
    if not key:
        return ""
    return REASON_LABELS.get(key, str(value).strip().replace("_", " ").title())


def human_reasons(values: Iterable[object], limit: int = MAX_REASON_COUNT) -> list[str]:
    ranked: list[tuple[int, int, str]] = []
    seen: set[str] = set()
    for idx, value in enumerate(values):
        key = _normalize_reason(value)
        label = human_reason(value)
        if not key or not label or label in seen:
            continue
        seen.add(label)
        ranked.append((REASON_PRIORITY.get(key, 99), idx, label))
    ranked.sort()
    return [label for _, _, label in ranked[:limit]]


def joined_reasons(values: Iterable[object], limit: int = MAX_REASON_COUNT, fallback: str = "Signal-Auffaelligkeit") -> str:
    reasons = human_reasons(values, limit=limit)
    return ", ".join(reasons) if reasons else fallback


def reason_lines(values: Iterable[object], limit: int = MAX_REASON_COUNT, fallback: str = "- Keine klaren Einzelgruende") -> str:
    reasons = human_reasons(values, limit=limit)
    return "\n".join(f"- {reason}" for reason in reasons) if reasons else fallback


def defense_reason(candidate: dict, values: Iterable[object]) -> str:
    reasons = human_reasons(values, limit=MAX_REASON_COUNT)
    if not reasons:
        return "Erhoehtes Risiko"
    if "Starker Abverkauf" in reasons and candidate.get("group") == "holding":
        return "Starker Abverkauf bei bestehender Depotposition"
    return ", ".join(reasons)


def _float_text(value: object, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return ""


def market_status_text(candidate: dict) -> str:
    status = candidate.get("market_status") or {}
    if isinstance(status, dict) and "is_open" in status:
        return "offen" if status.get("is_open") else "geschlossen"
    text = str(candidate.get("market_status_text") or "").strip()
    return text or "manuell pruefen"


def last_price_text(candidate: dict) -> str:
    quote = candidate.get("quote") or {}
    price = _float_text(quote.get("price") if isinstance(quote, dict) else None)
    if not price:
        price = _float_text(candidate.get("last_price"))
    currency = str(candidate.get("currency") or (quote.get("currency") if isinstance(quote, dict) else "") or "").strip().upper()
    if not price:
        return "manuell pruefen"
    return f"{price} {currency}".strip()


def entry_hint_text(candidate: dict) -> str:
    text = str(candidate.get("entry_hint") or candidate.get("entry") or "").strip()
    return text or "Einstieg manuell pruefen"


def stop_hint_text(candidate: dict) -> str:
    text = str(candidate.get("stop_hint") or candidate.get("stop_loss_hint") or candidate.get("stop_loss") or candidate.get("stop") or "").strip()
    return text or "Stop-Loss manuell pruefen"


def stop_loss_price_text(candidate: dict) -> str:
    return _float_text(candidate.get("stop_loss_price"))


def stop_distance_pct_text(candidate: dict) -> str:
    return _float_text(candidate.get("stop_distance_pct"))


def risk_eur_text(candidate: dict) -> str:
    text = _float_text(candidate.get("risk_eur"))
    return text or "manuell pruefen"


def position_size_hint(signal_strength: object) -> str:
    label = normalize_confidence(signal_strength)
    if label == "hoch":
        return "Mittlere bis groessere Positionsgroesse pruefen. Vorschlag: 1.000 bis 1.500 EUR."
    if label == "mittel":
        return "Kleine bis mittlere Positionsgroesse pruefen. Vorschlag: 750 bis 1.000 EUR."
    return "Nur kleine Testgroesse pruefen. Vorschlag: bis 500 EUR."


def sell_exit_hint(defense: dict) -> str:
    reasons = _reason_keys((defense.get("sell_reasons") or defense.get("reasons") or []))
    if reasons & {"negative_momentum_strong", "strong_selloff", "starker_abverkauf"}:
        return "Schwaeche bestaetigen und Exit-Level manuell festlegen."
    if reasons & {"news_burden", "negative_news"}:
        return "Belastende Nachrichtenlage gegen den Depotkontext pruefen und Exit-Level manuell festlegen."
    return "Teilverkauf oder Verkauf mit Blick auf Depotgewicht manuell pruefen."


def sell_size_hint(defense: dict, market_regime: object) -> str:
    reasons = _reason_keys((defense.get("sell_reasons") or defense.get("reasons") or []))
    sell_score = float((defense.get("sell_score") or defense.get("defense_score") or 0) or 0)
    high_weight = bool(reasons & {"high_weight", "very_high_weight", "grosses_positionsgewicht"})
    bad_news = bool(reasons & {"news_burden", "negative_news"})
    strong_weakness = bool(reasons & {"negative_momentum_strong", "strong_selloff", "starker_abverkauf"}) or sell_score >= 7
    if strong_weakness and bad_news and high_weight:
        return "Teilverkauf oder Vollverkauf pruefen."
    if market_label(market_regime) == "defensiv" and high_weight:
        return "Risikoabbau bevorzugen."
    if sell_score >= 5:
        return "Teilverkauf pruefen."
    return ""


def interpretation(candidate: dict) -> str:
    classification = classification_label(candidate.get("classification"), candidate)
    reasons = human_reasons((candidate.get("opportunity_score") or {}).get("reasons", []))
    if classification == "KAUFEN PRUEFEN":
        return "Mehrere Faktoren sprechen fuer eine interessante Lage. Einstieg und Groesse koennen jetzt geprueft werden."
    if classification == "VERKAUFEN PRUEFEN":
        return "Die Position zeigt klare Schwaeche. Verkauf oder Teilverkauf sollten jetzt geprueft werden."
    if classification == "RISIKO REDUZIEREN":
        return "Das Risiko in der Position steigt. Eine kleinere Groesse sollte geprueft werden."
    if "Depotrelevanz" in reasons or _is_holding(candidate):
        return "Die Position wirkt aktuell intakt. Ein neuer Eingriff ist derzeit nicht noetig."
    return "Der Titel bleibt interessant, aber aktuell steht kein schneller Eingriff im Vordergrund."
