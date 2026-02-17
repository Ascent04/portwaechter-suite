from __future__ import annotations

from datetime import datetime


def _parse_date(ts: str) -> str | None:
    try:
        return datetime.fromisoformat(ts).date().isoformat()
    except ValueError:
        return None


def _find_base_index(series: list[dict], event_day: str) -> int | None:
    for idx, row in enumerate(series):
        if str(row.get("date")) >= event_day:
            return idx
    return None


def _ret(direction: str, p0: float, p1: float) -> float | None:
    if p0 == 0:
        return None
    if direction == "down":
        return round(((p0 - p1) / p0) * 100, 4)
    return round(((p1 - p0) / p0) * 100, 4)


def compute_forward_returns_for_event(event: dict, quotes_index: dict, horizons: list[int] | None = None) -> dict:
    hz = horizons or [1, 3, 5]
    out = {}

    isin = str(event.get("isin") or "")
    event_day = _parse_date(str(event.get("ts") or ""))
    series = quotes_index.get(isin, [])

    if not event_day or not series:
        for h in hz:
            out[f"{h}d"] = {"status": "unavailable", "r_pct": None, "p0": None, "p1": None, "asof": None}
        return out

    base_idx = _find_base_index(series, event_day)
    if base_idx is None:
        for h in hz:
            out[f"{h}d"] = {"status": "unavailable", "r_pct": None, "p0": None, "p1": None, "asof": None}
        return out

    p0 = series[base_idx].get("close")
    for h in hz:
        key = f"{h}d"
        target = base_idx + h
        if p0 in (None, 0) or target >= len(series):
            out[key] = {"status": "unavailable", "r_pct": None, "p0": p0, "p1": None, "asof": None}
            continue
        p1 = series[target].get("close")
        if p1 is None:
            out[key] = {"status": "unavailable", "r_pct": None, "p0": p0, "p1": None, "asof": None}
            continue
        r = _ret(str(event.get("direction", "up")), float(p0), float(p1))
        if r is None:
            out[key] = {"status": "unavailable", "r_pct": None, "p0": p0, "p1": p1, "asof": series[target].get("date")}
            continue
        out[key] = {"status": "ok", "r_pct": r, "p0": p0, "p1": p1, "asof": series[target].get("date")}
    return out
