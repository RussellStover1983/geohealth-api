"""Tests for global exception handlers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from geohealth.api.main import app


@pytest.mark.asyncio
async def test_404_returns_structured_json(client):
    """GET /nonexistent -> structured JSON 404, not HTML."""
    resp = await client.get("/nonexistent")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"] is True
    assert body["status_code"] == 404
    assert "detail" in body


@pytest.mark.asyncio
async def test_422_returns_structured_json(client):
    """Missing required params -> structured JSON error."""
    resp = await client.get("/v1/nearby")
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"] is True
    assert body["status_code"] == 422


@pytest.mark.asyncio
async def test_429_preserves_rate_limit_headers(client):
    """Rate-limited response should include X-RateLimit-* headers."""
    from geohealth.services.rate_limiter import rate_limiter
    from geohealth.api.dependencies import get_db

    rate_limiter._max_requests = 1

    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        # Consume the limit
        await client.get("/v1/stats")
        # Should be rate-limited
        resp = await client.get("/v1/stats")
    finally:
        app.dependency_overrides.clear()
        rate_limiter._max_requests = 60

    assert resp.status_code == 429
    body = resp.json()
    assert body["error"] is True
    assert body["status_code"] == 429
    assert "X-RateLimit-Limit" in resp.headers


@pytest.mark.asyncio
async def test_unhandled_exception_returns_500():
    """An unhandled exception in an endpoint returns structured 500.

    Starlette's ServerErrorMiddleware always re-raises handled exceptions,
    so we use raise_app_exceptions=False to receive the response instead.
    """
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        with patch(
            "geohealth.api.routes.context.geocode",
            new_callable=AsyncMock,
            side_effect=RuntimeError("boom"),
        ):
            resp = await ac.get("/v1/context", params={"address": "test"})

    assert resp.status_code == 500
    body = resp.json()
    assert body["error"] is True
    assert body["status_code"] == 500
    assert body["detail"] == "Internal server error"
    # Must not leak internal details
    assert "boom" not in body["detail"]
