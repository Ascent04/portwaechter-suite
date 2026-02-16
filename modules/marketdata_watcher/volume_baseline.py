from __future__ import annotations

from pathlib import Path

from modules.common.utils import ensure_dir, now_iso_tz, read_json, write_json


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return float((ordered[mid - 1] + ordered[mid]) / 2)


def load_volume_baseline(path: str | Path) -> dict:
    file_path = Path(path)
    if not file_path.exists():
        return {}

    try:
        data = read_json(file_path)
    except Exception:
        return {}

    return data if isinstance(data, dict) else {}


def save_volume_baseline(path: str | Path, baseline: dict) -> None:
    file_path = Path(path)
    ensure_dir(file_path.parent)
    write_json(file_path, baseline)


def update_volume_baseline(
    baseline: dict,
    isin: str,
    volume: float | int | None,
    max_points: int = 200,
) -> None:
    if not isin or volume is None:
        return

    try:
        volume_value = float(volume)
    except (TypeError, ValueError):
        return

    if volume_value <= 0:
        return

    current = baseline.get(isin, {}) if isinstance(baseline.get(isin), dict) else {}
    volumes = list(current.get("volumes_last_n", []))
    volumes.append(volume_value)
    if len(volumes) > max_points:
        volumes = volumes[-max_points:]

    baseline[isin] = {
        "volumes_last_n": volumes,
        "count": len(volumes),
        "median_rolling": round(_median(volumes), 2),
        "updated_at": now_iso_tz(),
    }
