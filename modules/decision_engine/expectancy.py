from __future__ import annotations

from pathlib import Path

from modules.common.utils import read_json


def _latest(path: Path, pattern: str) -> Path | None:
    files = sorted(path.glob(pattern))
    return files[-1] if files else None


def _to_int(value: object, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def load_latest_expectancy(cfg: dict) -> dict:
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    report = _latest(root / "data" / "performance" / "reports", "weekly_*.json")
    if not report:
        return {}
    data = read_json(report)
    return data if isinstance(data, dict) else {}


def _pick_bucket(score_cal: dict, factor_score: float) -> dict:
    picks = []
    for key, value in score_cal.items():
        if not key.startswith("factor_score>="):
            continue
        try:
            threshold = float(key.split(">=", 1)[1])
        except ValueError:
            continue
        if factor_score >= threshold:
            picks.append((threshold, value))
    if not picks:
        return {}
    return sorted(picks, key=lambda x: x[0])[-1][1]


def attach_expectancy(candidates: list[dict], cfg: dict) -> list[dict]:
    report = load_latest_expectancy(cfg)
    score_cal = report.get("score_calibration", {}) if isinstance(report, dict) else {}

    for row in candidates:
        factor_score = float(row.get("signal_factor_score", 0))
        bucket = _pick_bucket(score_cal, factor_score)
        h3 = (bucket.get("3d") if isinstance(bucket, dict) else {}) or {}

        row["expectancy_3d"] = h3.get("expectancy")
        row["expectancy_confidence"] = h3.get("expectancy_confidence", "unavailable")
        row["expectancy_n"] = _to_int(h3.get("n"), 0)
    return candidates
