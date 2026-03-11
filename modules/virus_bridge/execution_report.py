from __future__ import annotations

from pathlib import Path

from modules.common.operator_warnings import warning_lines
from modules.common.runtime_dirs import ensure_runtime_directories
from modules.common.utils import ensure_dir, now_iso_tz, write_json
from modules.v2.telegram.copy import candidate_name
from modules.virus_bridge.cost_status import build_cost_status
from modules.virus_bridge.execution_performance import _build_all_positions, compute_execution_summary


def _root_dir(cfg: dict) -> Path:
    return Path(cfg.get("app", {}).get("root_dir", Path.cwd()))


def _report_path(cfg: dict) -> Path:
    stamp = now_iso_tz(cfg.get("app", {}).get("timezone", "Europe/Berlin"))[:16]
    stamp = stamp.replace("-", "").replace(":", "").replace("T", "_")
    return _root_dir(cfg) / "data" / "virus_bridge" / "performance" / f"execution_report_{stamp}.json"


def _safe_float(value: object) -> float | None:
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


def _fmt_money(value: object) -> str:
    amount = _safe_float(value)
    if amount is None:
        return "nicht belastbar verfuegbar"
    sign = "+" if amount > 0 else ""
    text = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{sign}{text} EUR"


def _fmt_amount(value: object) -> str:
    amount = _safe_float(value)
    if amount is None:
        return "nicht belastbar verfuegbar"
    absolute = abs(amount)
    text = f"{absolute:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{text} EUR"


def _fmt_pct(value: object) -> str:
    amount = _safe_float(value)
    if amount is None:
        return "nicht belastbar verfuegbar"
    return f"{amount:.1f}".replace(".", ",") + " %"


def _fmt_price(value: object) -> str:
    amount = _safe_float(value)
    if amount is None:
        return "nicht belastbar verfuegbar"
    return f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_qty(value: object) -> str:
    amount = _safe_float(value)
    if amount is None:
        return "nicht belastbar verfuegbar"
    return f"{amount:.4f}".rstrip("0").rstrip(".") or "0"


def _cost_reference_lines(reference: dict) -> list[str]:
    if not isinstance(reference, dict):
        return ["nicht belastbar verfuegbar"]
    lines = [str(reference.get("label") or "nicht belastbar verfuegbar")]
    eur_estimate = _safe_float(reference.get("eur_estimate"))
    if eur_estimate is not None:
        lines.append(f"Interne EUR-Referenz: {_fmt_amount(eur_estimate)}")
    return lines


def _warning_lines(report: dict) -> list[str]:
    source = report.get("source_details") or {}
    summary = report.get("summary") or {}
    warnings: list[tuple[str, str]] = []
    if not int(source.get("executions_count") or 0):
        warnings.append(("NOCH_NICHT_BEWERTBAR", "Es liegen noch keine echten Ausfuehrungen vor"))
    if summary.get("realized_pnl_complete") is False:
        warnings.append(("UNVOLLSTAENDIG", "Mindestens ein Exit ist nicht voll erfasst"))
    if int(summary.get("unpriced_open_total") or 0) > 0:
        warnings.append(("VERALTET", "Fehlende belastbare Quotes fuer offene PnL"))
    cost_status = str(report.get("cost_coverage_status") or "").upper()
    if cost_status == "NICHT_GEDECKT":
        warnings.append(("KOSTEN_NICHT_GEDECKT", "Die laufende Kostenhuerde ist nicht gedeckt"))
    elif cost_status == "NAHE_BREAK_EVEN":
        warnings.append(("NOCH_NICHT_BEWERTBAR", "Die Kostenhuerde ist noch nicht sauber gedeckt"))
    elif cost_status == "NOCH_NICHT_BEWERTBAR" and int(source.get("executions_count") or 0):
        warnings.append(("NOCH_NICHT_BEWERTBAR", "Wirtschaftliche Wirkung noch nicht belastbar"))
    return warning_lines(warnings)


def _quantity(size_eur: object, price: object) -> float | None:
    notional = _safe_float(size_eur)
    entry = _safe_float(price)
    if notional in {None, 0} or entry in {None, 0}:
        return None
    return round(notional / entry, 6)


def _source_details(cfg: dict) -> dict:
    root = _root_dir(cfg) / "data" / "virus_bridge"
    return {
        "executions_count": len(list((root / "executions").rglob("execution_*.json"))) if (root / "executions").exists() else 0,
        "exit_records_count": len(list((root / "exits").rglob("exit_*.json"))) if (root / "exits").exists() else 0,
        "lifecycle_count": len(list((root / "ticket_lifecycle").glob("*.json"))) if (root / "ticket_lifecycle").exists() else 0,
        "ticket_state_present": (root / "ticket_state.json").exists(),
    }


def _open_position(row: dict) -> dict:
    asset = row.get("asset") or {}
    return {
        "ticket_id": row.get("ticket_id"),
        "symbol": asset.get("symbol") or asset.get("isin"),
        "display_name": candidate_name(asset),
        "entry_quantity": _safe_float(row.get("entry_quantity")),
        "exited_quantity_total": _safe_float(row.get("exited_quantity_total")),
        "remaining_quantity": _quantity(row.get("remaining_size_eur"), row.get("entry_price")),
        "remaining_size_eur": _safe_float(row.get("remaining_size_eur")),
        "average_entry_price": _safe_float(row.get("entry_price")),
        "average_exit_price_weighted": _safe_float(row.get("average_exit_price_weighted")),
        "market_price": _safe_float(row.get("current_price")),
        "realized_pnl_eur": _safe_float(row.get("realized_pnl_eur")),
        "unrealized_pnl_eur": _safe_float(row.get("unrealized_pnl_eur")),
        "status": row.get("status"),
        "lifecycle_status": row.get("lifecycle_status"),
        "has_partial_exits": bool(row.get("has_partial_exits", False)),
        "partial_exit_count": int(row.get("partial_exit_count") or 0),
        "exit_reason": row.get("exit_reason"),
        "exit_reason_quality": row.get("exit_reason_quality"),
        "source": "TELEGRAM_MANUAL",
        "last_updated_at": row.get("latest_exit_timestamp") or row.get("entry_timestamp"),
        "price_status": row.get("price_status"),
        "current_price": _safe_float(row.get("current_price")),
    }


def _closed_trade(row: dict) -> dict:
    asset = row.get("asset") or {}
    return {
        "ticket_id": row.get("ticket_id"),
        "symbol": asset.get("symbol") or asset.get("isin"),
        "display_name": candidate_name(asset),
        "entry_quantity": _safe_float(row.get("entry_quantity")),
        "exited_quantity": _safe_float(row.get("exited_quantity_total")),
        "exited_quantity_total": _safe_float(row.get("exited_quantity_total")),
        "remaining_quantity": _safe_float(row.get("remaining_quantity")),
        "average_entry_price": _safe_float(row.get("entry_price")),
        "average_exit_price": _safe_float(row.get("average_exit_price_weighted") or row.get("latest_exit_price") or row.get("current_price")),
        "average_exit_price_weighted": _safe_float(row.get("average_exit_price_weighted")),
        "realized_pnl_eur": _safe_float(row.get("realized_pnl_eur")),
        "unrealized_pnl_eur": _safe_float(row.get("unrealized_pnl_eur")),
        "exit_reason": row.get("exit_reason") or row.get("status"),
        "exit_reason_quality": row.get("exit_reason_quality"),
        "closed_at": row.get("closed_at") or row.get("latest_exit_timestamp"),
        "realized_pnl_pct": _safe_float(row.get("realized_pnl_pct")),
        "lifecycle_status": row.get("lifecycle_status"),
        "has_partial_exits": bool(row.get("has_partial_exits", False)),
        "weighted_exit_method": bool(row.get("weighted_exit_method", False)),
    }


def _open_position_line(row: dict) -> str:
    parts = [str(row.get("display_name") or row.get("symbol") or row.get("ticket_id") or "-"), str(row.get("status") or "-")]
    remaining = row.get("remaining_size_eur")
    if remaining is not None:
        parts.append(f"Rest {_fmt_amount(remaining)}")
    if row.get("realized_pnl_eur") is not None and str(row.get("status") or "").upper() == "PARTIALLY_CLOSED":
        parts.append(f"Realisiert {_fmt_money(row.get('realized_pnl_eur'))}")
    if row.get("unrealized_pnl_eur") is not None:
        parts.append(f"Offen {_fmt_money(row.get('unrealized_pnl_eur'))}")
    return "- " + " | ".join(parts)


def _closed_trade_line(row: dict) -> str:
    parts = [str(row.get("display_name") or row.get("symbol") or row.get("ticket_id") or "-")]
    reason = str(row.get("exit_reason") or "-").strip()
    parts.append(f"Grund {reason}")
    if row.get("average_exit_price_weighted") is not None:
        parts.append(f"Exit {_fmt_price(row.get('average_exit_price_weighted'))}")
    parts.append(f"Realisiert {_fmt_money(row.get('realized_pnl_eur'))}")
    quality = str(row.get("exit_reason_quality") or "").strip()
    if quality:
        parts.append(f"Reason {quality}")
    return "- " + " | ".join(parts)


def build_execution_report(cfg) -> dict:
    ensure_runtime_directories(cfg)
    positions = _build_all_positions(cfg)
    summary = compute_execution_summary(positions, cfg)
    cost_status = build_cost_status(cfg)
    open_positions = [_open_position(row) for row in positions if row.get("status") in {"OPEN", "PARTIALLY_CLOSED"}]
    closed_trades = [_closed_trade(row) for row in positions if row.get("status") == "CLOSED"]
    notes = ["Auswertung basiert auf manuell erfassten Ausfuehrungen und Lifecycle-Daten."]
    if not summary.get("realized_pnl_complete", True):
        notes.append("Mindestens ein Exit ist unvollstaendig erfasst. Realisierte PnL und Exit-Durchschnitte sind deshalb nicht voll belastbar.")
    if summary.get("weighted_exit_method") is False:
        notes.append("Mindestens ein geschlossener Trade konnte nicht mit einem voll gewichteten Exit-Durchschnitt rekonstruiert werden.")
    if summary.get("unpriced_open_total", 0):
        if summary.get("priced_open_total", 0):
            notes.append("Offene Bewertungen sind nur teilweise enthalten, weil nicht fuer alle offenen Positionen ein belastbarer Marktpreis vorliegt.")
        else:
            notes.append("Offene Bewertungen sind derzeit nicht enthalten, weil kein belastbarer Marktpreis vorliegt.")
    elif open_positions:
        notes.append("Offene Bewertungen sind nur enthalten, wenn ein belastbarer Marktpreis vorliegt.")
    created_at = now_iso_tz(cfg.get("app", {}).get("timezone", "Europe/Berlin"))
    return {
        "evaluation_id": "EXEC-" + created_at[:19].replace("-", "").replace(":", "").replace("T", "-"),
        "created_at": created_at,
        "generated_at": created_at,
        "source_details": _source_details(cfg),
        "open_positions_count": summary["open_positions_count"],
        "closed_positions_count": summary["closed_positions_count"],
        "partial_exit_count": summary["partial_exit_count"],
        "realized_pnl_eur": summary["realized_pnl_eur_total"],
        "unrealized_pnl_eur": summary["unrealized_pnl_eur_total"],
        "total_pnl_eur": summary["total_pnl_eur"],
        "win_rate": summary["win_rate_closed"],
        "average_win_eur": summary["average_win_eur"],
        "average_loss_eur": summary["average_loss_eur"],
        "notes": notes,
        "open_positions": open_positions,
        "closed_trades": closed_trades,
        "summary": summary,
        "positions": positions,
        "cost_status": cost_status,
        "realized_pnl_before_costs": cost_status["realized_pnl_before_costs"],
        "operating_cost_reference": cost_status["operating_cost_reference"],
        "realized_pnl_after_costs": cost_status["realized_pnl_after_costs"],
        "cost_coverage_status": cost_status["cost_coverage_status"],
    }


def write_execution_report(report: dict, cfg: dict) -> str:
    path = _report_path(cfg)
    ensure_dir(path.parent)
    write_json(path, report)
    return str(path)


def render_execution_summary(cfg: dict) -> str:
    report = build_execution_report(cfg)
    warnings = _warning_lines(report)
    lines = [
        "CB Fund Desk - Ausfuehrungsstand",
        "",
        "Stand:",
        str(report["created_at"])[0:16].replace("T", " "),
        "",
        "Echte Ausfuehrungen:",
        str(int((report.get("summary") or {}).get("executed_total", 0) or 0)),
    ]
    if not report["source_details"]["executions_count"]:
        lines.extend(["", "Hinweis:", "Es liegen noch keine manuell erfassten Ausfuehrungen vor."])
    else:
        lines.extend(
            [
                "",
                "Offene Positionen:",
                str(int(report["open_positions_count"] or 0)),
                "",
                "Geschlossene Trades:",
                str(int(report["closed_positions_count"] or 0)),
                "",
                "Teilverkaeufe:",
                str(int(report["partial_exit_count"] or 0)),
                "",
                "Realisierte PnL:",
                _fmt_money(report.get("realized_pnl_eur")),
                "",
                "Unrealisierte PnL:",
                _fmt_money(report.get("unrealized_pnl_eur")),
                "",
                "Gesamt-PnL:",
                _fmt_money(report.get("total_pnl_eur")),
                "",
                "Trefferquote:",
                _fmt_pct(report.get("win_rate")),
            ]
        )
        if report.get("average_win_eur") is not None:
            lines.extend(["", "Durchschnitt Gewinn:", _fmt_money(report.get("average_win_eur"))])
        if report.get("average_loss_eur") is not None:
            lines.extend(["", "Durchschnitt Verlust:", _fmt_money(report.get("average_loss_eur"))])
        lines.extend(["", "Hinweis:", " ".join(str(note) for note in report.get("notes", []))])
        open_lines = [_open_position_line(row) for row in report.get("open_positions", [])[:3]]
        if open_lines:
            lines.extend(["", "Aktive Positionen:"] + open_lines)
        closed_lines = [_closed_trade_line(row) for row in report.get("closed_trades", [])[:3]]
        if closed_lines:
            lines.extend(["", "Zuletzt geschlossen:"] + closed_lines)
    if warnings:
        lines.extend(["", "Warnlage:"] + [f"- {item}" for item in warnings])
    lines.extend(
        [
            "",
            "KOSTENSTATUS:",
            str(report.get("cost_coverage_status") or "NOCH_NICHT_BEWERTBAR"),
            "",
            "Realisierte Performance vor Kosten:",
            _fmt_money(report.get("realized_pnl_before_costs")),
            "",
            "Fixkosten-Referenz:",
        ]
    )
    lines.extend(_cost_reference_lines(report.get("operating_cost_reference") or {}))
    lines.extend(
        [
            "",
            "Realisierte Performance nach Kosten:",
            _fmt_money(report.get("realized_pnl_after_costs")),
            "",
            "Bewertung:",
            str((report.get("cost_status") or {}).get("explanation") or "Noch nicht bewertbar."),
        ]
    )
    return "\n".join(lines)[:1800]
