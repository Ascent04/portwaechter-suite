from __future__ import annotations

import json

from modules.common.utils import read_json
from modules.marketdata_watcher.volume_baseline import load_volume_baseline
from modules.v2.config import load_v2_config, root_dir
from modules.v2.marketdata.batch_quotes import fetch_quotes_for_instruments
from modules.v2.scanner.momentum import score_momentum
from modules.v2.scanner.news_impact import score_news
from modules.v2.scanner.relative_strength import score_relative_strength
from modules.v2.scanner.volume_spike import score_volume
from modules.v2.universe.holdings_universe import load_current_holdings
from modules.v2.universe.scanner_universe import load_scanner_universe, merge_universes


def _latest_news(cfg: dict) -> list[dict]:
    news_dir = root_dir(cfg) / "data" / "news"
    items: list[dict] = []

    ranked = sorted(news_dir.glob("top_opportunities_*.json"))
    if ranked:
        top = read_json(ranked[-1])
        items.extend(top.get("top", []) if isinstance(top, dict) else [])

    translated = sorted(news_dir.glob("items_translated_*.jsonl"))
    if translated:
        with translated[-1].open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return items


def run_scanner(
    cfg: dict | None = None,
    holdings: list[dict] | None = None,
    scanner: list[dict] | None = None,
    quotes: list[dict] | None = None,
    news_items: list[dict] | None = None,
) -> list[dict]:
    active_cfg = cfg or load_v2_config()
    holdings_rows = holdings if holdings is not None else load_current_holdings(active_cfg)
    scanner_rows = scanner if scanner is not None else load_scanner_universe(active_cfg)
    universe = merge_universes(holdings_rows, scanner_rows)
    quote_rows = quotes if quotes is not None else fetch_quotes_for_instruments(universe, active_cfg)
    quote_map = {str(row.get("symbol") or "").upper(): row.get("quote") for row in quote_rows}
    baseline = load_volume_baseline(root_dir(active_cfg) / "data" / "marketdata" / "volume_baseline.json")
    latest_news = news_items if news_items is not None else _latest_news(active_cfg)

    candidates: list[dict] = []
    peer_moves = [
        float(quote["percent_change"])
        for quote in quote_map.values()
        if isinstance(quote, dict) and quote.get("status") == "ok" and quote.get("percent_change") is not None
    ]
    for item in universe:
        symbol = str(item.get("symbol") or "").upper()
        quote = quote_map.get(symbol) or {"symbol": symbol, "status": "error", "provider": "none"}
        momentum = score_momentum(quote)
        baseline_key = str(item.get("isin") or item.get("symbol") or "")
        volume = score_volume(quote, baseline.get(baseline_key))
        news = score_news(latest_news, item)
        relative = score_relative_strength(quote, peer_moves)

        candidates.append(
            {
                "symbol": item.get("symbol"),
                "isin": item.get("isin"),
                "name": item.get("name"),
                "country": item.get("country"),
                "sector": item.get("sector"),
                "theme": item.get("theme"),
                "group": item.get("group", "scanner"),
                "weight_pct": item.get("weight_pct", 0.0),
                "quote": quote,
                "scores": {
                    "momentum": momentum["score"],
                    "volume": volume["score"],
                    "news": news["score"],
                    "relative_strength": relative["score"],
                },
                "details": {
                    "momentum": momentum,
                    "volume": volume,
                    "news": news,
                    "relative_strength": relative,
                },
                "provider": quote.get("provider", "none"),
                "status": "ok" if quote.get("status") == "ok" else "quote_error",
            }
        )
    return candidates
