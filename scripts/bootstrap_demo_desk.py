#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.common.demo_seed import bootstrap_demo_runtime, default_demo_root


def main() -> int:
    parser = argparse.ArgumentParser(description="Erzeugt getrennte Demo-/Seed-Daten fuer lokale Desk-Trockenlaeufe.")
    parser.add_argument("--target-root", default=str(default_demo_root()), help="Getrennte Demo-Root. Darf nicht das Repo-Root sein.")
    parser.add_argument("--period", default=None, help="Monatsperiode fuer den Demo-Report, z. B. 2026-03.")
    parser.add_argument("--clean", action="store_true", help="Bestehende Demo-Root vor dem Schreiben loeschen.")
    args = parser.parse_args()

    result = bootstrap_demo_runtime(Path(args.target_root), clean=bool(args.clean), period=args.period)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
