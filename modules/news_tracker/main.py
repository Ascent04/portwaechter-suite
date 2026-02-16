from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from modules.common.config import load_config
from modules.common.utils import append_jsonl, ensure_dir
from modules.news_tracker.entities import build_entities
from modules.news_tracker.feeds import pull_feeds
from modules.news_tracker.notifier import send_top_opportunities
from modules.news_tracker.ranker import rank_opportunities
from modules.news_tracker.translate import translate_stub


DEFAULT_FEEDS = [
    {"name": "IR", "url": "https://www.eqs-news.com/feed/"},
    {"name": "Regulatory", "url": "https://www.sec.gov/rss/news/press.xml"},
    {"name": "MarketWatch", "url": "https://feeds.content.dowjones.io/public/rss/mw_topstories"},
]


def _latest_snapshot(root_dir: Path) -> Path:
    snapshots = sorted((root_dir / "data" / "snapshots").glob("portfolio_*.json"))
    if not snapshots:
        raise FileNotFoundError("No snapshot found under data/snapshots")
    return snapshots[-1]


def run() -> None:
    cfg = load_config()
    root_dir = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    news_dir = root_dir / "data" / "news"
    ensure_dir(news_dir)

    latest_snapshot = _latest_snapshot(root_dir)
    entities_path = news_dir / "entities.json"
    entities = build_entities(latest_snapshot, entities_path)

    feed_sources = cfg.get("news", {}).get("feed_sources", DEFAULT_FEEDS)
    pulled = pull_feeds(feed_sources, entities, news_dir)

    date_tag = datetime.now().strftime("%Y%m%d")
    translated_path = news_dir / f"items_translated_{date_tag}.jsonl"
    if translated_path.exists():
        translated_path.unlink()
    translated_path.write_text("", encoding="utf-8")

    for item in pulled.get("items", []):
        translated = translate_stub(item)
        append_jsonl(translated_path, translated)

    ranking_path = news_dir / f"top_opportunities_{date_tag}.json"
    ranking = rank_opportunities(translated_path, ranking_path)
    send_top_opportunities(ranking.get("top", []), cfg)


def _cli() -> None:
    parser = argparse.ArgumentParser(description="News tracker runner")
    parser.add_argument("command", choices=["run"])
    args = parser.parse_args()

    if args.command == "run":
        run()


if __name__ == "__main__":
    _cli()
