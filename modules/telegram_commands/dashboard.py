from __future__ import annotations

from modules.common.utils import now_iso_tz
from modules.health.report import collect_health_report
from modules.organism.monthly_evaluation import build_monthly_evaluation
from modules.portfolio_status.snapshot import build_portfolio_status
from modules.v2.marketdata.api_governor import status_snapshot
from modules.virus_bridge.execution_report import build_execution_report
from modules.virus_bridge.trade_candidate import load_recent_trade_candidates


SEVERITY_ICON = {
    "normal": "🟢",
    "pruefen": "🟡",
    "kritisch": "🔴",
}


def _fmt_money(value: object) -> str:
    try:
        return f"{float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " EUR"
    except (TypeError, ValueError):
        return "nicht belastbar"


def _dedupe(items: list[tuple[str, str]]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        if item in seen:
            continue
        out.append(item)
        seen.add(item)
    return out


def collect_operator_warning_items(cfg: dict) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    health = collect_health_report(cfg)
    checks = health.get("checks", {})
    api = status_snapshot(cfg)
    portfolio = build_portfolio_status(cfg)
    execution = build_execution_report(cfg)
    monthly = build_monthly_evaluation(cfg)
    candidates = load_recent_trade_candidates(cfg, limit=8)

    if str(health.get("overall_status") or "").lower() != "ok":
        items.append(("kritisch", "Desk-Zustand nicht sauber"))
    if str(api.get("mode") or "").lower() == "blocked":
        items.append(("kritisch", "API- oder Betriebsstress"))
    elif str(api.get("mode") or "").lower() == "degraded" or bool(api.get("scanner_throttled")):
        items.append(("pruefen", "API- oder Betriebsstress"))

    freshness = str(portfolio.get("freshness_status") or "").upper()
    if freshness in {"VERALTET", "TEILWEISE_AKTUELL"}:
        items.append(("pruefen", "Daten veraltet"))
    if str(portfolio.get("source_type") or "").upper() == "TELEGRAM_AUSFUEHRUNGEN":
        items.append(("pruefen", "Kein bestaetigter Depotauszug"))

    summary = execution.get("summary") or {}
    if int((execution.get("source_details") or {}).get("executions_count") or 0) == 0:
        items.append(("pruefen", "Keine echten Ausfuehrungen"))
    if int(summary.get("unpriced_open_total") or 0) > 0:
        items.append(("pruefen", "Fehlende Quotes fuer offene PnL"))

    cost_status = str(execution.get("cost_coverage_status") or "").upper()
    if cost_status == "NICHT_GEDECKT":
        items.append(("kritisch", "Kosten nicht gedeckt"))
    elif cost_status in {"NAHE_BREAK_EVEN", "NOCH_NICHT_BEWERTBAR"}:
        items.append(("pruefen", "Kostenlage noch offen"))

    if any(not bool(row.get("operational_is_actionable", True)) for row in candidates):
        items.append(("pruefen", "Unvollstaendige Kaufideen"))

    market_states = [
        bool((row.get("market_status") or {}).get("is_open"))
        for row in candidates
        if isinstance(row.get("market_status"), dict) and "is_open" in (row.get("market_status") or {})
    ]
    if market_states and not any(market_states):
        items.append(("pruefen", "Markt geschlossen"))

    economics = monthly.get("economics", {}) if isinstance(monthly, dict) else {}
    if str(economics.get("cost_coverage_status") or "").upper() == "NICHT_GEDECKT":
        items.append(("kritisch", "Monatskosten nicht gedeckt"))

    critical_checks = {
        "portfolio_ingest": "Portfolio-Daten fehlen",
        "marketdata": "Marktdaten stoeren",
        "news": "Nachrichtenlage stoert",
        "signals": "Signalschicht stoert",
        "telegram": "Telegram stoert",
    }
    for key, label in critical_checks.items():
        if str(checks.get(key) or "").lower() not in {"ok", "missing_mapping_only", "0_signals", "input_missing", "no_feeds", "missing_env", "skipped_no_pdf"}:
            items.append(("kritisch", label))

    return _dedupe(items)


def _warning_rollup(items: list[tuple[str, str]]) -> str:
    critical = sum(1 for severity, _ in items if severity == "kritisch")
    check = sum(1 for severity, _ in items if severity == "pruefen")
    if critical == 0 and check == 0:
        return f"{SEVERITY_ICON['normal']} normal"
    parts: list[str] = []
    if critical:
        parts.append(f"{SEVERITY_ICON['kritisch']} {critical} kritisch")
    if check:
        parts.append(f"{SEVERITY_ICON['pruefen']} {check} pruefen")
    return " | ".join(parts)


def _desk_state(items: list[tuple[str, str]]) -> tuple[str, str]:
    if any(severity == "kritisch" for severity, _ in items):
        return SEVERITY_ICON["kritisch"], "kritisch"
    if any(severity == "pruefen" for severity, _ in items):
        return SEVERITY_ICON["pruefen"], "pruefen"
    return SEVERITY_ICON["normal"], "normal"


def _market_status(cfg: dict) -> tuple[str, str]:
    candidates = load_recent_trade_candidates(cfg, limit=8)
    states = [
        bool((row.get("market_status") or {}).get("is_open"))
        for row in candidates
        if isinstance(row.get("market_status"), dict) and "is_open" in (row.get("market_status") or {})
    ]
    if not states:
        return SEVERITY_ICON["pruefen"], "unklar"
    if any(states) and any(not value for value in states):
        return SEVERITY_ICON["pruefen"], "teils offen"
    if any(states):
        return SEVERITY_ICON["normal"], "offen"
    return SEVERITY_ICON["pruefen"], "geschlossen"


def _portfolio_line(cfg: dict) -> str:
    status = build_portfolio_status(cfg)
    positions = int(status.get("positions_count", 0) or 0)
    gross = status.get("gross_value_eur")
    if positions <= 0 and gross in (None, 0):
        return "kein belastbarer Stand"
    return f"{positions} Positionen | {_fmt_money(gross)}"


def _cost_line(cfg: dict) -> str:
    report = build_execution_report(cfg)
    status = str(report.get("cost_coverage_status") or "NOCH_NICHT_BEWERTBAR").upper()
    mapping = {
        "KOSTEN_GEDECKT": (SEVERITY_ICON["normal"], "gedeckt"),
        "NAHE_BREAK_EVEN": (SEVERITY_ICON["pruefen"], "nahe Break-even"),
        "NICHT_GEDECKT": (SEVERITY_ICON["kritisch"], "nicht gedeckt"),
        "NOCH_NICHT_BEWERTBAR": (SEVERITY_ICON["pruefen"], "noch nicht bewertbar"),
    }
    icon, label = mapping.get(status, (SEVERITY_ICON["pruefen"], status.replace("_", " ").lower()))
    return f"{icon} {label}"


def render_desk_card(cfg: dict) -> str:
    warnings = collect_operator_warning_items(cfg)
    desk_icon, desk_label = _desk_state(warnings)
    market_icon, market_label = _market_status(cfg)
    lines = [
        "CB Fund Desk",
        "",
        "Stand:",
        now_iso_tz(cfg.get("app", {}).get("timezone", "Europe/Berlin"))[:16].replace("T", " "),
        "",
        "Desk-Zustand:",
        f"{desk_icon} {desk_label}",
        "",
        "Markt:",
        f"{market_icon} {market_label}",
        "",
        "Portfolio:",
        _portfolio_line(cfg),
        "",
        "Kosten:",
        _cost_line(cfg),
        "",
        "Warnlagen:",
        _warning_rollup(warnings),
    ]
    return "\n".join(lines)[:1400]


def render_warning_summary(cfg: dict) -> str:
    warnings = collect_operator_warning_items(cfg)
    desk_icon, desk_label = _desk_state(warnings)
    lines = [
        "CB Fund Desk - Warnlagen",
        "",
        "Stand:",
        now_iso_tz(cfg.get("app", {}).get("timezone", "Europe/Berlin"))[:16].replace("T", " "),
        "",
        "Lage:",
        f"{desk_icon} {desk_label}",
        "",
        "Kurzstand:",
        _warning_rollup(warnings),
    ]
    if not warnings:
        lines.extend(["", "Aktuell:", f"- {SEVERITY_ICON['normal']} Keine akuten Warnlagen"])
        return "\n".join(lines)[:1500]
    lines.extend(["", "Aktuell:"] + [f"- {SEVERITY_ICON[severity]} {label}" for severity, label in warnings[:8]])
    return "\n".join(lines)[:1500]
