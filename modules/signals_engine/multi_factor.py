from __future__ import annotations

import json
import re
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


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def _news_candidates(ranked_json: str | Path, score_min: float) -> list[dict]:
    ranked = read_json(ranked_json) if Path(ranked_json).exists() else {}
    candidates: list[dict] = []
    for item in ranked.get("top", []):
        score = float(item.get("score", 0))
        if score >= score_min:
            candidates.append(item)
    return candidates


def _text_has_name(text: str, name: str) -> bool:
    tokens = [t for t in re.findall(r"[A-Za-z0-9]+", name.lower()) if len(t) >= 4]
    lowered = text.lower()
    return any(token in lowered for token in tokens[:4])


def _volume_stats(
    rows: list[dict],
    baseline: dict,
    isin: str,
    min_volume_points: int,
) -> tuple[float | None, int]:
    base_entry = baseline.get(isin, {}) if isinstance(baseline.get(isin), dict) else {}
    base_vols = [float(v) for v in base_entry.get("volumes_last_n", []) if isinstance(v, (int, float))]
    intraday_vols = [float(row.get("volume")) for row in rows if row.get("volume") not in (None, "")]

    combined = base_vols + intraday_vols
    if len(combined) < min_volume_points:
        return None, len(combined)

    return _median(combined), len(combined)


def compute_multi_factor_signals(
    quotes_jsonl: str | Path,
    ranked_json: str | Path,
    volume_baseline_json: str | Path | None = None,
    pct_move_intraday: float = 2.0,
    pct_move_close_to_close: float = 3.0,
    news_keyword_score_min: float = 3,
    volume_spike_ratio: float = 1.8,
    multi_factor_score_min: float = 2,
    min_volume_points: int = 20,
    pct_move_intraday_no_news: float = 2.5,
    pct_move_close_to_close_no_news: float = 3.5,
) -> list[dict]:
    quotes = [q for q in _read_jsonl(quotes_jsonl) if q.get("status") == "ok" and q.get("isin")]
    news = _news_candidates(ranked_json, news_keyword_score_min)
    baseline = {}
    if volume_baseline_json and Path(volume_baseline_json).exists():
        baseline = read_json(volume_baseline_json)

    by_isin: dict[str, list[dict]] = {}
    for quote in quotes:
        by_isin.setdefault(str(quote.get("isin")), []).append(quote)

    signals: list[dict] = []
    for isin, rows in by_isin.items():
        rows.sort(key=_sort_key)
        current = rows[-1]

        factors: dict[str, int | str] = {"price": 0, "news": 0, "volume": 0}
        reasons: list[str] = []

        open_price = current.get("open")
        close_price = current.get("close")
        intraday_move = None
        if open_price and close_price:
            intraday_move = ((close_price - open_price) / open_price) * 100
            if abs(intraday_move) >= pct_move_intraday:
                factors["price"] = int(factors["price"]) + 1
                reasons.append(f"price_intraday={round(intraday_move, 2)}%")

        c2c_move = None
        if len(rows) >= 2 and rows[-2].get("close") and close_price:
            previous_close = rows[-2]["close"]
            c2c_move = ((close_price - previous_close) / previous_close) * 100
            if abs(c2c_move) >= pct_move_close_to_close:
                factors["price"] = int(factors["price"]) + 1
                reasons.append(f"price_c2c={round(c2c_move, 2)}%")

        baseline_median, sample_count = _volume_stats(rows, baseline, isin, min_volume_points)
        if baseline_median is None:
            factors["volume"] = "unavailable"
            reasons.append(f"Volume history insufficient (<{min_volume_points})")
        else:
            latest_volume = current.get("volume")
            if latest_volume:
                ratio = float(latest_volume) / baseline_median if baseline_median > 0 else 0.0
                if ratio >= volume_spike_ratio:
                    factors["volume"] = 1
                    reasons.append(f"volume_spike={round(ratio, 2)}x")

        current_name = str(current.get("name") or "")
        matched_news = []
        for item in news:
            text = f"{item.get('title_de') or item.get('title') or ''} {item.get('summary') or ''}".lower()
            if isin.lower() in text or _text_has_name(text, current_name):
                matched_news.append(item)

        if matched_news:
            factors["news"] = 1
            best_news = max(matched_news, key=lambda item: float(item.get("score", 0)))
            reasons.append(f"news_score={float(best_news.get('score', 0))}")
        else:
            best_news = None

        factor_score = int(factors["price"]) + int(factors["news"]) + int(factors["volume"] if isinstance(factors["volume"], int) else 0)
        if factor_score < multi_factor_score_min:
            continue

        if int(factors["news"]) == 0:
            strong_price = False
            if intraday_move is not None and abs(intraday_move) >= pct_move_intraday_no_news:
                strong_price = True
            if c2c_move is not None and abs(c2c_move) >= pct_move_close_to_close_no_news:
                strong_price = True
            if not strong_price:
                continue
            reasons.append("no_news_strong_price_gate")

        direction = "neutral"
        if intraday_move is not None:
            direction = "bullish" if intraday_move >= 0 else "bearish"

        message = (
            f"Multi-Faktor {direction} {current_name}: "
            f"Score {factor_score} (price={factors['price']}, news={factors['news']}, volume={factors['volume']})"
        )

        signals.append(
            {
                "id": "MULTI_FACTOR_SIGNAL",
                "key": f"mf:{isin}:{current.get('date')}:{current.get('time')}",
                "isin": isin,
                "name": current_name,
                "symbol": current.get("symbol"),
                "factor_score": factor_score,
                "direction": direction,
                "factors": factors,
                "reasons": reasons,
                "sample_count": sample_count,
                "link": best_news.get("link") if best_news else None,
                "message": message,
                "source": "multi_factor",
            }
        )

    return signals
