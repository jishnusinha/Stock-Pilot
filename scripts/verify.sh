#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pytest -q
python -m app.cli model-status
cd "$ROOT/frontend"
npm run build
if curl -fsS "http://127.0.0.1:8000/api/health" >/tmp/sp_health.json 2>/dev/null; then
  cat /tmp/sp_health.json
else
  echo "API not running (skip). Start with ./scripts/start-api.sh"
fi
echo "verify OK"
