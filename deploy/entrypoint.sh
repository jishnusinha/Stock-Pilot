#!/bin/sh
set -eu

mkdir -p /data/models /data/evaluation

# Prefer a pre-trained seed (baked into image or bind-mounted at /seed).
# Layout expected under /seed:
#   stockpilot.db
#   models/   (joblib agents)
#   evaluation/  (optional JSON metrics)
if [ ! -f /data/stockpilot.db ] && [ -f /seed/stockpilot.db ]; then
  echo "Loading pre-trained seed from /seed (no training on this host)..."
  cp -a /seed/stockpilot.db /data/stockpilot.db
  if [ -d /seed/models ]; then
    rm -rf /data/models
    cp -a /seed/models /data/models
  fi
  if [ -d /seed/evaluation ]; then
    rm -rf /data/evaluation
    cp -a /seed/evaluation /data/evaluation
  fi
  echo "Seed loaded."
fi

PRODUCTS="${STOCKPILOT_BOOTSTRAP_PRODUCTS:-50}"
DAYS="${STOCKPILOT_BOOTSTRAP_DAYS:-90}"
SEED="${STOCKPILOT_SEED:-42}"
THREADS="${STOCKPILOT_THREADS:-1}"
FAST_FLAG=""
case "${STOCKPILOT_BOOTSTRAP_FAST:-true}" in
  1|true|yes|TRUE|YES) FAST_FLAG="--fast" ;;
esac

# Only train on the server when neither volume data nor /seed is present.
if [ ! -f /data/stockpilot.db ]; then
  echo "No seed found — bootstrap products=${PRODUCTS} days=${DAYS} threads=${THREADS} ${FAST_FLAG}..."
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
