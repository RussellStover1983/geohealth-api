# NPPES tract-level ETL v2
FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

RUN useradd --create-home appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/

USER appuser

EXPOSE 8001

CMD exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port ${PORT:-8001} \
    --workers 2
