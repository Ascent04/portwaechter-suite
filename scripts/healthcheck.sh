#!/usr/bin/env bash
set -euo pipefail

ROOT="/opt/portwaechter"
PY="$ROOT/.venv/bin/python"
ENV_FILE="/etc/portwaechter/portwaechter.env"

if [[ ! -x "$PY" ]]; then
  echo "ERROR: missing interpreter at $PY"
  exit 2
fi

echo "== PortWächter Healthcheck =="
echo "root=$ROOT"
echo "python=$($PY -c 'import sys; print(sys.executable)')"

if [[ -r "$ENV_FILE" ]]; then
  set -a
  # shellcheck source=/etc/portwaechter/portwaechter.env
  source "$ENV_FILE"
  set +a
fi

tmp_report="$(mktemp)"
trap 'rm -f "$tmp_report"' EXIT

"$PY" -m modules.health.report > "$tmp_report"

status="$($PY - <<'PY' "$tmp_report"
import json, sys
p = sys.argv[1]
r = json.load(open(p, 'r', encoding='utf-8'))
print(r.get('overall_status', 'failed'))
PY
)"

echo "overall_status=$status"
"$PY" - <<'PY' "$tmp_report"
import json, sys
r = json.load(open(sys.argv[1], 'r', encoding='utf-8'))
for k, v in r.get('checks', {}).items():
    print(f"{k}={v}")
PY

if [[ "$status" == "ok" ]]; then
  exit 0
fi
exit 1
