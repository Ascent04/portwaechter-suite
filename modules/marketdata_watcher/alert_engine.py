from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from modules.alerts.state import load_alert_state, save_alert_state
from modules.common.utils import append_jsonl, ensure_dir, now_iso_tz


def _read_jsonl(path: str | Path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    rows = []
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


def _state_path(cfg: dict, out_alerts_path: str | Path) -> str:
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


def _direction(pct: float) -> str:
    if pct > 0:
        return "up"
    if pct < 0:
        return "down"
    return "flat"


def _trigger_flags(cur: float, last: dict, cfg: dict) -> tuple[list[str], bool]:
    mcfg = cfg.get("marketdata_alerts", {})
    min_delta = float(mcfg.get("min_delta_pct", 0.5))
    threshold = float(mcfg.get("threshold_pct", 5.0))

    cur_dir = _direction(cur)
    cur_th = abs(cur) >= threshold

    last_pct = last.get("last_pct")
    last_dir = str(last.get("last_dir", "flat"))
    last_th = bool(last.get("last_threshold", False))

    triggers = []
    if mcfg.get("send_on_delta", True) and last_pct is not None and abs(cur - float(last_pct)) >= min_delta and cur != float(last_pct):
        triggers.append("delta")
    if mcfg.get("send_on_direction_change", True) and last_pct is not None and cur_dir != last_dir:
        triggers.append("direction")
    if mcfg.get("send_on_threshold_cross", True) and last_pct is not None and cur_th != last_th:
        triggers.append("threshold_cross")

    if last_pct is None and cur_th:
        triggers.append("initial_threshold")

    return triggers, cur_th


def detect_intraday_moves(quotes_jsonl_path: str | Path, out_alerts_path: str | Path, cfg: dict) -> list[dict]:
    mcfg = cfg.get("marketdata_alerts", {})
    if not mcfg.get("enabled", True):
        return []

    state = load_alert_state(_state_path(cfg, out_alerts_path))
    md_state = state.setdefault("marketdata", {})
    counters = state.setdefault("counters", {"watch": 0, "marketdata": 0})

    quotes = _read_jsonl(quotes_jsonl_path)
    cooldown = timedelta(minutes=int(mcfg.get("cooldown_minutes_per_isin", 120)))
    max_per_day = int(mcfg.get("max_per_day", 10))
    now = datetime.fromisoformat(now_iso_tz(cfg.get("app", {}).get("timezone", "Europe/Berlin")))

    alerts: list[dict] = []
    for quote in quotes:
        if quote.get("status") != "ok":
            continue
        isin = str(quote.get("isin") or "")
        open_price = quote.get("open")
        close_price = quote.get("close")
        if not isin or not open_price or not close_price:
            continue

        cur = round(((close_price - open_price) / open_price) * 100.0, 2)
        cur_dir = _direction(cur)
        prev = md_state.get(isin, {}) if isinstance(md_state.get(isin), dict) else {}

        triggers, cur_th = _trigger_flags(cur, prev, cfg)
        should = bool(triggers)

        if should and int(counters.get("marketdata", 0)) >= max_per_day:
            should = False

        if should:
            last_ts = _parse_iso(prev.get("last_sent_ts"))
            if last_ts and now - last_ts < cooldown:
                should = False

        if should:
            alert = {
                "created_at": quote.get("fetched_at") or now_iso_tz(),
                "alert_id": "INTRADAY_MOVE_UP" if cur_dir == "up" else "INTRADAY_MOVE_DOWN" if cur_dir == "down" else "INTRADAY_MOVE_FLAT",
                "isin": isin,
                "name": quote.get("name"),
                "symbol": quote.get("symbol"),
                "move_pct": cur,
                "open": open_price,
                "last": close_price,
                "trigger": "+".join(triggers),
                "message": f"PortWächter Marketdata: {quote.get('name')} ({isin}) {cur:+.2f}% | Trigger: {'+'.join(triggers)}",
            }
            alerts.append(alert)
            counters["marketdata"] = int(counters.get("marketdata", 0)) + 1
            prev["last_sent_ts"] = now.isoformat()
            prev["last_pct"] = cur
            prev["last_dir"] = cur_dir
            prev["last_threshold"] = cur_th
        else:
            prev["last_pct"] = cur
            prev["last_dir"] = cur_dir
            prev["last_threshold"] = cur_th

        md_state[isin] = prev

    if alerts:
        out_path = Path(out_alerts_path)
        ensure_dir(out_path.parent)
        for alert in alerts:
            append_jsonl(out_path, alert)

    save_alert_state(_state_path(cfg, out_alerts_path), state)
    return alerts
