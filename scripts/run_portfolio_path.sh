#!/usr/bin/env bash
set -euo pipefail

ROOT="/opt/portwaechter"
INBOX="$ROOT/data/inbox"
PROCESSED="$ROOT/data/raw/processed_inbox"
LOCKFILE="$ROOT/data/cache/portfolio_path.lock"

mkdir -p "$PROCESSED" "$(dirname "$LOCKFILE")"

exec 9>"$LOCKFILE"
if ! flock -n 9; then
  exit 0
fi

PDF="$(ls -t "$INBOX"/*.pdf 2>/dev/null | head -n 1 || true)"
if [[ -z "${PDF}" ]]; then
  exit 0
fi

cd "$ROOT"
"$ROOT/.venv/bin/python" -m modules.portfolio_ingest.main run

# Collector already consumes the inbox file; fallback move is for backward compatibility.
if [[ -f "$PDF" ]]; then
  ts="$(date +%Y%m%d_%H%M%S)"
  mv -f "$PDF" "$PROCESSED/$(basename "$PDF" .pdf)_$ts.pdf"
fi
