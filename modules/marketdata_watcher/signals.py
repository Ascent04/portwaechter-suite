from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from modules.common.utils import append_jsonl, ensure_dir, now_iso_tz


MOVE_THRESHOLD_PCT = 2.0


def _read_jsonl(path: str | Path) -> list[dict]:
    file_path = Path(path)
    if not file_path.exists():
        return []

    records = []
    with file_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def detect_intraday_moves(quotes_jsonl_path: str | Path, out_alerts_path: str | Path, cooldown_min: int) -> list[dict]:
    quotes = _read_jsonl(quotes_jsonl_path)
    existing_alerts = _read_jsonl(out_alerts_path)

    last_alert_by_isin: dict[str, datetime] = {}
    for alert in existing_alerts:
        isin = alert.get("isin")
        created_at = _parse_ts(alert.get("created_at"))
        if isin and created_at:
            current = last_alert_by_isin.get(isin)
            if current is None or created_at > current:
                last_alert_by_isin[isin] = created_at

    cooldown = timedelta(minutes=cooldown_min)
    alerts: list[dict] = []

    for quote in quotes:
        if quote.get("status") != "ok":
            continue

        open_price = quote.get("open")
        close_price = quote.get("close")
        if not open_price or not close_price:
            continue

        move_pct = ((close_price - open_price) / open_price) * 100
        if abs(move_pct) < MOVE_THRESHOLD_PCT:
            continue

        isin = quote.get("isin")
        event_time = _parse_ts(quote.get("fetched_at")) or datetime.fromisoformat(now_iso_tz())
        last_event = last_alert_by_isin.get(isin)
        if isin and last_event and event_time - last_event < cooldown:
            continue

        alert = {
            "created_at": quote.get("fetched_at") or now_iso_tz(),
            "alert_id": "INTRADAY_MOVE_UP" if move_pct >= 0 else "INTRADAY_MOVE_DOWN",
            "isin": isin,
            "name": quote.get("name"),
            "symbol": quote.get("symbol"),
            "move_pct": round(move_pct, 2),
            "open": open_price,
            "last": close_price,
        }
        alerts.append(alert)
        if isin:
            last_alert_by_isin[isin] = event_time

    if alerts:
        out_path = Path(out_alerts_path)
        ensure_dir(out_path.parent)
        for alert in alerts:
            append_jsonl(out_path, alert)

    return alerts
