#!/usr/bin/env bash
# Pack local SQLite + models (+ evaluation) into deploy/seed for the Docker image.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$ROOT/backend"
SEED="$ROOT/deploy/seed"
DB="$BACKEND/data/stockpilot.db"
MODELS="$BACKEND/artifacts/models"
EVAL="$BACKEND/artifacts/evaluation"

if [[ ! -f "$DB" ]]; then
  echo "Missing $DB — run ./scripts/bootstrap.sh first." >&2
  exit 1
fi
if [[ ! -d "$MODELS" ]]; then
  echo "Missing $MODELS — bootstrap/train did not write model artifacts." >&2
  exit 1
fi

find "$SEED" -mindepth 1 ! -name '.gitkeep' -exec rm -rf {} + 2>/dev/null || true
mkdir -p "$SEED"
cp -a "$DB" "$SEED/stockpilot.db"
cp -a "$MODELS" "$SEED/models"
if [[ -d "$EVAL" ]]; then
  cp -a "$EVAL" "$SEED/evaluation"
fi

du -sh "$SEED"
echo "Seed ready. Next: docker compose build"
