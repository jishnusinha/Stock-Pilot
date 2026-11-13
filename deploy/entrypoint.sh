#!/bin/sh
set -eu

mkdir -p /data/models

if [ ! -f /data/stockpilot.db ]; then
  echo "First start: seeding demo data and training models (this can take several minutes)..."
  python -m app.cli bootstrap --products 200 --days 365 --seed 42 --threads 2 --fast
  python -m app.cli build-analytics --seed 42
  echo "Bootstrap complete."
fi

nginx
exec uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
