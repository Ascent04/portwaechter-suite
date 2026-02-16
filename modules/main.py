from __future__ import annotations

import argparse

from modules.app_router import run_mode
from modules.common.config import load_config


def run() -> None:
    cfg = load_config()
    run_mode(cfg)


def _cli() -> None:
    parser = argparse.ArgumentParser(description="PortWächter mode runner")
    parser.add_argument("command", choices=["run"])
    args = parser.parse_args()

    if args.command == "run":
        run()


if __name__ == "__main__":
    _cli()
