"""Integration tests for /metrics, X-Request-ID, and enhanced /health."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import Result

from geohealth.api.dependencies import get_db
from geohealth.api.main import app
from geohealth.services.metrics import metrics


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_db_session():
    """Return an AsyncMock that passes the health-check SELECT 1."""
    session = AsyncMock()
    result = AsyncMock(spec=Result)
    session.execute.return_value = result
    return session


# ---------------------------------------------------------------------------
# /metrics endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_metrics_endpoint_structure(client):
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_requests" in data
    assert "cache" in data
    assert "hits" in data["cache"]
    assert "rate_limiter" in data
    assert "latency_ms" in data
    assert "p50" in data["latency_ms"]
    assert "uptime_seconds" in data


# ---------------------------------------------------------------------------
# X-Request-ID header
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_request_id_generated(client):
    resp = await client.get("/metrics")
    rid = resp.headers.get("x-request-id")
    assert rid is not None
    assert len(rid) == 32  # uuid4 hex


@pytest.mark.asyncio
async def test_request_id_echoed(client):
    resp = await client.get("/metrics", headers={"x-request-id": "my-custom-id-123"})
    assert resp.headers.get("x-request-id") == "my-custom-id-123"


# ---------------------------------------------------------------------------
# Enhanced /health
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_includes_subsystems(client):
    session = _mock_db_session()
    app.dependency_overrides[get_db] = lambda: session
    try:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "cache" in data
        assert "size" in data["cache"]
        assert "max_size" in data["cache"]
        assert "hit_rate" in data["cache"]
        assert "rate_limiter" in data
        assert "active_keys" in data["rate_limiter"]
        assert "uptime_seconds" in data
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Middleware increments metrics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_middleware_increments_metrics(client):
    before = metrics.total_requests
    await client.get("/metrics")
    assert metrics.total_requests == before + 1
