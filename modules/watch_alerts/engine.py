from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from modules.common.notification_gate import quiet_hours_active
from modules.alerts.state import load_alert_state, save_alert_state
from modules.common.utils import read_json
from modules.performance.notifier import send_performance_text
from modules.watch_alerts.helpers import (
    build_watch_message,
    extract_intraday_from_reasons,
    is_volume_candidate_allowed,
    latest,
    now_berlin,
    read_jsonl,
)


def _state_path(cfg: dict) -> str:
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    rel = cfg.get("alerts", {}).get("state_file", "data/alerts/state.json")
    p = Path(rel)
    return str(p if p.is_absolute() else root / p)


def load_state(cfg: dict) -> dict:
    return load_alert_state(_state_path(cfg))


def save_state(cfg: dict, state: dict) -> None:
    save_alert_state(_state_path(cfg), state)


def _parse_iso(v: str | None) -> datetime | None:
    if not v:
        return None
    try:
        return datetime.fromisoformat(v)
    except ValueError:
        return None


def should_send(isin: str, alert_type: str, now: datetime, cfg: dict, state: dict) -> bool:
    wa = cfg.get("watch_alerts", {})
    if not wa.get("enabled", True):
        return False

    counters = state.setdefault("counters", {"watch": 0, "marketdata": 0})
    if int(counters.get("watch", 0)) >= int(wa.get("max_per_day", 5)):
        return False

    day = now.date().isoformat()
    entry = state.setdefault("watch", {}).setdefault(isin, {"last_sent_ts": None, "dedupe": []})
    key = f"WATCH:{alert_type}:{isin}:{day}"
    if key in set(entry.setdefault("dedupe", [])):
        return False

    cooldown = timedelta(minutes=int(wa.get("cooldown_minutes_per_isin", 360)))
    last = _parse_iso(entry.get("last_sent_ts"))
    if last and now - last < cooldown:
        return False
    return True


def _load_inputs(cfg: dict) -> tuple[set[str], list[dict], list[dict], dict, str]:
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))

    holdings: set[str] = set()
    snapshot_path = latest(root / "data" / "snapshots", "portfolio_*.json")
    if snapshot_path:
        snapshot = read_json(snapshot_path)
        holdings = {str(p.get("isin")) for p in snapshot.get("positions", []) if p.get("isin")}

    signals = [s for s in read_jsonl(latest(root / "data" / "signals", "signals_*.jsonl")) if s.get("id") == "MULTI_FACTOR_SIGNAL"]

    news: list[dict] = []
    ranked = latest(root / "data" / "news", "top_opportunities_*.json")
    if ranked:
        top = read_json(ranked)
        news.extend(top.get("top", []))
    news.extend(read_jsonl(latest(root / "data" / "news", "items_translated_*.jsonl"))[:120])

    volume_lights: dict[str, str] = {}
    regime = "neutral"
    briefing = latest(root / "data" / "briefings", "morning_*.json")
    if briefing:
        brief = read_json(briefing)
        regime = (brief.get("regime") or {}).get("regime", "neutral")
        for row in (brief.get("volume_lights") or {}).get("holdings", []):
            isin = row.get("isin")
            if isin:
                volume_lights[str(isin)] = str(row.get("light", "gray"))

    return holdings, signals, news, volume_lights, regime


def _build_candidates(holdings: set[str], signals: list[dict], news: list[dict], volume_lights: dict[str, str], regime: str, state: dict, cfg: dict) -> list[dict]:
    wa = cfg.get("watch_alerts", {})
    min_score = float(wa.get("min_score", 3))
    candidates: list[dict] = []

    if wa.get("include_holdings", True):
        for signal in signals:
            isin = str(signal.get("isin") or "")
            score = float(signal.get("factor_score", 0) or 0)
            if isin in holdings and score >= min_score:
                reasons = signal.get("reasons", [])
                candidates.append(
                    {
                        "alert_type": "multi_factor",
                        "isin": isin,
                        "name": signal.get("name") or isin,
                        "reasons": ["multi_factor"],
                        "score": score,
                        "confidence": signal.get("confidence"),
                        "regime": regime,
                        "matched_news": any("news_score" in str(r) for r in reasons),
                        "pct_move_intraday": extract_intraday_from_reasons(reasons),
                    }
                )

    for item in news:
        isin = str(item.get("isin") or "")
        if not isin:
            continue
        is_holding = isin in holdings
        if is_holding and not wa.get("include_holdings", True):
            continue
        if (not is_holding) and not wa.get("include_radar", True):
            continue
        candidates.append(
            {
                "alert_type": "news",
                "isin": isin,
                "name": item.get("name") or item.get("title_de") or item.get("title") or isin,
                "reasons": ["news"],
                "score": item.get("score"),
                "confidence": item.get("confidence"),
                "regime": regime,
                "news_source": item.get("source"),
                "news_title": item.get("title_de") or item.get("title"),
                "matched_news": True,
            }
        )

    old_lights = (state.get("meta") or {}).get("last_volume_lights", {}) if isinstance((state.get("meta") or {}).get("last_volume_lights", {}), dict) else {}
    for isin, light in volume_lights.items():
        if light == "red" and old_lights.get(isin) != "red":
            candidates.append(
                {
                    "alert_type": "volume_red",
                    "isin": isin,
                    "name": isin,
                    "reasons": ["volume_red"],
                    "score": None,
                    "confidence": None,
                    "regime": regime,
                    "matched_news": False,
                    "pct_move_intraday": None,
                }
            )

    return candidates


def run(cfg: dict) -> None:
    wa = cfg.get("watch_alerts", {})
    if not wa.get("enabled", True):
        return

    now = now_berlin(cfg.get("app", {}).get("timezone", "Europe/Berlin"))
    if quiet_hours_active(cfg, now):
        return

    try:
        holdings, signals, news, volume_lights, regime = _load_inputs(cfg)
        state = load_state(cfg)
        state.setdefault("meta", {"last_volume_lights": {}, "last_regime": None, "last_regime_sent_day": ""})

        min_score = float(wa.get("min_score", 3))
        min_move = float(wa.get("min_intraday_move_for_volume", 1.5))
        candidates = _build_candidates(holdings, signals, news, volume_lights, regime, state, cfg)

        for candidate in candidates:
            if not is_volume_candidate_allowed(candidate, min_score, min_move):
                continue
            isin = str(candidate.get("isin") or "GLOBAL")
            alert_type = str(candidate.get("alert_type") or "watch")
            if not should_send(isin, alert_type, now, cfg, state):
                continue
            if not send_performance_text(build_watch_message(candidate), cfg):
                continue

            watch_entry = state.setdefault("watch", {}).setdefault(isin, {"last_sent_ts": None, "dedupe": []})
            watch_entry["last_sent_ts"] = now.isoformat()
            watch_entry.setdefault("dedupe", []).append(f"WATCH:{alert_type}:{isin}:{now.date().isoformat()}")
            counters = state.setdefault("counters", {"watch": 0, "marketdata": 0})
            counters["watch"] = int(counters.get("watch", 0)) + 1

        state["meta"]["last_volume_lights"] = volume_lights
        state["meta"]["last_regime"] = regime
        save_state(cfg, state)
    except Exception:
        return
