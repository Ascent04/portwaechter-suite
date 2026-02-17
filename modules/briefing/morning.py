from __future__ import annotations

import argparse
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib import parse, request

from modules.briefing.delta import compute_delta, find_previous_briefing, load_previous_briefing
from modules.briefing.helpers import briefing_text, latest, read_jsonl, signal_time, to_float
from modules.briefing.regime import compute_market_regime
from modules.briefing.volume_lights import compute_volume_lights_for_holdings, load_volume_baseline
from modules.common.config import load_config
from modules.common.utils import now_iso_tz, read_json, write_json

def _briefing_cfg(cfg: dict) -> dict:
    src = cfg.get("briefing", {}).get("morning", {})
    return {
        "delta_lookback_days": int(src.get("delta_lookback_days", 7)),
        "volume_lights": {
            "green_ratio": float(src.get("volume_lights", {}).get("green_ratio", 2.0)),
            "yellow_ratio": float(src.get("volume_lights", {}).get("yellow_ratio", 1.3)),
            "min_volume_points": int(src.get("volume_lights", {}).get("min_volume_points", 20)),
        },
    }

def _latest_quotes(root: Path) -> dict:
    path = latest(root / "data" / "marketdata", "quotes_*.jsonl")
    quotes: dict[str, dict] = {}
    if not path:
        return quotes
    for row in read_jsonl(path):
        isin = str(row.get("isin") or "")
        if not isin or row.get("status") != "ok":
            continue
        quotes[isin] = row
    return quotes

def load_portfolio_snapshot(cfg: dict) -> dict:
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    snapshot_path = next(
        (p for p in [latest(root / "data" / "portfolio", "*.json"), latest(root / "data" / "snapshots", "portfolio_*.json")] if p),
        None,
    )
    if not snapshot_path:
        return {"positions": []}
    data = read_json(snapshot_path)
    quote_by_isin = _latest_quotes(root)
    positions = []
    for pos in data.get("positions", []):
        isin = pos.get("isin")
        avg_price = to_float(pos.get("avg_price") or pos.get("price_eur"))
        row = quote_by_isin.get(str(isin))
        last_price = to_float((row or {}).get("close")) or to_float(pos.get("last_price") or pos.get("price_eur"))
        pnl_pct = to_float(pos.get("pnl_pct"))
        if pnl_pct is None and avg_price and last_price and avg_price != 0:
            pnl_pct = round(((last_price - avg_price) / avg_price) * 100, 2)

        positions.append(
            {
                "isin": isin,
                "name": pos.get("name"),
                "quantity": to_float(pos.get("quantity")) or 0,
                "avg_price": avg_price,
                "last_price": last_price,
                "pnl_pct": pnl_pct,
            }
        )
    return {"positions": positions}

def load_latest_signals(cfg: dict) -> list[dict]:
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    signals_dir = root / "data" / "signals"
    now = datetime.now(timezone.utc)
    dedup: dict[tuple[str, str], dict] = {}
    for path in sorted(signals_dir.glob("signals_*.jsonl")):
        for item in read_jsonl(path):
            if item.get("id") != "MULTI_FACTOR_SIGNAL":
                continue
            ts = signal_time(item)
            if ts and now - ts > timedelta(hours=24):
                continue
            direction_raw = str(item.get("direction", "neutral")).lower()
            direction = "up" if direction_raw in {"bullish", "up"} else "down" if direction_raw in {"bearish", "down"} else "neutral"
            row = {
                "isin": item.get("isin"),
                "name": item.get("name"),
                "direction": direction,
                "factor_score": int(item.get("factor_score", 0)),
                "reasons": [str(r).split("=", 1)[0] for r in item.get("reasons", [])],
            }
            key = (str(row.get("isin")), direction)
            prev = dedup.get(key)
            if not prev or row["factor_score"] >= prev["factor_score"]:
                dedup[key] = row
    return sorted(dedup.values(), key=lambda r: r.get("factor_score", 0), reverse=True)
def load_ranked_news(cfg: dict) -> list[dict]:
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    path = latest(root / "data" / "news", "top_opportunities_*.json")
    if not path:
        return []
    ranked = read_json(path)
    result = []
    for item in ranked.get("top", []):
        score = to_float(item.get("score")) or 0
        if score < 3:
            continue
        title = item.get("title") or ""
        title_de = item.get("title_de") or title
        isin = item.get("isin")
        if not isin:
            match = re.search(r"[A-Z]{2}[A-Z0-9]{10}", f"{title} {title_de}")
            isin = match.group(0) if match else None
        name = item.get("name") or title_de.split(" - ", 1)[0][:80]
        result.append({"isin": isin, "name": name, "title": title, "title_translated": title_de, "score": score, "source": item.get("source")})
        if len(result) >= 10:
            break
    return result

def build_briefing(snapshot: dict, signals: list[dict], news: list[dict], cfg: dict | None = None) -> dict:
    threshold = int((cfg or {}).get("signals", {}).get("thresholds", {}).get("multi_factor_score_min", 2))
    positions = [p for p in snapshot.get("positions", []) if p.get("isin")]
    holdings_isins = {str(p.get("isin")) for p in positions}
    winners = sorted([p for p in positions if (p.get("pnl_pct") or 0) > 0], key=lambda p: p.get("pnl_pct", 0), reverse=True)[:3]
    losers = sorted([p for p in positions if (p.get("pnl_pct") or 0) < 0], key=lambda p: p.get("pnl_pct", 0))[:3]
    invested = sum((to_float(p.get("avg_price")) or 0) * (to_float(p.get("quantity")) or 0) for p in positions)
    market = sum((to_float(p.get("last_price")) or 0) * (to_float(p.get("quantity")) or 0) for p in positions)
    total_pnl_pct = round(((market - invested) / invested) * 100, 2) if invested > 0 else 0.0

    holdings_summary = (
        " | ".join([f"+ {p.get('name')} {p.get('pnl_pct')}%" for p in winners] + [f"- {p.get('name')} {p.get('pnl_pct')}%" for p in losers])
        or "Keine PnL-Daten verfügbar"
    )
    active = [s for s in signals if int(s.get("factor_score", 0)) >= threshold]
    holdings_signals = [s for s in active if str(s.get("isin")) in holdings_isins]
    radar_signals = [s for s in active if str(s.get("isin")) not in holdings_isins]
    up = [s for s in holdings_signals if s.get("direction") == "up"]
    down = [s for s in holdings_signals if s.get("direction") == "down"]
    signals_summary = f"Up: {len(up)} | Down: {len(down)} | Total: {len(holdings_signals)}"

    radar_news = [n for n in news if str(n.get("isin")) not in holdings_isins]
    by_key: dict[str, dict] = {}
    for s in radar_signals:
        key = str(s.get("isin") or f"sig-{len(by_key)}")
        row = by_key.setdefault(key, {"isin": s.get("isin"), "name": None, "signal": 0.0, "news": 0.0, "reasons": []})
        row["signal"] = max(row["signal"], float(s.get("factor_score", 0)))
        row["name"] = row["name"] or s.get("name")
        row["reasons"] = s.get("reasons", [])
    for n in radar_news:
        key = str(n.get("isin") or n.get("title"))
        row = by_key.setdefault(key, {"isin": n.get("isin"), "name": None, "signal": 0.0, "news": 0.0, "reasons": []})
        row["news"] = max(row["news"], min(float(n.get("score", 0)), 5.0))
        row["name"] = row["name"] or n.get("name")
    opportunities = []
    for row in by_key.values():
        score = (row["signal"] * 2) + row["news"]
        if score < 3:
            continue
        reasons = [str(r) for r in row.get("reasons", [])]
        if row["news"] > 0 and any("volume" in r for r in reasons):
            reason = "Volumenauffälligkeit"
        elif row["news"] > 0:
            reason = "News-getrieben"
        elif row["signal"] > 0:
            reason = "Trendfortsetzung"
        else:
            reason = "Beobachtung"
        confidence = "hoch" if score >= 7 else "mittel" if score >= 5 else "spekulativ"
        opportunities.append({"isin": row.get("isin"), "name": row.get("name"), "reason": reason, "confidence": confidence, "opportunity_score": round(score, 2)})
    opportunities.sort(key=lambda x: x.get("opportunity_score", 0), reverse=True)
    return {
        "holdings_summary": holdings_summary,
        "signals_summary": signals_summary,
        "top_opportunities": opportunities[:5],
        "holdings_block": {"top_winners": winners, "top_losers": losers, "total_pnl_pct": total_pnl_pct},
        "holdings_signals": holdings_signals,
        "positions": positions,
        "generated_at": now_iso_tz(),
    }

def send_briefing(cfg: dict, briefing_json: dict) -> None:
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    out_path = root / "data" / "briefings" / f"morning_{datetime.now().strftime('%Y%m%d')}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(out_path, briefing_json)
    tg_cfg = cfg.get("notify", {}).get("telegram", {})
    if not tg_cfg.get("enabled", False):
        return

    token = os.getenv(tg_cfg.get("bot_token_env", "TG_BOT_TOKEN"))
    chat_id = os.getenv(tg_cfg.get("chat_id_env", "TG_CHAT_ID"))
    if not token or not chat_id:
        return
    text = briefing_text(briefing_json)
    payload = parse.urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
    req = request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=payload, method="POST")
    try:
        with request.urlopen(req, timeout=10):
            return
    except Exception:
        return

def run() -> None:
    cfg = load_config()
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    mcfg = _briefing_cfg(cfg)
    snapshot = load_portfolio_snapshot(cfg)
    signals = load_latest_signals(cfg)
    news = load_ranked_news(cfg)
    briefing = build_briefing(snapshot, signals, news, cfg=cfg)
    prev_file = find_previous_briefing(root / "data" / "briefings", mcfg["delta_lookback_days"])
    briefing["delta"] = compute_delta(load_previous_briefing(prev_file), briefing)

    quotes = _latest_quotes(root)
    baseline = load_volume_baseline(root / "data" / "marketdata" / "volume_baseline.json")
    lights = compute_volume_lights_for_holdings(briefing.get("positions", []), quotes, baseline, mcfg["volume_lights"])
    briefing["volume_lights"] = {"holdings": lights}
    briefing["regime"] = compute_market_regime(briefing.get("positions", []), briefing.get("holdings_signals", []), cfg)
    send_briefing(cfg, briefing)
def _cli() -> None:
    parser = argparse.ArgumentParser(description="Morning briefing runner")
    parser.add_argument("command", choices=["run"])
    args = parser.parse_args()
    if args.command == "run":
        run()

if __name__ == "__main__":
    _cli()
