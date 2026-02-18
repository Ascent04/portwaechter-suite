from __future__ import annotations

from datetime import datetime
from pathlib import Path

from modules.common.config import load_config
from modules.common.utils import read_json
from modules.config.runtime import get_current_profile, set_market_thresholds, set_profile
from modules.health.report import collect_health_report


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


def status_text(cfg: dict, verbose: bool = False) -> str:
    report = collect_health_report(cfg)
    checks = report.get("checks", {})
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))

    lines = [
        "PortWächter Status",
        f"overall={report.get('overall_status')}",
        f"portfolio={checks.get('portfolio_ingest')}",
        f"marketdata={checks.get('marketdata')}",
        f"news={checks.get('news')}",
        f"signals={checks.get('signals')}",
        f"telegram={checks.get('telegram')}",
    ]

    if verbose:
        market_file = _latest(root / "data" / "marketdata", "quotes_*.jsonl")
        news_file = _latest(root / "data" / "news", "items_*.jsonl") or _latest(root / "data" / "news", "top_opportunities_*.json")
        signals_file = _latest(root / "data" / "signals", "signals_*.jsonl")
        brief_file = _latest(root / "data" / "briefings", "morning_*.json")
        watch_state = root / "data" / "alerts" / "state.json"
        warn_state = root / "data" / "performance" / "warn_state.json"

        md_sent, watch_sent = _alerts_state_counts(root)
        eff = _effective_market_thresholds(cfg)
        lines.extend(
            [
                "",
                "/status verbose",
                f"run.marketdata={_fmt_file_time(market_file)}",
                f"run.news={_fmt_file_time(news_file)}",
                f"run.signals={_fmt_file_time(signals_file)}",
                f"run.watchalerts={_fmt_file_time(watch_state)}",
                f"run.briefing={_fmt_file_time(brief_file)}",
                f"sent.marketdata_today={md_sent}",
                f"sent.watch_today={watch_sent}",
                f"sent.perf_warn_last={_fmt_file_time(warn_state)}",
                f"profile={get_current_profile(cfg)}",
                f"market.enabled={eff['enabled']}",
                f"market.holdings={eff['holdings']}",
                f"market.radar={eff['radar']}",
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
        "/status\n"
        "/status verbose\n"
        "/alerts show\n"
        "/alerts set active|normal|quiet|off\n"
        "/alerts thresholds market <threshold_pct> <min_delta_pct>\n"
        "/alerts thresholds market off\n"
        "/testalert market|watch|performance"
    )


def testalert_text(module_name: str) -> str:
    module = module_name.lower().strip()
    if module not in {"market", "watch", "performance"}:
        return "Usage: /testalert market|watch|performance"
    return f"TESTALERT {module}: Telegram-Pipeline ok ({module})."
