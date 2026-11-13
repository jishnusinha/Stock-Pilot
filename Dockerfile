# --- frontend build ---
FROM node:24-bookworm-slim AS ui
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Empty = same-origin /api (nginx proxies to FastAPI)
ENV VITE_API_URL=
RUN npm run build

# --- runtime: nginx + FastAPI ---
FROM python:3.12-slim-bookworm
RUN apt-get update \
 && apt-get install -y --no-install-recommends nginx \
 && rm -rf /var/lib/apt/lists/* \
 && rm -f /etc/nginx/sites-enabled/default

WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend /app/backend
COPY --from=ui /src/frontend/dist /usr/share/nginx/html
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY deploy/entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

WORKDIR /app/backend
# Defaults sized for AWS free-tier t2/t3.micro (~1 GB). Prefer shipping /seed
# from a local bootstrap so the micro never trains.
ENV STOCKPILOT_THREADS=1 \
    STOCKPILOT_BOOTSTRAP_PRODUCTS=50 \
    STOCKPILOT_BOOTSTRAP_DAYS=90 \
    STOCKPILOT_BOOTSTRAP_FAST=true \
    STOCKPILOT_DB_PATH=/data/stockpilot.db \
    STOCKPILOT_MODEL_DIR=/data/models \
    STOCKPILOT_EVAL_DIR=/data/evaluation \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1

# Optional pre-trained artifacts: run scripts/export-docker-seed.ps1 first, then rebuild.
# If deploy/seed/stockpilot.db is missing, the empty dir is still copied and
# entrypoint falls back to in-container bootstrap.
COPY deploy/seed /seed

EXPOSE 80
VOLUME ["/data"]
ENTRYPOINT ["/entrypoint.sh"]
