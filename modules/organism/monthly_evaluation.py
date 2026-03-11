from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from modules.common.utils import now_iso_tz, read_json
from modules.v2.telegram.copy import candidate_name, classification_label
from modules.virus_bridge.cost_status import build_cost_status
from modules.virus_bridge.execution_performance import _build_all_positions, load_exit_records
from modules.virus_bridge.lifecycle import load_lifecycle
from modules.virus_bridge.trade_candidate import load_trade_candidate


def _root_dir(cfg: dict) -> Path:
    return Path(cfg.get("app", {}).get("root_dir", Path.cwd()))


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


def _period_bounds(period: str | None) -> tuple[str, datetime, datetime]:
    text = str(period or datetime.now().strftime("%Y-%m")).strip()
    year, month = [int(part) for part in text.split("-", 1)]
    start = datetime(year, month, 1)
    end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    return f"{year:04d}-{month:02d}", start, end


def _in_period(dt: datetime | None, start: datetime, end: datetime) -> bool:
    return dt is not None and start <= dt < end


def _mtime(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime)


def _safe_float(value: object) -> float:
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return 0.0


def _safe_optional_float(value: object) -> float | None:
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


def _latest_trade_candidate_risk(ticket_id: str, cfg: dict) -> float | None:
    trade_candidate = load_trade_candidate(ticket_id, cfg) or {}
    risk = trade_candidate.get("risk_eur")
    try:
        return round(float(risk), 2)
    except (TypeError, ValueError):
        return None


def _activity_metrics(cfg: dict, start: datetime, end: datetime) -> dict:
    root = _root_dir(cfg)
    recommendations_total = 0
    buckets = {"KAUFEN PRUEFEN": 0, "VERKAUFEN PRUEFEN": 0, "RISIKO REDUZIEREN": 0, "HALTEN": 0}
    scanner_runs = 0
    for path in sorted((root / "data" / "v2").glob("recommendations_*.json")):
        if not _in_period(_mtime(path), start, end):
            continue
        scanner_runs += 1
        try:
            payload = read_json(path)
        except Exception:
            continue
        rows = payload.get("recommendations", []) if isinstance(payload, dict) else []
        for row in rows if isinstance(rows, list) else []:
            recommendations_total += 1
            label = classification_label((row.get("user_classification") or row.get("classification")), row)
            if label in buckets:
                buckets[label] += 1

    trade_candidates_total = sum(1 for path in (root / "data" / "virus_bridge" / "trade_candidates").rglob("ticket_*.json") if _in_period(_mtime(path), start, end))
    executed_total = 0
    partial_exits_total = 0
    closed_total = 0
    lifecycle_root = root / "data" / "virus_bridge" / "ticket_lifecycle"
    for path in sorted(lifecycle_root.glob("*.json")):
        lifecycle = load_lifecycle(path.stem, cfg)
        if not lifecycle:
            continue
        events = lifecycle.get("events", [])
        for event in events if isinstance(events, list) else []:
            event_dt = _parse_ts(event.get("timestamp"))
            if not _in_period(event_dt, start, end):
                continue
            event_type = str(event.get("event_type") or "").upper()
            if event_type == "TRADE_EXECUTED_MANUAL":
                executed_total += 1
            elif event_type == "TRADE_PARTIAL_EXIT":
                partial_exits_total += 1
            elif event_type in {"TRADE_CLOSED_MANUAL", "TRADE_CLOSED_STOP_LOSS", "TRADE_CLOSED_TARGET_REACHED"}:
                closed_total += 1

    return {
        "scanner_runs": scanner_runs,
        "recommendations_total": recommendations_total,
        "kaufen_pruefen_total": buckets["KAUFEN PRUEFEN"],
        "verkaufen_pruefen_total": buckets["VERKAUFEN PRUEFEN"],
        "risiko_reduzieren_total": buckets["RISIKO REDUZIEREN"],
        "halten_total": buckets["HALTEN"],
        "trade_candidates_total": trade_candidates_total,
        "executed_total": executed_total,
        "partial_exits_total": partial_exits_total,
        "closed_total": closed_total,
    }


def _performance_metrics(cfg: dict, start: datetime, end: datetime) -> tuple[dict, list[dict]]:
    positions = _build_all_positions(cfg)
    exits = [row for row in load_exit_records(cfg) if _in_period(_parse_ts(row.get("timestamp")), start, end)]
    realized_values = [_safe_optional_float(row.get("realized_pnl_eur")) for row in exits]
    realized_complete = all(value is not None for value in realized_values)
    realized_total = round(sum(value for value in realized_values if value is not None), 2) if realized_complete else None
    unrealized_total = round(sum(_safe_float(row.get("unrealized_pnl_eur")) for row in positions if row.get("status") in {"OPEN", "PARTIALLY_CLOSED"}), 2)
    closed_positions = [row for row in positions if row.get("status") == "CLOSED" and _in_period(_parse_ts(row.get("latest_exit_timestamp")), start, end)]
    closed_pcts = [float(row.get("realized_pnl_pct") or 0) for row in closed_positions]
    wins = [pct for pct in closed_pcts if pct > 0]
    best = max(closed_positions, key=lambda row: float(row.get("realized_pnl_pct") or 0), default=None)
    worst = min(closed_positions, key=lambda row: float(row.get("realized_pnl_pct") or 0), default=None)
    return (
        {
            "realized_pnl_eur_total": realized_total,
            "realized_pnl_complete": realized_complete,
            "unrealized_pnl_eur_total": unrealized_total,
            "avg_closed_pnl_pct": round(sum(closed_pcts) / len(closed_pcts), 4) if closed_pcts else None,
            "win_rate_closed": round((len(wins) / len(closed_pcts)) * 100.0, 2) if closed_pcts else None,
            "best_trade": {"name": candidate_name(best.get("asset") or {}), "pnl_pct": round(float(best.get("realized_pnl_pct") or 0), 2)} if best else None,
            "worst_trade": {"name": candidate_name(worst.get("asset") or {}), "pnl_pct": round(float(worst.get("realized_pnl_pct") or 0), 2)} if worst else None,
        },
        positions,
    )


def _risk_metrics(cfg: dict, positions: list[dict]) -> dict:
    active = [row for row in positions if row.get("status") in {"OPEN", "PARTIALLY_CLOSED"}]
    exposures = [float(row.get("remaining_size_eur") or 0) for row in active]
    risk_values = [risk for risk in (_latest_trade_candidate_risk(str(row.get("ticket_id") or ""), cfg) for row in active) if risk is not None]
    return {
        "open_positions_total": len([row for row in positions if row.get("status") == "OPEN"]),
        "partially_closed_total": len([row for row in positions if row.get("status") == "PARTIALLY_CLOSED"]),
        "total_open_exposure_eur": round(sum(exposures), 2),
        "largest_open_position_eur": round(max(exposures), 2) if exposures else 0.0,
        "largest_open_risk_eur": round(max(risk_values), 2) if risk_values else None,
    }


def _api_metrics(cfg: dict, start: datetime, end: datetime) -> dict:
    root = _root_dir(cfg) / "data" / "api_governor"
    rows: list[dict] = []
    for path in sorted(root.glob("usage_*.jsonl")):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            event_dt = _parse_ts(payload.get("timestamp"))
            if _in_period(event_dt, start, end):
                rows.append(payload)
    api_calls_total = round(sum(_safe_float(row.get("cost")) for row in rows), 2)
    per_minute: dict[str, float] = defaultdict(float)
    degraded_minutes: set[str] = set()
    blocked_minutes: set[str] = set()
    days: set[str] = set()
    for row in rows:
        event_dt = _parse_ts(row.get("timestamp"))
        if event_dt is None:
            continue
        minute_key = event_dt.strftime("%Y-%m-%dT%H:%M")
        day_key = event_dt.strftime("%Y-%m-%d")
        per_minute[minute_key] += _safe_float(row.get("cost"))
        days.add(day_key)
        mode = str(row.get("mode") or "normal").lower()
        if mode == "degraded":
            degraded_minutes.add(minute_key)
        if mode == "blocked":
            blocked_minutes.add(minute_key)
    return {
        "api_calls_total": api_calls_total,
        "avg_calls_per_day": round(api_calls_total / len(days), 2) if days else 0.0,
        "max_calls_in_minute_seen": round(max(per_minute.values()), 2) if per_minute else 0.0,
        "blocked_runs_total": len(blocked_minutes),
        "degraded_runs_total": len(degraded_minutes),
    }


def _economics_metrics(performance: dict, cost_status: dict) -> dict:
    reference = cost_status.get("operating_cost_reference") if isinstance(cost_status.get("operating_cost_reference"), dict) else {}
    monthly_cost_usd = _safe_float(reference.get("amount_usd") or 30)
    eurusd = _safe_float(reference.get("eurusd_rate_assumption") or 0.92)
    monthly_cost_eur = _safe_optional_float(reference.get("eur_estimate"))
    realized = _safe_optional_float(cost_status.get("realized_pnl_before_costs"))
    realized_after_cost = _safe_optional_float(cost_status.get("realized_pnl_after_costs"))
    unrealized = _safe_optional_float(performance.get("unrealized_pnl_eur_total"))
    total_minus_cost = None
    if realized_after_cost is not None and unrealized is not None:
        total_minus_cost = round(realized_after_cost + unrealized, 2)
    return {
        "monthly_cost_usd": monthly_cost_usd,
        "eurusd_rate_assumption": eurusd,
        "monthly_cost_eur_estimate": monthly_cost_eur,
        "realized_pnl_before_costs": realized,
        "realized_pnl_minus_cost_eur": realized_after_cost,
        "total_pnl_minus_cost_eur": total_minus_cost,
        "cost_coverage_status": cost_status.get("cost_coverage_status"),
        "realized_pnl_complete": bool(cost_status.get("realized_pnl_complete", False)),
        "manual_activity_count": int(cost_status.get("manual_activity_count") or 0),
        "executed_entries_count": int(cost_status.get("executed_entries_count") or 0),
        "realized_exit_count": int(cost_status.get("realized_exit_count") or 0),
        "operating_cost_reference": reference,
        "cost_status_explanation": cost_status.get("explanation"),
    }


def evaluate_organism(report_data, cfg) -> dict:
    activity = report_data.get("activity", {})
    performance = report_data.get("performance", {})
    api = report_data.get("api", {})
    economics = report_data.get("economics", {})
    actionable = int(activity.get("kaufen_pruefen_total", 0) or 0) + int(activity.get("verkaufen_pruefen_total", 0) or 0)
    executed = int(economics.get("executed_entries_count") or activity.get("executed_total", 0) or 0)
    realized_after_cost = _safe_optional_float(economics.get("realized_pnl_minus_cost_eur"))
    cost_coverage_status = str(economics.get("cost_coverage_status") or "").upper()
    realized_complete = bool(economics.get("realized_pnl_complete", True))
    blocked = int(api.get("blocked_runs_total", 0) or 0)
    degraded = int(api.get("degraded_runs_total", 0) or 0)
    max_calls_in_minute = float(api.get("max_calls_in_minute_seen", 0) or 0)
    api_cfg = cfg.get("api_governor", {}) if isinstance(cfg.get("api_governor"), dict) else {}
    minute_limit_hard = float(api_cfg.get("minute_limit_hard", 55) or 55)
    realized = _safe_optional_float(performance.get("realized_pnl_eur_total"))
    win_rate = performance.get("win_rate_closed")
    reasons: list[str] = []
    api_stress = blocked > 0 or degraded >= 3 or (minute_limit_hard > 0 and max_calls_in_minute > minute_limit_hard)
    weak_real_performance = executed > 0 and realized_complete and (
        (realized is not None and realized < 0)
        or (realized_after_cost is not None and realized_after_cost < 0)
        or (win_rate is not None and float(win_rate) < 40.0)
    )

    if executed == 0 and not api_stress:
        reasons = [
            "Keine echten manuellen Echtgeld-Ausfuehrungen im Zeitraum",
            "Die Leistungsbewertung bleibt deshalb fachlich eingeschraenkt",
        ]
        status = "UEBERPRUEFEN"
        summary = (
            "Im Zeitraum gab es keine echten manuellen Echtgeld-Ausfuehrungen. "
            "Deshalb ist nur eine eingeschraenkte Leistungsbewertung moeglich. "
            "Technik und Prozess koennen dennoch sinnvoll bewertet werden."
        )
    elif not realized_complete:
        reasons = [
            "Mindestens ein echter Exit ist fachlich nicht voll erfasst",
            "Die reale Kosten- und Performancebewertung bleibt deshalb eingeschraenkt",
        ]
        status = "UEBERPRUEFEN"
        summary = (
            "Es liegen echte Ausfuehrungen vor, aber mindestens ein Exit ist nicht voll erfasst. "
            "Deshalb bleibt die Monatsbewertung bewusst defensiv und nicht voll belastbar."
        )
    elif api_stress:
        reasons = ["API-Druck war zu hoch", "Der Betrieb sollte vor einer Ausweitung stabilisiert werden"]
        if blocked > 0:
            reasons.append("Es gab blockierte oder budgetkritische Laufphasen")
        elif degraded > 0:
            reasons.append("Der Desk musste im Monatsverlauf gedrosselt werden")
        elif max_calls_in_minute > minute_limit_hard:
            reasons.append("Die Minutenlast lag ueber dem vorgesehenen Budget")
        status = "GEDROSSELT_FUEHREN"
        summary = (
            "Der API-Druck war im Zeitraum zu hoch. "
            "Der Desk sollte vor einer Ausweitung erst stabilisiert oder gedrosselt weitergefuehrt werden."
        )
    elif weak_real_performance:
        reasons = ["Echte Ausfuehrungen waren im Zeitraum zu schwach", "Die reale Performance rechtfertigt aktuell keinen offensiveren Betrieb"]
        if win_rate is not None and float(win_rate) < 40.0:
            reasons.append("Die Trefferquote geschlossener Trades war schwach")
        status = "GEDROSSELT_FUEHREN"
        summary = (
            "Es liegen echte Ausfuehrungen vor, aber die Real-Performance war zu schwach. "
            "Der Desk sollte im naechsten Monat vorsichtiger und enger gefuehrt werden."
        )
    elif cost_coverage_status == "KOSTEN_GEDECKT" and realized and realized > 0 and (win_rate is None or float(win_rate) >= 50.0) and blocked == 0 and degraded <= 2 and actionable >= 5:
        reasons = ["Positive realisierte Performance", "Aktive, aber kontrollierte Nutzung", "API-Budget blieb stabil"]
        status = "AUSBAUEN"
        summary = "Der Desk liefert tragfaehige Signale bei kontrolliertem Betrieb und kann vorsichtig ausgebaut werden."
    elif realized_after_cost is not None and realized_after_cost >= 0 and blocked == 0:
        reasons = ["Aktivitaet und Kosten stehen im vernuenftigen Verhaeltnis", "Keine kritische API-Belastung"]
        status = "WEITER_FUEHREN"
        summary = "Der Desk arbeitet stabil genug und kann im naechsten Monat normal weitergefuehrt werden."
    else:
        reasons = ["Aussagekraft des Monats ist begrenzt", "Signal- oder Kostenbild ist noch nicht stabil genug"]
        status = "UEBERPRUEFEN"
        summary = "Der Nutzen ist aktuell noch nicht klar genug. Der Desk sollte im naechsten Monat bewusst ueberprueft werden."

    return {"organism_status": status, "reasons": reasons, "summary": summary}


def build_monthly_evaluation(cfg, period: str | None = None) -> dict:
    period_key, start, end = _period_bounds(period)
    activity = _activity_metrics(cfg, start, end)
    performance, positions = _performance_metrics(cfg, start, end)
    risk = _risk_metrics(cfg, positions)
    api = _api_metrics(cfg, start, end)
    cost_status = build_cost_status(cfg, period_key)
    economics = _economics_metrics(performance, cost_status)
    report = {
        "period": period_key,
        "generated_at": now_iso_tz(cfg.get("app", {}).get("timezone", "Europe/Berlin")),
        "activity": activity,
        "performance": performance,
        "risk": risk,
        "api": api,
        "economics": economics,
        "cost_status": cost_status,
    }
    report["evaluation"] = evaluate_organism(report, cfg)
    return report
