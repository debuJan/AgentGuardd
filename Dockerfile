FROM python:3.10-slim-bookworm

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY configs ./configs

# Alembic migrations (run by the entrypoint before the API starts).
COPY alembic.ini ./
COPY migrations ./migrations

# Production entrypoint: runs migrations, then starts uvicorn with workers.
COPY docker/entrypoint.sh /usr/local/bin/agentguard-entrypoint.sh
RUN chmod +x /usr/local/bin/agentguard-entrypoint.sh

# Run as a non-root user (least privilege inside the container).
RUN useradd --create-home --uid 10001 agentguard \
    && chown -R agentguard:agentguard /app
USER agentguard

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import sys, urllib.request; \
        sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status == 200 else 1)"

ENTRYPOINT ["agentguard-entrypoint.sh"]
