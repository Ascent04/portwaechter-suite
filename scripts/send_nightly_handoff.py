#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.common.config import load_config
from modules.telegram_commands.nightly_handoff import notify_nightly_handoff


def main() -> int:
    parser = argparse.ArgumentParser(description="Sendet den finalen NIGHTLY_HANDOFF-Status ueber den aktiven Telegram-Pfad.")
    parser.add_argument("--force", action="store_true", help="Dedupe fuer den aktuellen Handoff-Stand ignorieren.")
    args = parser.parse_args()

    result = notify_nightly_handoff(load_config(), force=bool(args.force))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("status") in {"sent", "dedupe_skip"}:
        return 0
    if result.get("status") == "skipped_not_ready":
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
