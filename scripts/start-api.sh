#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"
# shellcheck disable=SC1091
source .venv/bin/activate
export OMP_NUM_THREADS=2
exec python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
