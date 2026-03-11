from __future__ import annotations

from pathlib import Path

from modules.common.utils import read_json
from modules.v2.config import data_dir
from modules.v2.telegram.copy import (
    candidate_label,
    candidate_name,
    classification_label,
    display_name,
    format_score,
    human_reasons,
    interpretation,
    market_label,
    normalize_confidence,
)


def _latest_recommendations_path(cfg: dict) -> Path | None:
    files = sorted(data_dir(cfg).glob("recommendations_*.json"))
    return files[-1] if files else None


def load_latest_recommendations(cfg: dict) -> list[dict]:
    path = _latest_recommendations_path(cfg)
    if path is None or not path.exists():
        return []
    data = read_json(path)
    if not isinstance(data, dict):
        return []
    rows = data.get("recommendations", [])
    return rows if isinstance(rows, list) else []


def _example_symbol(latest_recommendations: list[dict] | None = None) -> str:
    for candidate in latest_recommendations or []:
        symbol = str(candidate.get("symbol") or "").strip()
        if symbol:
            return symbol
    return "BAYN.DE"


def _score(candidate: dict) -> str:
    if str(candidate.get("classification") or "").upper() == "DEFENSE":
        label = classification_label(candidate.get("classification"), candidate)
        defense = candidate.get("defense_score") or {}
        if label == "VERKAUFEN PRUEFEN":
            return format_score(defense.get("sell_score") or defense.get("defense_score"))
        return format_score(defense.get("risk_reduce_score") or defense.get("defense_score"))
    return format_score((candidate.get("opportunity_score") or {}).get("total_score"))


def _signal_strength(candidate: dict) -> str:
    if str(candidate.get("classification") or "").upper() == "DEFENSE":
        label = classification_label(candidate.get("classification"), candidate)
        defense = candidate.get("defense_score") or {}
        score = float(
            (
                defense.get("sell_score")
                if label == "VERKAUFEN PRUEFEN"
                else defense.get("risk_reduce_score")
            )
            or defense.get("defense_score", 0)
            or 0
        )
        if score >= 7:
            return "hoch"
        if score >= 5:
            return "mittel"
        return "spekulativ"
    return normalize_confidence((candidate.get("opportunity_score") or {}).get("confidence"))


def _reason_lines(candidate: dict) -> str:
    if str(candidate.get("classification") or "").upper() == "DEFENSE":
        label = classification_label(candidate.get("classification"), candidate)
        defense = candidate.get("defense_score") or {}
        values = defense.get("sell_reasons", []) if label == "VERKAUFEN PRUEFEN" else defense.get("risk_reduce_reasons", []) or defense.get("reasons", [])
    else:
        values = (candidate.get("opportunity_score") or {}).get("reasons", [])
    reasons = human_reasons(values)
    return "\n".join(f"- {reason}" for reason in reasons) if reasons else "- Keine klaren Einzelgruende"


def render_example_text(candidate: dict) -> str:
    return (
        f"{candidate_label(candidate)}\n\n"
        f"Typ: {classification_label(candidate.get('classification'), candidate)}\n"
        f"Score: {_score(candidate)}\n"
        f"Signalstaerke: {_signal_strength(candidate)}\n"
        f"Marktlage: {market_label(candidate.get('regime'))}\n\n"
        f"Warum jetzt relevant:\n{_reason_lines(candidate)}\n\n"
        f"Einordnung:\n{interpretation(candidate)}"
    )[:1800]


def render_help_text(latest_recommendations: list[dict] | None = None, cfg: dict | None = None) -> str:
    example = _example_symbol(latest_recommendations)
    return (
        f"{display_name(cfg)} Hilfe\n\n"
        "KAUFEN PRUEFEN\n"
        "Ein Einstieg kann jetzt naeher geprueft werden.\n\n"
        "HALTEN\n"
        "Aktuell kein akuter Eingriff. Position weiter begleiten.\n\n"
        "VERKAUFEN PRUEFEN\n"
        "Das Bild wird schwaecher. Ausstieg oder Teilverkauf pruefen.\n\n"
        "RISIKO REDUZIEREN\n"
        "Die Position wirkt riskanter. Groesse und Absicherung pruefen.\n\n"
        "Signalstaerke\n"
        "hoch = staerkeres Signal\n"
        "mittel = brauchbar\n"
        "spekulativ = fruehes oder unsicheres Signal\n\n"
        "Wichtige Befehle:\n"
        "/status - Systemlage und Warnungen\n"
        "/portfolio - letzter belastbarer Depotstand\n"
        "/execution - echte Trades, Teilverkaeufe und PnL\n"
        "/proposals - offene Ideen und Ticket-Reife\n"
        "/tickets - offene Tickets und Positionen\n"
        "/organism - Monatsbewertung und Kostenlage\n"
        "/help - Kurzhilfe\n\n"
        "Weitere Befehle:\n"
        "/top - wichtigste Signale\n"
        "/meaning - Bedeutung der Meldungen\n"
        "/alerts - Alert-Profil und Schwellwerte\n"
        "/ticket <ticket_id> - Ticket-Details\n"
        f"/why {example} - Begruendung zu einem Titel"
    )[:1800]


def render_meaning_text(latest_recommendations: list[dict] | None = None, cfg: dict | None = None) -> str:
    example = _example_symbol(latest_recommendations)
    return (
        f"Bedeutung der Meldungen in {display_name(cfg)}\n\n"
        "KAUFEN PRUEFEN\n"
        "Mehrere Faktoren sprechen fuer einen moeglichen Einstieg.\n\n"
        "HALTEN\n"
        "Die Lage bleibt stabil genug, um die Position weiter laufen zu lassen.\n\n"
        "VERKAUFEN PRUEFEN\n"
        "Das Setup schwaecht sich ab. Ein Ausstieg sollte geprueft werden.\n\n"
        "RISIKO REDUZIEREN\n"
        "Das Risiko in der Position steigt. Eine kleinere Groesse kann sinnvoll sein.\n\n"
        "Score\n"
        "Je hoeher der Score, desto staerker die Signalqualitaet.\n\n"
        "Signalstaerke\n"
        "hoch = starke Gesamtlage\n"
        "mittel = solide Beobachtung\n"
        "spekulativ = fruehes Signal mit hoeherer Unsicherheit\n\n"
        "Marktlage\n"
        "positiv = Markt eher aufnahmebereit\n"
        "neutral = gemischte Lage\n"
        "defensiv = vorsichtiges Umfeld\n\n"
        "Beispielbefehle:\n"
        f"/why {example}\n"
        "/execution\n"
        "/organism\n"
        "/top\n"
        "/proposals"
    )[:1800]


def render_top_text(latest_recommendations: list[dict], cfg: dict | None = None) -> str:
    if not latest_recommendations:
        return "Noch keine V2-Empfehlungen verfuegbar."

    lines = [f"{display_name(cfg)} Top Signale", ""]
    for label in ("VERKAUFEN PRUEFEN", "RISIKO REDUZIEREN", "KAUFEN PRUEFEN", "HALTEN"):
        rows = [row for row in latest_recommendations if classification_label(row.get("classification"), row) == label]
        rows.sort(key=lambda row: float(_score(row)), reverse=True)
        lines.append(f"{label.title()}:")
        if not rows:
            lines.append("- keine")
        else:
            for row in rows[:3]:
                lines.append(f"- {candidate_name(row)} ({_score(row)})")
        lines.append("")

    regime = market_label(next((row.get("regime") for row in latest_recommendations if row.get("regime")), "neutral"))
    lines.append(f"Marktlage: {regime}")
    return "\n".join(lines).strip()[:1800]


def explain_candidate(symbol_or_isin: str, latest_recommendations: list[dict]) -> str:
    needle = str(symbol_or_isin or "").strip().upper()
    if not needle:
        return "Bitte: /why <symbol|isin>"

    for candidate in latest_recommendations:
        symbol = str(candidate.get("symbol") or "").strip().upper()
        isin = str(candidate.get("isin") or "").strip().upper()
        if needle not in {symbol, isin}:
            continue
        return (
            f"{candidate_label(candidate)}\n\n"
            f"Typ: {classification_label(candidate.get('classification'), candidate)}\n"
            f"Score: {_score(candidate)}\n"
            f"Signalstaerke: {_signal_strength(candidate)}\n"
            f"Marktlage: {market_label(candidate.get('regime'))}\n\n"
            f"Warum jetzt relevant:\n{_reason_lines(candidate)}\n\n"
            f"Einordnung:\n{interpretation(candidate)}"
        )[:1800]

    return f"Kein Kandidat fuer '{symbol_or_isin}' in den letzten Empfehlungen gefunden."
