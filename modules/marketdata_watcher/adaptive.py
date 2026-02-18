from __future__ import annotations

import json
from datetime import date
from pathlib import Path


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
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


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _iter_quote_files(root: Path, today: date | None = None) -> list[Path]:
    files = sorted((root / "data" / "marketdata").glob("quotes_*.jsonl"), reverse=True)
    if today is None:
        return files

    tag = today.strftime("%Y%m%d")
    return [f for f in files if f.stem.split("_", 1)[-1] <= tag]


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def load_recent_quotes(cfg: dict, isin: str, date_today: date | None = None) -> list[float]:
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    ad_cfg = cfg.get("marketdata_alerts", {}).get("adaptive", {})
    lookback = int(ad_cfg.get("lookback_points", 20))

    if not isin:
        return []

    points: list[float] = []
    for file in _iter_quote_files(root, date_today):
        for row in _read_jsonl(file):
            if row.get("status") != "ok" or str(row.get("isin") or "") != isin:
                continue

            open_price = _to_float(row.get("open"))
            close_price = _to_float(row.get("close"))
            prev_close = _to_float(row.get("prev_close"))

            pct = None
            if open_price and close_price and open_price != 0:
                pct = ((close_price - open_price) / open_price) * 100.0
            elif prev_close and close_price and prev_close != 0:
                pct = ((close_price - prev_close) / prev_close) * 100.0

            if pct is None:
                continue
            points.append(float(pct))
            if len(points) >= lookback:
                return points

    return points


def compute_adaptive_floor(
    pcts: list[float],
    k_multiplier: float = 1.2,
    min_floor_pct: float = 0.6,
    max_floor_pct: float = 2.5,
) -> float:
    if not pcts:
        return float(min_floor_pct)

    abs_vals = [abs(float(v)) for v in pcts]
    med = _median(abs_vals)
    floor = med * float(k_multiplier)
    floor = max(float(min_floor_pct), floor)
    floor = min(float(max_floor_pct), floor)
    return round(float(floor), 4)
