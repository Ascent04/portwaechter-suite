from __future__ import annotations

import argparse
import json
from pathlib import Path

from modules.common.config import load_config
from modules.setup_engine.planner import build_setup, enqueue_setup_for_approval, handle_approval_command, notify_setup


def _latest(path: Path, pattern: str) -> Path | None:
    files = sorted(path.glob(pattern))
    return files[-1] if files else None


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _latest_quotes_by_isin(root: Path) -> dict:
    path = _latest(root / "data" / "marketdata", "quotes_*.jsonl")
    rows = _read_jsonl(path) if path else []
    out = {}
    for row in rows:
        isin = str(row.get("isin") or "")
        if isin and row.get("status") == "ok":
            out[isin] = row
    return out


def run(cfg: dict) -> list[dict]:
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    queue_path = _latest(root / "data" / "decisions", "decision_queue_*.json")
    if not queue_path:
        return []

    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    max_setups = int(cfg.get("decision", {}).get("max_setups_per_day", 2))
    setups = [c for c in queue.get("candidates", []) if c.get("bucket") == "SETUP"][:max_setups]

    quotes = _latest_quotes_by_isin(root)
    created = []
    for candidate in setups:
        setup = build_setup(candidate, quotes.get(str(candidate.get("isin")), {}), cfg)
        enqueue_setup_for_approval(setup, cfg)
        notify_setup(setup, cfg)
        created.append(setup)
    return created


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Setup prep runner")
    parser.add_argument("command", choices=["run", "handle"])
    parser.add_argument("--message", default="")
    args = parser.parse_args()

    cfg = load_config()
    if args.command == "run":
        run(cfg)
    elif args.command == "handle":
        handle_approval_command(args.message, cfg)


if __name__ == "__main__":
    _cli()
