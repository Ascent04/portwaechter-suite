from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from modules.common.utils import append_jsonl, ensure_dir


def _day_file(cfg: dict, day: str | None = None) -> Path:
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    stamp = day or datetime.now().strftime("%Y%m%d")
    return root / "data" / "performance" / f"outcomes_{stamp}.jsonl"


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
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


def _id_value(row: dict) -> str:
    return str(row.get("signal_id") or row.get("setup_id") or "")


def dedupe_outcomes(event_id: str, ts_eval_day: str, cfg: dict) -> bool:
    file = _day_file(cfg, ts_eval_day.replace("-", ""))
    for row in _read_jsonl(file):
        if _id_value(row) == event_id:
            return True
    return False


def append_outcome(outcome: dict, cfg: dict) -> Path:
    ts_eval = str(outcome.get("ts_eval") or "")
    day = ts_eval[:10].replace("-", "") if len(ts_eval) >= 10 else None
    path = _day_file(cfg, day)
    ensure_dir(path.parent)
    append_jsonl(path, outcome)
    return path
