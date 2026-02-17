from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from modules.common.utils import ensure_dir, write_json

log = logging.getLogger(__name__)


def _mode1() -> None:
    from modules.marketdata_watcher.main import run as run_marketdata
    from modules.news_tracker.main import run as run_news
    from modules.portfolio_ingest.main import run as run_portfolio

    run_portfolio()
    run_marketdata()
    run_news()


def _mode2(cfg: dict) -> None:
    from modules.decision_engine.engine import run as run_decision
    from modules.setup_engine.run import run as run_setups
    from modules.signals_engine.notifier import send_signals
    from modules.signals_engine.orchestrator import run as run_signals
    from modules.watch_alerts.engine import run as run_watch_alerts

    _mode1()
    signals = run_signals(cfg)
    send_signals(signals, cfg)
    run_decision(cfg)
    run_setups(cfg)
    run_watch_alerts(cfg)


def _mode3(cfg: dict) -> None:
    from modules.optimizer_engine.orchestrator import run as run_optimizer

    _mode1()
    run_optimizer(cfg)


def _mode4(cfg: dict) -> None:
    try:
        from modules.radar.crawler import pull_radar_feeds
        from modules.radar.notifier import send_radar_top
        from modules.radar.ranker import rank_radar
        from modules.radar.universe import build_universe
    except ModuleNotFoundError as exc:
        log.warning("mode4 skipped: missing dependency: %s", exc.name)
        return

    if not cfg.get("radar", {}).get("enabled", True):
        return

    root_dir = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    radar_dir = root_dir / "data" / "radar"
    ensure_dir(radar_dir)

    universe = build_universe(cfg)
    write_json(radar_dir / "universe.json", {"entities": universe})

    items_path = pull_radar_feeds(cfg, radar_dir)
    ranked = rank_radar(items_path)

    date_tag = datetime.now().strftime("%Y%m%d")
    ranking_path = radar_dir / f"top_radar_{date_tag}.json"
    write_json(ranking_path, ranked)
    send_radar_top(ranked.get("top", []), cfg)


def run_mode(cfg: dict) -> None:
    mode = int(cfg.get("app", {}).get("mode", 1))

    if mode == 1:
        _mode1()
        return
    if mode == 2:
        _mode2(cfg)
        return
    if mode == 3:
        _mode3(cfg)
        return
    if mode == 4:
        _mode4(cfg)
        return

    raise ValueError(f"Unsupported app.mode: {mode}")
