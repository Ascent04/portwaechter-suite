from __future__ import annotations

from pathlib import Path

from modules.common.operator_warnings import warning_lines
from modules.common.runtime_dirs import ensure_runtime_directories
from modules.common.utils import ensure_dir, now_iso_tz, read_json, write_json
from modules.organism.monthly_evaluation import build_monthly_evaluation
from modules.v2.telegram.copy import display_name


def _root_dir(cfg: dict) -> Path:
    return Path(cfg.get("app", {}).get("root_dir", Path.cwd()))


def _report_path(period: str, cfg: dict) -> Path:
    stamp = str(period or now_iso_tz(cfg.get("app", {}).get("timezone", "Europe/Berlin"))[:7]).replace("-", "_")
    return _root_dir(cfg) / "data" / "organism" / "monthly" / f"monthly_evaluation_{stamp}.json"


def _fmt_money(value: object) -> str:
    try:
        return f"{float(value):.2f}".replace(".", ",")
    except (TypeError, ValueError):
        return "nicht belastbar"


def _money_label(value: object) -> str:
    text = _fmt_money(value)
    return f"{text} EUR" if text != "nicht belastbar" else text


def _fmt_pct(value: object) -> str:
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "-"


def _warning_lines(report: dict, no_real_data: bool) -> list[str]:
    api = report.get("api", {})
    economics = report.get("economics", {})
    warnings: list[tuple[str, str]] = []
    if no_real_data:
        warnings.append(("NOCH_NICHT_BEWERTBAR", "Es liegen noch keine echten Ausfuehrungen vor"))
    elif economics.get("realized_pnl_complete") is False:
        warnings.append(("UNVOLLSTAENDIG", "Mindestens ein echter Exit ist nicht voll erfasst"))
    cost_status = str(economics.get("cost_coverage_status") or "").upper()
    if cost_status == "NICHT_GEDECKT":
        warnings.append(("KOSTEN_NICHT_GEDECKT", "Die laufende Kostenhuerde ist nicht gedeckt"))
    elif cost_status == "NOCH_NICHT_BEWERTBAR" and not no_real_data:
        warnings.append(("NOCH_NICHT_BEWERTBAR", "Die wirtschaftliche Wirkung ist noch nicht belastbar"))
    if int(api.get("degraded_runs_total", 0) or 0) > 0:
        warnings.append(("API_DRUCK", "Der Betrieb wurde im Zeitraum mindestens einmal gedrosselt"))
    return warning_lines(warnings)


def write_monthly_evaluation(report: dict, cfg: dict) -> str:
    path = _report_path(str(report.get("period") or ""), cfg)
    ensure_dir(path.parent)
    write_json(path, report)
    return str(path)


def load_monthly_evaluation(cfg: dict, period: str | None = None) -> dict | None:
    if period:
        path = _report_path(period, cfg)
        if not path.exists():
            return None
        data = read_json(path)
        return data if isinstance(data, dict) else None
    monthly_dir = _root_dir(cfg) / "data" / "organism" / "monthly"
    files = sorted(monthly_dir.glob("monthly_evaluation_*.json"))
    if not files:
        return None
    data = read_json(files[-1])
    return data if isinstance(data, dict) else None


def build_and_write_monthly_evaluation(cfg: dict, period: str | None = None) -> dict:
    ensure_runtime_directories(cfg)
    report = build_monthly_evaluation(cfg, period)
    return {"path": write_monthly_evaluation(report, cfg), "report": report}


def render_organism_text(cfg: dict, period: str | None = None) -> str:
    report = build_and_write_monthly_evaluation(cfg, period)["report"]
    activity = report.get("activity", {})
    performance = report.get("performance", {})
    api = report.get("api", {})
    economics = report.get("economics", {})
    evaluation = report.get("evaluation", {})
    buy_total = int(activity.get("kaufen_pruefen_total", 0) or 0)
    sell_total = int(activity.get("verkaufen_pruefen_total", 0) or 0)
    executed_total = int(economics.get("executed_entries_count") or activity.get("executed_total", 0) or 0)
    closed_total = int(activity.get("closed_total", 0) or 0)
    realized_exit_count = int(economics.get("realized_exit_count", 0) or 0)
    best = performance.get("best_trade") if isinstance(performance.get("best_trade"), dict) else None
    worst = performance.get("worst_trade") if isinstance(performance.get("worst_trade"), dict) else None
    no_real_data = executed_total == 0
    warnings = _warning_lines(report, no_real_data)

    lines = [
        f"{display_name(cfg)} - Monatsbewertung",
        "",
        f"Monat: {report.get('period')}",
        "",
        "Aktivitaet:",
        f"- Kaufideen: {buy_total}",
        f"- Verkaufssignale: {sell_total}",
        f"- Echte Ausfuehrungen: {executed_total}",
        f"- Geschlossen: {closed_total}",
        f"- Bewertbare Exits: {realized_exit_count}",
        "",
        "Performance:",
        f"- Realisiert: {_money_label(performance.get('realized_pnl_eur_total'))}",
        f"- Offen: {_money_label(performance.get('unrealized_pnl_eur_total'))}",
        f"- Trefferquote: {_fmt_pct(performance.get('win_rate_closed'))} %",
        "",
        "Betrieb:",
        f"- API-Calls: {int(float(api.get('api_calls_total', 0) or 0))}",
        f"- Gedrosselte Laeufe: {int(api.get('degraded_runs_total', 0) or 0)}",
        "",
        "Kosten:",
        f"- Monatlich: {_money_label(economics.get('monthly_cost_eur_estimate'))}",
        f"- Vor Kosten: {_money_label(economics.get('realized_pnl_before_costs'))}",
        f"- Ergebnis nach Kosten: {_money_label(economics.get('realized_pnl_minus_cost_eur'))}",
        f"- Kostenstatus: {economics.get('cost_coverage_status') or 'NOCH_NICHT_BEWERTBAR'}",
        "",
        "Bewertung:",
        str(evaluation.get("organism_status") or "UEBERPRUEFEN"),
        "",
        "Kurzfazit:",
        str(evaluation.get("summary") or "Noch keine klare Monatsbewertung verfuegbar."),
    ]
    if best or worst:
        lines.extend(
            [
                "",
                "Spanne:",
                f"- Beste Position: {best.get('name')} {_fmt_pct(best.get('pnl_pct'))} %" if best else "- Beste Position: -",
                f"- Schwaechste Position: {worst.get('name')} {_fmt_pct(worst.get('pnl_pct'))} %" if worst else "- Schwaechste Position: -",
            ]
        )
    if warnings:
        lines.extend(["", "Warnlage:"] + [f"- {item}" for item in warnings])
    return "\n".join(lines)[:1800]
