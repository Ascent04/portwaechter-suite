from __future__ import annotations

from datetime import datetime

from modules.virus_bridge.execution_performance import load_executed_tickets, load_exit_records


def _parse_ts(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    for candidate in (text, text.replace("Z", "+00:00")):
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            continue
        return parsed.astimezone().replace(tzinfo=None) if parsed.tzinfo else parsed
    return None


def _period_bounds(period: str | None = None) -> tuple[str, datetime, datetime]:
    text = str(period or datetime.now().strftime("%Y-%m")).strip()
    year, month = [int(part) for part in text.split("-", 1)]
    start = datetime(year, month, 1)
    end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    return f"{year:04d}-{month:02d}", start, end


def _in_period(value: object, start: datetime, end: datetime) -> bool:
    parsed = _parse_ts(value)
    return parsed is not None and start <= parsed < end


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return default


def _realized_pnl_value(row: dict) -> float | None:
    try:
        return round(float(row.get("realized_pnl_eur")), 2)
    except (TypeError, ValueError):
        return None


def build_cost_status(cfg: dict, period: str | None = None) -> dict:
    period_key, start, end = _period_bounds(period)
    settings = cfg.get("organism_evaluation", {}) if isinstance(cfg.get("organism_evaluation"), dict) else {}
    monthly_cost_usd = _safe_float(settings.get("monthly_cost_usd"), 30.0) or 30.0
    eurusd_rate = _safe_float(settings.get("eurusd_rate_assumption"), 0.92) or 0.92
    operating_cost_eur = round(monthly_cost_usd * eurusd_rate, 2)

    executed_entries = [row for row in load_executed_tickets(cfg) if _in_period(row.get("entry_timestamp"), start, end)]
    realized_exits = [row for row in load_exit_records(cfg) if _in_period(row.get("timestamp"), start, end)]
    realized_values = [_realized_pnl_value(row) for row in realized_exits]
    realized_complete = all(value is not None for value in realized_values)
    realized_before_costs = round(sum(value for value in realized_values if value is not None), 2) if realized_complete else None
    realized_after_costs = round(realized_before_costs - operating_cost_eur, 2) if realized_before_costs is not None else None
    activity_count = len(executed_entries) + len(realized_exits)

    if activity_count == 0:
        status = "NOCH_NICHT_BEWERTBAR"
        explanation = "Es liegen im betrachteten Monat noch keine echten manuellen Ausfuehrungen vor."
    elif not realized_complete:
        status = "NOCH_NICHT_BEWERTBAR"
        explanation = "Mindestens ein Exit ist im betrachteten Monat nicht voll erfasst. Die reale Kosten- und Performancebewertung bleibt deshalb eingeschraenkt."
    elif realized_after_costs >= 0:
        status = "KOSTEN_GEDECKT"
        explanation = "Die realisierte Performance deckt die laufende Kostenhuerde im betrachteten Zeitraum."
    elif realized_after_costs >= -5.0:
        status = "NAHE_BREAK_EVEN"
        explanation = "Die realisierte Performance liegt nahe an der laufenden Kostenhuerde, deckt sie aber noch nicht sauber."
    else:
        status = "NICHT_GEDECKT"
        explanation = "Der Desk war aktiv, hat die laufende Kostenhuerde im betrachteten Zeitraum aber noch nicht gedeckt."

    return {
        "period": period_key,
        "realized_pnl_before_costs": realized_before_costs,
        "operating_cost_reference": {
            "amount_usd": round(monthly_cost_usd, 2),
            "currency": "USD",
            "period": "month",
            "eur_estimate": operating_cost_eur,
            "eurusd_rate_assumption": round(eurusd_rate, 4),
            "label": f"{monthly_cost_usd:.0f} USD pro Monat",
        },
        "realized_pnl_after_costs": realized_after_costs,
        "cost_coverage_status": status,
        "realized_pnl_complete": realized_complete,
        "manual_activity_count": activity_count,
        "executed_entries_count": len(executed_entries),
        "realized_exit_count": len(realized_exits),
        "explanation": explanation,
    }
