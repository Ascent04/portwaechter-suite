from __future__ import annotations

from pathlib import Path
from statistics import median

from modules.common.utils import read_json


def load_volume_baseline(path: str | Path) -> dict:
    file = Path(path)
    if not file.exists():
        return {}
    try:
        data = read_json(file)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _baseline_median(row: dict) -> tuple[float | None, int]:
    if "median_rolling" in row:
        med = row.get("median_rolling")
        count = int(row.get("count") or 0)
        return (float(med), count) if med not in (None, 0) else (None, count)

    values = row.get("volumes_last_n", [])
    vals = [float(v) for v in values if v is not None]
    if not vals:
        return None, 0
    return float(median(vals)), len(vals)


def compute_volume_light(isin: str, latest_volume: float | None, baseline: dict, thresholds: dict) -> dict:
    green_ratio = float(thresholds.get("green_ratio", 2.0))
    yellow_ratio = float(thresholds.get("yellow_ratio", 1.3))
    min_points = int(thresholds.get("min_volume_points", 20))

    if latest_volume is None:
        return {"isin": isin, "light": "gray", "ratio": None, "reason": "unavailable"}

    row = baseline.get(isin, {})
    med, count = _baseline_median(row if isinstance(row, dict) else {})
    if med is None or med <= 0 or count < min_points:
        return {"isin": isin, "light": "gray", "ratio": None, "reason": "unavailable"}

    ratio = round(float(latest_volume) / med, 2)
    if ratio >= green_ratio:
        return {"isin": isin, "light": "green", "ratio": ratio, "reason": "spike"}
    if ratio >= yellow_ratio:
        return {"isin": isin, "light": "yellow", "ratio": ratio, "reason": "normal"}
    return {"isin": isin, "light": "red", "ratio": ratio, "reason": "normal"}


def compute_volume_lights_for_holdings(positions: list[dict], quotes: dict, baseline: dict, thresholds: dict) -> list[dict]:
    result = []
    for pos in positions:
        isin = str(pos.get("isin") or "")
        latest_row = quotes.get(isin, {})
        vol = latest_row.get("volume")
        item = compute_volume_light(isin, float(vol) if vol not in (None, "") else None, baseline, thresholds)
        item["name"] = pos.get("name")
        result.append(item)
    return result
