from __future__ import annotations

from modules.common.operator_warnings import warning_lines
from modules.common.runtime_dirs import ensure_runtime_directories
from modules.portfolio_status.snapshot import (
    build_portfolio_status,
    load_latest_portfolio_snapshot,
    load_manual_execution_count_since_snapshot,
)


def _format_timestamp(value: object) -> str:
    from modules.portfolio_status.snapshot import _parse_timestamp

    dt = _parse_timestamp(value)
    return dt.strftime("%d.%m.%Y %H:%M") if dt else "noch nicht vorhanden"


def _format_eur(value: object) -> str:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "nicht belastbar verfuegbar"
    text = f"{amount:,.2f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".") + " EUR"


def _label(value: object) -> str:
    return str(value or "UNBEKANNT").replace("_", " ")


def _warning_lines(status: dict) -> list[str]:
    source_type = str(status.get("source_type") or "").upper()
    freshness = str(status.get("freshness_status") or "").upper()
    confidence = str(status.get("confidence_status") or "").upper()
    warnings: list[tuple[str, str]] = []
    if freshness == "VERALTET":
        warnings.append(("VERALTET", "Portfolio-Stand veraltet"))
    elif freshness == "TEILWEISE_AKTUELL":
        warnings.append(("VERALTET", "Portfolio-Stand nur teilweise aktuell"))
    if confidence == "NIEDRIG":
        warnings.append(("VERALTET", "Datenqualitaet niedrig"))
    if source_type == "TELEGRAM_AUSFUEHRUNGEN":
        warnings.append(("NOCH_NICHT_BEWERTBAR", "Kein bestaetigter Depotauszug vorhanden"))
    elif source_type == "GEMISCHT":
        warnings.append(("UNVOLLSTAENDIG", "Stand enthaelt zusaetzliche manuelle Ausfuehrungen"))
    return warning_lines(warnings)


def render_portfolio_status(cfg) -> str:
    ensure_runtime_directories(cfg)
    status = build_portfolio_status(cfg)
    warnings = _warning_lines(status)
    lines = [
        "CB Fund Desk - Portfolio",
        "",
        "Stand:",
        _format_timestamp(status.get("created_at")),
        "",
        "Quelle:",
        _label(status.get("source_type")),
        "",
        "Frische:",
        _label(status.get("freshness_status")),
        "",
        "Datenqualitaet:",
        _label(status.get("confidence_status")),
        "",
        "Positionen:",
        str(int(status.get("positions_count", 0) or 0)),
        "",
        "Depotwert:",
        _format_eur(status.get("gross_value_eur")),
        "",
        "Freies Budget:",
        _format_eur(status.get("free_budget_eur")),
    ]
    cash_eur = status.get("cash_eur")
    if cash_eur is not None:
        lines.extend(["", "Cash:", _format_eur(cash_eur)])
    if warnings:
        lines.extend(["", "Warnlage:"] + [f"- {item}" for item in warnings])
    lines.extend(["", "Hinweis:", str(status.get("notes") or "Es liegt noch kein belastbarer Portfolio-Stand vor.")])
    return "\n".join(lines)[:1800]
