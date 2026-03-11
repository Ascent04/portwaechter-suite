from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path

from modules.common.config import load_config
from modules.common.utils import now_iso_tz, read_json, write_json
from modules.config.runtime import get_current_profile
from modules.performance.notifier import send_performance_text


def _state_path(cfg: dict) -> Path:
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    raw = str(cfg.get("tactical_warnings", {}).get("state_file", "data/performance/warn_state.json"))
    p = Path(raw)
    return p if p.is_absolute() else root / p


def _load_state(cfg: dict) -> dict:
    path = _state_path(cfg)
    if not path.exists():
        return {}
    data = read_json(path)
    return data if isinstance(data, dict) else {}


def _save_state(cfg: dict, state: dict) -> None:
    write_json(_state_path(cfg), state)


def _latest_report_path(cfg: dict) -> Path | None:
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    reports = sorted((root / "data" / "performance" / "reports").glob("weekly_*.json"))
    return reports[-1] if reports else None


def load_latest_weekly_report(cfg: dict) -> dict | None:
    report_path = _latest_report_path(cfg)
    if not report_path:
        return None
    data = read_json(report_path)
    return data if isinstance(data, dict) else None


def extract_expectancy(report: dict, horizon: str) -> tuple[float | None, int]:
    row = (report.get("by_horizon") or {}).get(horizon, {})
    exp = row.get("expectancy")
    n = int(row.get("n", 0) or 0)
    try:
        value = float(exp) if exp is not None else None
    except (TypeError, ValueError):
        value = None
    return value, n


def should_warn(expectancy: float | None, n: int, cfg: dict, state: dict, report_key: str) -> bool:
    profile = get_current_profile(cfg)
    if profile == "off":
        return False

    tw = cfg.get("tactical_warnings", {})
    if expectancy is None or n < int(tw.get("min_n", 30)):
        return False
    if expectancy >= float(tw.get("warn_if_expectancy_below", 0.0)):
        return False

    today = now_iso_tz(cfg.get("app", {}).get("timezone", "Europe/Berlin"))[:10]
    if state.get("last_sent_day") == today:
        return False
    if state.get("last_report_key") == report_key:
        return False

    last_sent = state.get("last_sent_at")
    if not last_sent:
        return True
    try:
        last_dt = datetime.fromisoformat(str(last_sent))
    except ValueError:
        return True

    cooldown = timedelta(hours=int(tw.get("cooldown_hours", 24)))
    now = datetime.fromisoformat(now_iso_tz(cfg.get("app", {}).get("timezone", "Europe/Berlin")))
    return now - last_dt >= cooldown


def send_warning(cfg: dict, text: str) -> bool:
    return send_performance_text(text, cfg)


def run(cfg: dict) -> None:
    if not cfg.get("tactical_warnings", {}).get("enabled", True):
        return

    report_path = _latest_report_path(cfg)
    if not report_path:
        return
    report = load_latest_weekly_report(cfg)
    if not report:
        return

    state = _load_state(cfg)
    report_key = report_path.stem
    horizons = cfg.get("tactical_warnings", {}).get("horizons", ["3d"])

    for horizon in horizons:
        exp, n = extract_expectancy(report, str(horizon))
        if not should_warn(exp, n, cfg, state, report_key):
            continue

        profile = get_current_profile(cfg)
        msg = f"PERF WARN: {horizon} expectancy < 0 (n={n}, exp={exp:+.2f}%). profile={profile}"
        if send_warning(cfg, msg):
            now = now_iso_tz(cfg.get("app", {}).get("timezone", "Europe/Berlin"))
            state.update(
                {
                    "last_sent_at": now,
                    "last_sent_day": now[:10],
                    "last_report_key": report_key,
                    "last_horizon": str(horizon),
                    "last_n": n,
                    "last_expectancy": exp,
                }
            )
            _save_state(cfg, state)
        return


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Tactical warning sender")
    parser.add_argument("command", choices=["run"])
    args = parser.parse_args()
    if args.command == "run":
        run(load_config())


if __name__ == "__main__":
    _cli()
