from __future__ import annotations

from datetime import datetime
from pathlib import Path

from modules.common.utils import append_jsonl, ensure_dir
from modules.performance.log_events import append_event, build_signal_event
from modules.signals_engine.multi_factor import compute_multi_factor_signals
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
    volume_baseline_path = market_dir / "volume_baseline.json"

    signals: list[dict] = []

    latest_quotes = _latest(market_dir, "quotes_*.jsonl")
    latest_ranked = _latest(news_dir, "top_opportunities_*.json")

    if latest_quotes and latest_ranked:
        signals.extend(
            compute_multi_factor_signals(
                latest_quotes,
                latest_ranked,
                pct_move_intraday=float(thresholds.get("pct_move_intraday", 2.0)),
                pct_move_close_to_close=float(thresholds.get("pct_move_close_to_close", 3.0)),
                news_keyword_score_min=float(thresholds.get("news_keyword_score_min", 3)),
                volume_spike_ratio=float(thresholds.get("volume_spike_ratio", 1.8)),
                multi_factor_score_min=float(thresholds.get("multi_factor_score_min", 2)),
                min_volume_points=int(thresholds.get("min_volume_points", 20)),
                pct_move_intraday_no_news=float(thresholds.get("pct_move_intraday_no_news", 2.5)),
                pct_move_close_to_close_no_news=float(thresholds.get("pct_move_close_to_close_no_news", 3.5)),
                volume_baseline_json=volume_baseline_path,
            )
        )

    if latest_quotes:
        signals.extend(
            compute_price_signals(
                latest_quotes,
                pct_move_intraday=float(thresholds.get("pct_move_intraday", 2.0)),
                pct_move_close_to_close=float(thresholds.get("pct_move_close_to_close", 3.0)),
            )
        )

    latest_items = _latest(news_dir, "items_translated_*.jsonl") or _latest(news_dir, "items_*.jsonl")
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
        if signal.get("id") == "MULTI_FACTOR_SIGNAL" and cfg.get("performance", {}).get("enabled", True):
            try:
                append_event(build_signal_event(signal, cfg), cfg)
            except Exception:
                pass

    return signals
