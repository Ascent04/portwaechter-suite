from __future__ import annotations

import json
from pathlib import Path

from modules.common.utils import read_json


def _read_jsonl(path: str | Path) -> list[dict]:
    rows: list[dict] = []
    file_path = Path(path)
    if not file_path.exists():
        return rows

    with file_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _sort_key(quote: dict) -> tuple[str, str, str]:
    return (
        str(quote.get("date", "")),
        str(quote.get("time", "")),
        str(quote.get("fetched_at", "")),
    )


def _news_candidates(ranked_json: str | Path, news_keyword_score_min: float) -> list[dict]:
    ranked = read_json(ranked_json) if Path(ranked_json).exists() else {}
    candidates: list[dict] = []
    for item in ranked.get("top", []):
        score = float(item.get("score", 0))
        if score >= news_keyword_score_min:
            candidates.append(item)
    return candidates


def compute_price_signals(
    quotes_jsonl: str | Path,
    pct_move_intraday: float = 2.0,
    pct_move_close_to_close: float = 3.0,
) -> list[dict]:
    quotes = _read_jsonl(quotes_jsonl)
    signals: list[dict] = []

    by_isin: dict[str, list[dict]] = {}
    for quote in quotes:
        if quote.get("status") != "ok":
            continue

        isin = quote.get("isin")
        if not isin:
            continue

        by_isin.setdefault(isin, []).append(quote)

        open_price = quote.get("open")
        close_price = quote.get("close")
        if not open_price or not close_price:
            continue

        intraday = ((close_price - open_price) / open_price) * 100
        if abs(intraday) >= pct_move_intraday:
            signals.append(
                {
                    "id": "PRICE_INTRADAY_MOVE",
                    "key": f"intraday:{isin}:{quote.get('date')}:{quote.get('time')}",
                    "isin": isin,
                    "name": quote.get("name"),
                    "symbol": quote.get("symbol"),
                    "value_pct": round(intraday, 2),
                    "message": f"Intraday move {round(intraday, 2)}% for {quote.get('name')}",
                    "source": "quotes",
                }
            )

    for isin, rows in by_isin.items():
        rows.sort(key=_sort_key)
        if len(rows) < 2:
            continue

        previous = rows[-2]
        current = rows[-1]
        previous_close = previous.get("close")
        current_close = current.get("close")
        if not previous_close or not current_close:
            continue

        close_move = ((current_close - previous_close) / previous_close) * 100
        if abs(close_move) >= pct_move_close_to_close:
            signals.append(
                {
                    "id": "PRICE_CLOSE_TO_CLOSE_MOVE",
                    "key": f"c2c:{isin}:{current.get('date')}:{current.get('time')}",
                    "isin": isin,
                    "name": current.get("name"),
                    "symbol": current.get("symbol"),
                    "value_pct": round(close_move, 2),
                    "message": f"Close-to-close move {round(close_move, 2)}% for {current.get('name')}",
                    "source": "quotes",
                }
            )

    return signals


def compute_news_signals(
    items_jsonl: str | Path,
    ranked_json: str | Path,
    news_keyword_score_min: float = 3,
) -> list[dict]:
    _ = _read_jsonl(items_jsonl)
    candidates = _news_candidates(ranked_json, news_keyword_score_min)

    signals: list[dict] = []
    for item in candidates:
        score = float(item.get("score", 0))
        item_key = item.get("id") or item.get("link") or item.get("title")
        signals.append(
            {
                "id": "NEWS_OPPORTUNITY",
                "key": f"news:{item_key}",
                "title": item.get("title_de") or item.get("title"),
                "score": score,
                "link": item.get("link"),
                "message": f"News opportunity score {score}: {item.get('title_de') or item.get('title')}",
                "source": "news_ranked",
            }
        )

    return signals
