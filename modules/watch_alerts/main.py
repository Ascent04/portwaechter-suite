from __future__ import annotations

import argparse

from modules.common.config import load_config
from modules.watch_alerts.engine import run


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Watch alerts runner")
    parser.add_argument("command", choices=["run"])
    args = parser.parse_args()
    if args.command == "run":
        run(load_config())


if __name__ == "__main__":
    _cli()
