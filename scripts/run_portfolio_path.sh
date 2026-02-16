#!/usr/bin/env bash
set -euo pipefail

ROOT="/opt/portwaechter"
INBOX="$ROOT/data/inbox"
PROCESSED="$ROOT/data/raw/processed_inbox"

mkdir -p "$PROCESSED"

# Wenn keine PDFs da sind: Exit 0 (kein Fehler)
shopt -s nullglob
pdfs_before=("$INBOX"/*.pdf)
shopt -u nullglob
if (( ${#pdfs_before[@]} == 0 )); then
  exit 0
fi

cd "$ROOT"

# Run Portfolio ingest (kann intern kopieren/umbenennen)
"$ROOT/.venv/bin/python" -m modules.portfolio_ingest.main run

# Nach Erfolg: Inbox leeren (alles was noch .pdf ist, verschieben)
shopt -s nullglob
pdfs_after=("$INBOX"/*.pdf)
shopt -u nullglob

if (( ${#pdfs_after[@]} == 0 )); then
  exit 0
fi

ts="$(date +%Y%m%d_%H%M%S)"
for f in "${pdfs_after[@]}"; do
  base="$(basename "$f" .pdf)"
  mv -f "$f" "$PROCESSED/${base}_${ts}.pdf"
done
