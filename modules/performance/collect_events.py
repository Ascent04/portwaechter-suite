from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path


def _to_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
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


def load_events(date_from: str | date, date_to: str | date, cfg: dict) -> list[dict]:
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    perf_dir = root / "data" / "performance"

    start = _to_date(date_from)
    end = _to_date(date_to)
    if end < start:
        start, end = end, start

    rows: list[dict] = []
    current = start
    while current <= end:
        path = perf_dir / f"events_{current.strftime('%Y%m%d')}.jsonl"
        rows.extend(_read_jsonl(path))
        current += timedelta(days=1)
    return rows
