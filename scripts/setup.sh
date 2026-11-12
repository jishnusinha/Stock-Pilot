#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo "StockPilot setup (Unix)"
python3 --version
node --version
npm --version
cd "$ROOT/backend"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
pip install --no-cache-dir -r requirements.txt
cd "$ROOT/frontend"
npm install
echo "Next: ./scripts/bootstrap.sh then start-api.sh and start-ui.sh"
