from __future__ import annotations

import argparse

from modules.common.config import load_config
from modules.decision_engine.engine import run as run_engine


def run() -> dict:
    cfg = load_config()
    return run_engine(cfg)


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Decision queue runner")
    parser.add_argument("command", choices=["run"])
    args = parser.parse_args()
    if args.command == "run":
        run()


if __name__ == "__main__":
    _cli()
