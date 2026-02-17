from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib import parse, request

from modules.common.state import load_state, mark_sent, save_state, should_send
from modules.common.utils import now_iso_tz, read_json, write_json
from modules.decision_engine.expectancy import attach_expectancy
from modules.decision_engine.risk_integration import apply_position_sizing


def _latest(path: Path, pattern: str) -> Path | None:
    files = sorted(path.glob(pattern))
    return files[-1] if files else None


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _load_inputs(cfg: dict) -> tuple[list[dict], list[dict], list[dict], list[dict], str, dict]:
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    briefing_path = _latest(root / "data" / "briefings", "morning_*.json")
    briefing = read_json(briefing_path) if briefing_path else {}

    holdings = briefing.get("positions", []) if isinstance(briefing, dict) else []
    radar = briefing.get("top_opportunities", []) if isinstance(briefing, dict) else []
    regime = (briefing.get("regime") or {}).get("regime", "neutral") if isinstance(briefing, dict) else "neutral"

    volume_map = {}
    for row in ((briefing.get("volume_lights") or {}).get("holdings", []) if isinstance(briefing, dict) else []):
        if row.get("isin"):
            volume_map[str(row.get("isin"))] = str(row.get("light", "gray"))

    signals = []
    now = datetime.now(timezone.utc)
    sig_path = _latest(root / "data" / "signals", "signals_*.jsonl")
    if sig_path:
        for item in _read_jsonl(sig_path):
            if item.get("id") != "MULTI_FACTOR_SIGNAL":
                continue
            created = str(item.get("created_at") or "")
            if created:
                try:
                    dt = datetime.fromisoformat(created)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if now - dt > timedelta(hours=24):
                        continue
                except ValueError:
                    pass
            signals.append(item)

    news = []
    news_path = _latest(root / "data" / "news", "top_opportunities_*.json")
    if news_path:
        news = (read_json(news_path) or {}).get("top", [])

    return holdings, radar, signals, news, regime, volume_map


def score_candidates(holdings: list[dict], radar: list[dict], signals: list[dict], news: list[dict], regime: str, volume_lights: dict) -> list[dict]:
    holdings_isins = {str(p.get("isin")) for p in holdings if p.get("isin")}
    by_isin: dict[str, dict] = {}

    for s in signals:
        isin = str(s.get("isin") or "")
        if not isin:
            continue
        row = by_isin.setdefault(
            isin,
            {
                "isin": isin,
                "name": s.get("name"),
                "in_holdings": isin in holdings_isins,
                "signal_factor_score": 0.0,
                "news_score": 0.0,
                "direction": s.get("direction", "neutral"),
                "volume_light": volume_lights.get(isin, "gray"),
                "reasons": [],
            },
        )
        row["signal_factor_score"] = max(float(row["signal_factor_score"]), float(s.get("factor_score", 0)))
        row["reasons"] = list(set(row["reasons"] + [str(r) for r in s.get("reasons", [])]))

    for n in news:
        isin = str(n.get("isin") or "")
        if not isin:
            continue
        row = by_isin.setdefault(
            isin,
            {
                "isin": isin,
                "name": n.get("name"),
                "in_holdings": isin in holdings_isins,
                "signal_factor_score": 0.0,
                "news_score": 0.0,
                "direction": "neutral",
                "volume_light": volume_lights.get(isin, "gray"),
                "reasons": [],
            },
        )
        row["name"] = row.get("name") or n.get("name") or n.get("title")
        row["news_score"] = max(float(row["news_score"]), float(n.get("score", 0)))

    for r in radar:
        isin = str(r.get("isin") or "")
        if not isin:
            continue
        row = by_isin.setdefault(isin, {"isin": isin, "name": r.get("name"), "in_holdings": False, "signal_factor_score": 0.0, "news_score": 0.0, "direction": "neutral", "volume_light": volume_lights.get(isin, "gray"), "reasons": []})
        row["news_score"] = max(float(row["news_score"]), float(r.get("opportunity_score", 0)))

    candidates = []
    vol_bonus = {"green": 1.0, "yellow": 0.5, "red": 0.0, "gray": 0.0}
    for row in by_isin.values():
        score = float(row["signal_factor_score"]) + float(row["news_score"]) + vol_bonus.get(str(row["volume_light"]), 0.0)
        row["score"] = round(score, 2)
        row["regime"] = regime
        candidates.append(row)

    candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
    return candidates


def classify_candidate(candidate: dict, bias: str = "long-only") -> dict:
    score = float(candidate.get("score", 0))
    news_score = float(candidate.get("news_score", 0))
    vol = str(candidate.get("volume_light", "gray"))
    regime = str(candidate.get("regime", "neutral"))
    direction = str(candidate.get("direction", "neutral"))
    expectancy = candidate.get("expectancy_3d")
    expectancy_conf = str(candidate.get("expectancy_confidence", "unavailable"))
    expectancy_blocks_setup = expectancy is None or float(expectancy) <= 0 or expectancy_conf in {"low", "unavailable"}

    reasons = []
    if score >= 7 and vol in {"green", "yellow"} and not (bias == "long-only" and direction == "bearish") and regime != "risk_off" and not expectancy_blocks_setup:
        bucket = "SETUP"
        reasons.append("high_score")
    elif score >= 5 or (news_score >= 4 and vol != "gray"):
        bucket = "WATCH"
        reasons.append("watch_threshold")
    elif score < 3 and news_score == 0 and float(candidate.get("signal_factor_score", 0)) == 0:
        bucket = "DROP"
        reasons.append("no_signal_no_news")
    else:
        bucket = "OBSERVE"
        reasons.append("monitor")
    if expectancy_blocks_setup:
        reasons.append("expectancy_gate")

    confidence = "high" if score >= 7 else "medium" if score >= 5 else "speculative"
    return {"bucket": bucket, "reasons": reasons, "confidence": confidence}


def write_decision_queue(queue: dict, cfg: dict) -> Path:
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    out = root / "data" / "decisions" / f"decision_queue_{datetime.now().strftime('%Y%m%d')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    write_json(out, queue)
    return out


def _send_telegram(text: str, cfg: dict) -> bool:
    tg = cfg.get("notify", {}).get("telegram", {})
    if not tg.get("enabled", False):
        return False
    token = os.getenv(tg.get("bot_token_env", "TG_BOT_TOKEN"))
    chat_id = os.getenv(tg.get("chat_id_env", "TG_CHAT_ID"))
    if not token or not chat_id:
        return False
    payload = parse.urlencode({"chat_id": chat_id, "text": text[:3400]}).encode("utf-8")
    req = request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=payload, method="POST")
    try:
        with request.urlopen(req, timeout=10):
            return True
    except Exception:
        return False


def notify_decision_queue(queue: dict, cfg: dict) -> None:
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    state_path = root / "data" / "state" / "notify_state.json"
    state = load_state(state_path)
    now_iso = now_iso_tz(cfg.get("app", {}).get("timezone", "Europe/Berlin"))
    cooldown = int(cfg.get("notify", {}).get("telegram", {}).get("cooldown_min", 30))
    key = f"DECISION_QUEUE:{datetime.now().strftime('%Y%m%d')}"

    if not should_send(key, now_iso, cooldown, state):
        return

    top = queue.get("candidates", [])[:5]
    lines = ["PortWächter Decision Queue", f"Regime: {queue.get('regime')}"]
    for c in top:
        lines.append(f"- {c.get('bucket')} {c.get('name') or c.get('isin')} | Score {c.get('score')} | {c.get('confidence')}")

    if _send_telegram("\n".join(lines), cfg):
        mark_sent(key, now_iso, state)
        save_state(state_path, state)


def run(cfg: dict) -> dict:
    holdings, radar, signals, news, regime, volume_lights = _load_inputs(cfg)
    bias = str(cfg.get("decision", {}).get("bias", "long-only") or "long-only")
    candidates = score_candidates(holdings, radar, signals, news, regime, volume_lights)
    candidates = attach_expectancy(candidates, cfg)
    candidates = apply_position_sizing(candidates, cfg, regime)

    for c in candidates:
        c.update(classify_candidate(c, bias=bias))

    queue = {
        "generated_at": now_iso_tz(cfg.get("app", {}).get("timezone", "Europe/Berlin")),
        "regime": regime,
        "candidates": candidates,
    }
    write_decision_queue(queue, cfg)

    watch_items = [
        {
            "isin": c.get("isin"),
            "name": c.get("name"),
            "bucket": c.get("bucket"),
            "score": c.get("score"),
            "confidence": c.get("confidence"),
        }
        for c in candidates
        if c.get("bucket") in {"WATCH", "SETUP"}
    ]
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    write_json(root / "data" / "watchlist" / "watchlist.json", {"updated_at": queue["generated_at"], "items": watch_items})

    notify_decision_queue(queue, cfg)
    return queue
