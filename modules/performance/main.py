from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta
from pathlib import Path

from modules.common.config import load_config
from modules.common.utils import now_iso_tz
from modules.performance.collect_events import load_events
from modules.performance.forward_returns import compute_forward_returns_for_event
from modules.performance.log_events import append_event, build_signal_event
from modules.performance.outcomes import append_outcome, dedupe_outcomes
from modules.performance.report_weekly import build_weekly_report, write_weekly_report
from modules.performance.telegram_reporting import send_if_relevant


def _ensure_dirs(cfg: dict) -> Path:
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    base = root / "data" / "performance"
    (base / "reports").mkdir(parents=True, exist_ok=True)
    return base


def _latest(path: Path, pattern: str) -> Path | None:
    files = sorted(path.glob(pattern))
    return files[-1] if files else None


def _read_jsonl(path: Path) -> list[dict]:
    if not path or not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _quotes_index(cfg: dict, lookback_days: int) -> dict:
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    market = root / "data" / "marketdata"
    files = sorted(market.glob("quotes_*.jsonl"))[-max(lookback_days, 5) :]

    temp: dict[tuple[str, str], dict] = {}
    for file in files:
        for row in _read_jsonl(file):
            if row.get("status") != "ok" or row.get("close") is None:
                continue
            key = (str(row.get("isin")), str(row.get("date")))
            prev = temp.get(key)
            t = str(row.get("time") or row.get("fetched_at") or "")
            if not prev or t >= str(prev.get("time") or prev.get("fetched_at") or ""):
                temp[key] = {"date": row.get("date"), "close": row.get("close"), "time": row.get("time")}

    idx: dict[str, list[dict]] = {}
    for (isin, _), row in temp.items():
        idx.setdefault(isin, []).append({"date": row.get("date"), "close": row.get("close")})
    for isin in idx:
        idx[isin].sort(key=lambda x: str(x.get("date")))
    return idx


def _event_id(event: dict) -> str:
    return str(event.get("signal_id") or event.get("setup_id") or "")


def log_latest(cfg: dict) -> int:
    _ensure_dirs(cfg)
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    latest_signals = _latest(root / "data" / "signals", "signals_*.jsonl")
    if not latest_signals:
        print("no signals files found")
        return 0

    count = 0
    for s in _read_jsonl(latest_signals):
        if s.get("id") != "MULTI_FACTOR_SIGNAL":
            continue
        append_event(build_signal_event(s, cfg), cfg)
        count += 1
    if count == 0:
        print("no multi-factor signals found")
    else:
        print(f"logged_events={count}")
    return count


def eval_events(cfg: dict, days: int) -> int:
    _ensure_dirs(cfg)
    today = date.today()
    events = load_events(today - timedelta(days=days), today, cfg)
    if not events:
        print("no events")
        return 0

    quotes = _quotes_index(cfg, days + 10)
    horizons = cfg.get("performance", {}).get("horizons_days", [1, 3, 5])
    tz = cfg.get("app", {}).get("timezone", "Europe/Berlin")
    eval_ts = now_iso_tz(tz)
    eval_day = eval_ts[:10]

    wrote = 0
    for event in events:
        event_id = _event_id(event)
        if not event_id or dedupe_outcomes(event_id, eval_day, cfg):
            continue
        outcome = {
            "ts_eval": eval_ts,
            "event_type": event.get("event_type"),
            "signal_id": event.get("signal_id"),
            "setup_id": event.get("setup_id"),
            "isin": event.get("isin"),
            "direction": event.get("direction", "up"),
            "factor_score": event.get("factor_score"),
            "confidence": event.get("confidence"),
            "regime": event.get("regime"),
            "volume_light": event.get("volume_light"),
            "horizons": compute_forward_returns_for_event(event, quotes, horizons=[int(h) for h in horizons]),
            "meta": {"price_source": "marketdata_quotes", "notes": []},
        }
        append_outcome(outcome, cfg)
        wrote += 1
    if wrote == 0:
        print("no new outcomes")
    else:
        print(f"outcomes_written={wrote}")
    return wrote


def report_weekly(cfg: dict) -> Path:
    perf_dir = _ensure_dirs(cfg)
    outcomes = []
    for p in sorted(perf_dir.glob("outcomes_*.jsonl"))[-30:]:
        outcomes.extend(_read_jsonl(p))
    report = build_weekly_report(outcomes, cfg)
    path = write_weekly_report(report, cfg)
    send_if_relevant(report, cfg)
    print(f"weekly_report={path}")
    return path


def run() -> None:
    cfg = load_config()
    if not cfg.get("performance", {}).get("enabled", True):
        return

    _ensure_dirs(cfg)
    lookback = int(cfg.get("performance", {}).get("eval_lookback_days", 30))
    eval_events(cfg, lookback)

    day_name = str(cfg.get("performance", {}).get("weekly_report_day", "Sun")).lower()
    today_name = datetime.now().strftime("%a").lower()
    if today_name.startswith(day_name[:3]):
        report_weekly(cfg)


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Performance engine")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run")
    sub.add_parser("log-latest")
    eval_p = sub.add_parser("eval")
    eval_p.add_argument("--days", type=int, default=14)
    sub.add_parser("report-weekly")

    args = parser.parse_args()
    cfg = load_config()

    if args.cmd == "run":
        run()
    elif args.cmd == "log-latest":
        log_latest(cfg)
    elif args.cmd == "eval":
        eval_events(cfg, int(args.days))
    elif args.cmd == "report-weekly":
        report_weekly(cfg)


if __name__ == "__main__":
    _cli()
