from __future__ import annotations

import json
import logging
import os
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from modules.alerts.state import load_alert_state, save_alert_state
from modules.common.utils import append_jsonl, ensure_dir, now_iso_tz
from modules.marketdata_watcher.grouping import classify_isin, load_holdings_isins
from modules.marketdata_watcher.rules import effective_thresholds, evaluate_triggers

log = logging.getLogger(__name__)


def _read_jsonl(path: str | Path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    rows: list[dict] = []
    with p.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _state_path(cfg: dict) -> str:
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    rel = cfg.get("alerts", {}).get("state_file", "data/alerts/state.json")
    p = Path(rel)
    return str(p if p.is_absolute() else root / p)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _profile_name(cfg: dict) -> str:
    return str(cfg.get("alert_profiles", {}).get("current", "normal")).lower()


def _log_summary(evaluated: int, sent: int, reasons: Counter[str]) -> None:
    suppressed = sum(reasons.values())
    log.warning(
        "marketdata_alerts summary: evaluated=%s sent=%s suppressed=%s reasons=%s",
        evaluated,
        sent,
        suppressed,
        dict(reasons),
    )


def detect_intraday_moves(quotes_jsonl_path: str | Path, out_alerts_path: str | Path, cfg: dict) -> list[dict]:
    mcfg = cfg.get("marketdata_alerts", {})
    profile = _profile_name(cfg)

    quotes = _read_jsonl(quotes_jsonl_path)
    evaluated = 0
    reason_counts: Counter[str] = Counter()

    if not mcfg.get("enabled", True):
        for row in quotes:
            if row.get("isin"):
                evaluated += 1
                reason_counts["profile_off" if profile == "off" else "market_disabled"] += 1
        _log_summary(evaluated, 0, reason_counts)
        return []

    debug_alerts = os.getenv("DEBUG_ALERTS", "0") == "1" or bool(cfg.get("debug", {}).get("alerts", False))
    state = load_alert_state(_state_path(cfg))
    md_state = state.setdefault("marketdata", {})
    counters = state.setdefault("counters", {"watch": 0, "marketdata": 0})

    cooldown = timedelta(minutes=int(mcfg.get("cooldown_minutes_per_isin", 120)))
    max_per_day = int(mcfg.get("max_per_day", 10))
    msg_max_len = int(((mcfg.get("message") or {}).get("max_len", 900)))
    now = datetime.fromisoformat(now_iso_tz(cfg.get("app", {}).get("timezone", "Europe/Berlin")))

    holdings = load_holdings_isins(cfg)
    adaptive_cache: dict[str, list[float]] = {}
    alerts: list[dict] = []

    for quote in quotes:
        isin = str(quote.get("isin") or "")
        if not isin:
            continue
        evaluated += 1

        status = quote.get("status")
        if status == "missing_mapping":
            reason_counts["missing_mapping"] += 1
            continue
        if status != "ok":
            reason_counts["missing_quote_fields"] += 1
            continue

        open_price = quote.get("open")
        close_price = quote.get("close")
        if not open_price or not close_price:
            reason_counts["missing_quote_fields"] += 1
            continue

        current_pct = round(((close_price - open_price) / open_price) * 100.0, 2)
        prev = md_state.get(isin, {}) if isinstance(md_state.get(isin), dict) else {}
        group = classify_isin(isin, holdings)
        thresholds = effective_thresholds(cfg, group, isin, adaptive_cache)

        triggers, delta_pct, direction, suppress_reason = evaluate_triggers(current_pct, prev, thresholds, cfg)

        if profile == "quiet" and bool(mcfg.get("threshold_cross_only", False)):
            if not any(t in {"threshold_cross", "initial_threshold"} for t in triggers):
                reason_counts["quiet_profile_market_disabled"] += 1
                if debug_alerts:
                    log.warning(
                        "marketdata_alerts suppressed isin=%s reason=%s pct=%.2f delta=%.2f group=%s",
                        isin,
                        "quiet_profile_market_disabled",
                        current_pct,
                        delta_pct,
                        group,
                    )
                continue

        if not triggers:
            reason_counts[suppress_reason or "below_min_delta"] += 1
            if debug_alerts:
                log.warning(
                    "marketdata_alerts suppressed isin=%s reason=%s pct=%.2f delta=%.2f group=%s",
                    isin,
                    suppress_reason or "below_min_delta",
                    current_pct,
                    delta_pct,
                    group,
                )
            continue

        if int(counters.get("marketdata", 0)) >= max_per_day:
            reason_counts["max_per_day_reached"] += 1
            continue

        last_ts = _parse_iso(prev.get("last_sent_ts"))
        if last_ts and now - last_ts < cooldown:
            reason_counts["cooldown_active"] += 1
            continue

        trigger_text = "+".join(triggers)
        message = (
            f"PortWächter Marketdata: {quote.get('name')} ({isin}) {current_pct:+.2f}% "
            f"| Δ={delta_pct:+.2f}% | Trigger: {trigger_text} | Gruppe: {group}"
        )[:msg_max_len]

        alert = {
            "created_at": quote.get("fetched_at") or now_iso_tz(),
            "alert_id": "INTRADAY_MOVE_UP" if direction == "up" else "INTRADAY_MOVE_DOWN" if direction == "down" else "INTRADAY_MOVE_FLAT",
            "isin": isin,
            "name": quote.get("name"),
            "symbol": quote.get("symbol"),
            "group": group,
            "move_pct": current_pct,
            "delta_pct": delta_pct,
            "open": open_price,
            "last": close_price,
            "trigger": trigger_text,
            "thresholds": {
                "effective_min_delta": thresholds["effective_min_delta"],
                "effective_min_direction": thresholds["effective_min_direction"],
                "threshold_pct": thresholds["threshold_pct"],
                "adaptive_floor": thresholds["adaptive_floor"],
            },
            "message": message,
        }
        alerts.append(alert)

        counters["marketdata"] = int(counters.get("marketdata", 0)) + 1
        md_state[isin] = {
            "last_sent_ts": now.isoformat(),
            "last_pct": current_pct,
            "last_dir": direction,
            "last_threshold": abs(current_pct) >= float(thresholds["threshold_pct"]),
        }

    if alerts:
        out_path = Path(out_alerts_path)
        ensure_dir(out_path.parent)
        for alert in alerts:
            append_jsonl(out_path, alert)

    save_alert_state(_state_path(cfg), state)
    _log_summary(evaluated, len(alerts), reason_counts)
    return alerts
