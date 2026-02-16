from __future__ import annotations

from datetime import datetime
from pathlib import Path

from modules.common.utils import append_jsonl, ensure_dir
from modules.signals_engine.rules import compute_news_signals, compute_price_signals


def _latest(path: Path, pattern: str) -> Path | None:
    files = sorted(path.glob(pattern))
    return files[-1] if files else None


def run(cfg: dict) -> list[dict]:
    if not cfg.get("signals", {}).get("enabled", True):
        return []

    thresholds = cfg.get("signals", {}).get("thresholds", {})
    root_dir = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    market_dir = root_dir / "data" / "marketdata"
    news_dir = root_dir / "data" / "news"

    signals: list[dict] = []

    latest_quotes = _latest(market_dir, "quotes_*.jsonl")
    if latest_quotes:
        signals.extend(
            compute_price_signals(
                latest_quotes,
                pct_move_intraday=float(thresholds.get("pct_move_intraday", 2.0)),
                pct_move_close_to_close=float(thresholds.get("pct_move_close_to_close", 3.0)),
            )
        )

    latest_items = _latest(news_dir, "items_translated_*.jsonl") or _latest(news_dir, "items_*.jsonl")
    latest_ranked = _latest(news_dir, "top_opportunities_*.json")
    if latest_items and latest_ranked:
        signals.extend(
            compute_news_signals(
                latest_items,
                latest_ranked,
                news_keyword_score_min=float(thresholds.get("news_keyword_score_min", 3)),
            )
        )

    out_dir = root_dir / "data" / "signals"
    ensure_dir(out_dir)
    out_path = out_dir / f"signals_{datetime.now().strftime('%Y%m%d')}.jsonl"
    for signal in signals:
        append_jsonl(out_path, signal)

    return signals
