#!/bin/sh
set -eu

mkdir -p /data/models

PRODUCTS="${STOCKPILOT_BOOTSTRAP_PRODUCTS:-50}"
DAYS="${STOCKPILOT_BOOTSTRAP_DAYS:-90}"
SEED="${STOCKPILOT_SEED:-42}"
THREADS="${STOCKPILOT_THREADS:-1}"
FAST_FLAG=""
case "${STOCKPILOT_BOOTSTRAP_FAST:-true}" in
  1|true|yes|TRUE|YES) FAST_FLAG="--fast" ;;
esac

if [ ! -f /data/stockpilot.db ]; then
  echo "First start: bootstrap products=${PRODUCTS} days=${DAYS} threads=${THREADS} ${FAST_FLAG}..."
  # shellcheck disable=SC2086
  python -m app.cli bootstrap \
    --products "${PRODUCTS}" \
    --days "${DAYS}" \
    --seed "${SEED}" \
    --threads "${THREADS}" \
    ${FAST_FLAG}
  python -m app.cli build-analytics --seed "${SEED}"
  echo "Bootstrap complete."
fi

nginx
exec uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
