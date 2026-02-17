#!/usr/bin/env bash
set -euo pipefail

echo "=== FAILED UNITS ==="
systemctl --no-pager --failed || true
echo

echo "=== TIMERS ==="
systemctl list-timers --no-pager | grep -i portwaechter || true
echo

for u in portwaechter-portfolio.service portwaechter-marketdata.service portwaechter-news.service; do
  echo "=== $u (last 30 lines) ==="
  journalctl -u "$u" -n 30 --no-pager || true
  echo
done

echo "=== HEALTH ==="
/opt/portwaechter/.venv/bin/python -m modules.health.report --pretty | head -n 200
