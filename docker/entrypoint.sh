#!/bin/sh
# Production entrypoint for the AgentGuard API container.
#
# 1. Runs Alembic migrations when the Postgres store is enabled, so the
#    schema is always current before the app serves traffic.
# 2. Starts uvicorn with multiple workers (POST /runs is synchronous; more
#    workers = more concurrent evaluations). Tune via UVICORN_WORKERS.
set -e

if [ "${USE_POSTGRES:-true}" = "true" ]; then
    echo "[entrypoint] Running database migrations..."
    alembic upgrade head
    echo "[entrypoint] Migrations complete."
else
    echo "[entrypoint] USE_POSTGRES != true; skipping migrations (in-memory store)."
fi

WORKERS="${UVICORN_WORKERS:-2}"
# Render (and most PaaS hosts) assigns the port via $PORT; default to 8000 locally.
APP_PORT="${PORT:-8000}"
echo "[entrypoint] Starting API with ${WORKERS} worker(s) on port ${APP_PORT}..."
exec uvicorn src.api.app:app --host 0.0.0.0 --port "${APP_PORT}" --workers "${WORKERS}"
