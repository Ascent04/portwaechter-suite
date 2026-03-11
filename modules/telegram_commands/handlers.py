from __future__ import annotations

from datetime import datetime
from pathlib import Path

from modules.common.config import load_config
from modules.common.operator_warnings import warning_lines
from modules.common.utils import read_json
from modules.config.runtime import get_current_profile, set_market_thresholds, set_profile
from modules.health.report import collect_health_report
from modules.portfolio_status.status import render_portfolio_status
from modules.v2.marketdata.api_governor import status_snapshot
from modules.v2.telegram.copy import display_name


def _latest(path: Path, pattern: str) -> Path | None:
    files = sorted(path.glob(pattern))
    return files[-1] if files else None


def _fmt_file_time(path: Path | None) -> str:
    if not path or not path.exists():
        return "missing"
    return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")


def _alerts_state_counts(root: Path) -> tuple[int, int]:
    state_file = root / "data" / "alerts" / "state.json"
    if not state_file.exists():
        return 0, 0
    try:
        state = read_json(state_file)
    except Exception:
        return 0, 0
    counters = state.get("counters", {}) if isinstance(state, dict) else {}
    return int(counters.get("marketdata", 0) or 0), int(counters.get("watch", 0) or 0)


def _effective_market_thresholds(cfg: dict) -> dict:
    mcfg = cfg.get("marketdata_alerts", {})
    gd = mcfg.get("group_defaults", {}) if isinstance(mcfg.get("group_defaults"), dict) else {}
    return {
        "enabled": bool(mcfg.get("enabled", True)),
        "threshold_cross_only": bool(mcfg.get("threshold_cross_only", False)),
        "holdings": gd.get("holdings", {}),
        "radar": gd.get("radar", {}),
    }


def _friendly_status(status: object) -> str:
    mapping = {
        "ok": "OK",
        "failed": "Problem",
        "fail": "Problem",
        "missing_env": "Fehlt",
        "missing_mapping_only": "OK",
        "no_feeds": "Keine Feeds",
        "parse_fail": "Problem",
        "input_missing": "Wartet auf Input",
        "0_signals": "Keine Signale",
        "skipped_no_pdf": "Wartet auf PDF",
        "start-limit-hit": "Problem",
        "root_owned_files": "Rechteproblem",
    }
    return mapping.get(str(status or "").strip(), str(status or "Unbekannt"))


def _mapping_status_text(checks: dict) -> str:
    marketdata = str(checks.get("marketdata") or "")
    if marketdata == "missing_mapping_only":
        return "Fehlende Mappings sind aktuell toleriert."
    if marketdata == "ok":
        return "Keine fehlenden Mappings erkannt."
    return "Mapping-Status aktuell nicht eindeutig."


def _file_health(path: Path | None) -> str:
    return "OK" if path and path.exists() else "Fehlt"


def _warning_lines(checks: dict, brief_file: Path | None, weekly_file: Path | None, api_budget: dict) -> list[str]:
    warnings: list[tuple[str, str]] = []
    critical_checks = {
        "portfolio_ingest": "Portfolio-Daten nicht sauber verfuegbar",
        "marketdata": "Marktdaten nicht sauber verfuegbar",
        "news": "Nachrichtenlage nicht sauber verfuegbar",
        "signals": "Signalschicht nicht sauber verfuegbar",
        "telegram": "Telegram-Schnittstelle nicht sauber verfuegbar",
    }
    for key, label in critical_checks.items():
        if _friendly_status(checks.get(key)) != "OK":
            warnings.append(("UNVOLLSTAENDIG", label))
    if _file_health(brief_file) != "OK":
        warnings.append(("UNVOLLSTAENDIG", "Morgenbriefing fehlt"))
    if _file_health(weekly_file) != "OK":
        warnings.append(("UNVOLLSTAENDIG", "Wochenbericht fehlt"))
    mode = str(api_budget.get("mode") or "").lower()
    if mode == "blocked":
        warnings.append(("API_DRUCK", "API-Budget ist aktuell blockiert"))
    elif mode == "degraded" or api_budget.get("scanner_throttled"):
        warnings.append(("API_DRUCK", "API-Budget ist aktuell gedrosselt"))
    return warning_lines(warnings)


def status_text(cfg: dict, verbose: bool = False) -> str:
    report = collect_health_report(cfg)
    checks = report.get("checks", {})
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    brief_file = _latest(root / "data" / "briefings", "morning_*.json")
    weekly_file = _latest(root / "data" / "performance" / "reports", "weekly_*.json")
    api_budget = status_snapshot(cfg)
    warnings = _warning_lines(checks, brief_file, weekly_file, api_budget)

    lines = [
        f"{display_name(cfg)} - Status",
        "",
        "Systemlage:",
        _friendly_status(report.get("overall_status")),
        "",
        "Kernbereiche:",
        f"- Portfolio: {_friendly_status(checks.get('portfolio_ingest'))}",
        f"- Marktdaten: {_friendly_status(checks.get('marketdata'))}",
        f"- Nachrichten: {_friendly_status(checks.get('news'))}",
        f"- Signale: {_friendly_status(checks.get('signals'))}",
        f"- Telegram: {_friendly_status(checks.get('telegram'))}",
        "",
        "Dateien:",
        f"- Morgenbriefing: {_file_health(brief_file)}",
        f"- Wochenbericht: {_file_health(weekly_file)}",
        "",
        "Symbol-Mappings:",
        _mapping_status_text(checks),
    ]
    if warnings:
        lines.extend(["", "Warnlage:"] + [f"- {item}" for item in warnings])

    if verbose:
        market_file = _latest(root / "data" / "marketdata", "quotes_*.jsonl")
        news_file = _latest(root / "data" / "news", "items_*.jsonl") or _latest(root / "data" / "news", "top_opportunities_*.json")
        signals_file = _latest(root / "data" / "signals", "signals_*.jsonl")
        watch_state = root / "data" / "alerts" / "state.json"
        warn_state = root / "data" / "performance" / "warn_state.json"

        md_sent, watch_sent = _alerts_state_counts(root)
        eff = _effective_market_thresholds(cfg)
        lines.extend(
            [
                "",
                "Details:",
                f"- Letzte Marktdaten: {_fmt_file_time(market_file)}",
                f"- Letzte Nachrichten: {_fmt_file_time(news_file)}",
                f"- Letzte Signale: {_fmt_file_time(signals_file)}",
                f"- Letzte Alerts: {_fmt_file_time(watch_state)}",
                f"- Letztes Briefing: {_fmt_file_time(brief_file)}",
                f"- Marktmeldungen heute: {md_sent}",
                f"- Watchmeldungen heute: {watch_sent}",
                f"- Letzte Warnmeldung: {_fmt_file_time(warn_state)}",
                f"- Alert-Profil: {get_current_profile(cfg)}",
                "",
                "API Budget:",
                f"- Minute: {api_budget['minute_used']} / {api_budget['minute_limit_hard']}",
                f"- Modus: {api_budget['mode']}",
                f"- Scanner gedrosselt: {'ja' if api_budget['scanner_throttled'] else 'nein'}",
                "",
                "Maerkte:",
                f"- Alerts aktiv: {'ja' if eff['enabled'] else 'nein'}",
                f"- Holdings: {eff['holdings']}",
                f"- Radar: {eff['radar']}",
            ]
        )

    return "\n".join(lines)[:1900]


def alerts_show_text(cfg: dict) -> str:
    profile = get_current_profile(cfg)
    eff = _effective_market_thresholds(cfg)
    return (
        f"Alert-Profil={profile}\n"
        f"market.enabled={eff['enabled']}\n"
        f"market.threshold_cross_only={eff['threshold_cross_only']}\n"
        f"market.holdings={eff['holdings']}\n"
        f"market.radar={eff['radar']}\n"
        f"watch.enabled={cfg.get('watch_alerts', {}).get('enabled', True)}\n"
        f"watch.max_per_day={cfg.get('watch_alerts', {}).get('max_per_day')}\n"
        f"watch.min_score={cfg.get('watch_alerts', {}).get('min_score')}"
    )[:1900]


def handle_alerts_set(profile: str, cfg: dict) -> str:
    set_profile(profile, cfg)
    merged = load_config()
    return f"OK, profile set to {get_current_profile(merged)}\n{alerts_show_text(merged)}"


def handle_alerts_thresholds_market(params: list[str], cfg: dict) -> str:
    if len(params) == 1 and params[0].lower() == "off":
        set_market_thresholds(cfg, None, None, off=True)
        merged = load_config()
        return f"OK, market thresholds off\n{alerts_show_text(merged)}"

    if len(params) != 2:
        return "Usage: /alerts thresholds market <threshold_pct> <min_delta_pct> | off"

    try:
        threshold = float(params[0])
        min_delta = float(params[1])
    except ValueError:
        return "Fehler: Werte müssen Zahlen sein."

    if threshold <= 0 or min_delta <= 0:
        return "Fehler: threshold_pct und min_delta_pct müssen > 0 sein."

    set_market_thresholds(cfg, threshold, min_delta, off=False)
    merged = load_config()
    return f"OK, market thresholds gesetzt auf threshold={threshold} min_delta={min_delta}\n{alerts_show_text(merged)}"


def help_text() -> str:
    return (
        "Befehle:\n"
        "/portfolio\n"
        "/status\n"
        "/status verbose\n"
        "/organism\n"
        "/execution\n"
        "/tickets\n"
        "/alerts show\n"
        "/alerts set active|normal|quiet|off\n"
        "/alerts thresholds market <threshold_pct> <min_delta_pct>\n"
        "/alerts thresholds market off\n"
        "/testalert market|watch|performance"
    )


def portfolio_text(cfg: dict) -> str:
    return render_portfolio_status(cfg)


def testalert_text(module_name: str) -> str:
    module = module_name.lower().strip()
    if module not in {"market", "watch", "performance"}:
        return "Usage: /testalert market|watch|performance"
    return f"TESTALERT {module}: Telegram-Pipeline ok ({module})."
