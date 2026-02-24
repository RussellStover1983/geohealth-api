# ---------------------------------------------------------------------------
# Stage 1: Builder — install dependencies into an isolated virtualenv
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS builder

RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq-dev gcc && \
    rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Install dependencies first (layer caching)
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application code and reinstall (picks up the app package)
COPY geohealth/ geohealth/
COPY alembic.ini .
RUN pip install --no-cache-dir .

# ---------------------------------------------------------------------------
# Stage 2: Runtime — minimal image with only what's needed to run
# ---------------------------------------------------------------------------
FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 curl && \
    rm -rf /var/lib/apt/lists/*

RUN useradd --create-home appuser

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY --from=builder /app/geohealth/ geohealth/
COPY --from=builder /app/alembic.ini .

USER appuser

EXPOSE 8000

CMD gunicorn geohealth.api.main:app \
    --bind "0.0.0.0:${PORT:-8000}" \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 2 \
    --timeout 120 \
    --graceful-timeout 30 \
    --access-logfile -
