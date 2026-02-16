from __future__ import annotations

import argparse
from pathlib import Path

from modules.common.config import load_config
from modules.marketdata_watcher.adapter_http import run_quotes
from modules.marketdata_watcher.notifier import send_market_alerts
from modules.marketdata_watcher.signals import detect_intraday_moves
from modules.marketdata_watcher.watchlist import build_watchlist


def _latest_snapshot(root_dir: Path) -> Path:
    snapshots = sorted((root_dir / "data" / "snapshots").glob("portfolio_*.json"))
    if not snapshots:
        raise FileNotFoundError("No snapshot found under data/snapshots")
    return snapshots[-1]


def run() -> None:
    cfg = load_config()
    root_dir = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))

    latest_snapshot = _latest_snapshot(root_dir)
    watchlist_path = root_dir / "data" / "marketdata" / "watchlist.json"
    quotes_dir = root_dir / "data" / "marketdata"
    alerts_path = root_dir / "data" / "marketdata" / "alerts.jsonl"

    build_watchlist(latest_snapshot, watchlist_path)

    mapping_path = cfg.get("marketdata", {}).get(
        "isin_to_symbol",
        str(root_dir / "config" / "isin_to_symbol.json"),
    )
    quote_result = run_quotes(watchlist_path, mapping_path, quotes_dir)

    cooldown = int(cfg.get("marketdata", {}).get("cooldown_min", 60))
    alerts = detect_intraday_moves(quote_result["quotes_path"], alerts_path, cooldown)
    send_market_alerts(alerts, cfg)


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Marketdata watcher runner")
    parser.add_argument("command", choices=["run"])
    args = parser.parse_args()

    if args.command == "run":
        run()


if __name__ == "__main__":
    _cli()
