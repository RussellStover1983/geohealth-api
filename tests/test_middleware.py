"""Tests for request logging middleware."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from geohealth.api.dependencies import get_db
from geohealth.api.main import app


@pytest.mark.asyncio
async def test_response_time_header_on_success(client):
    """Every response should include X-Response-Time-Ms header."""
    resp = await client.get("/health")
    assert "X-Response-Time-Ms" in resp.headers
    # Should be a valid float
    float(resp.headers["X-Response-Time-Ms"])


@pytest.mark.asyncio
async def test_response_time_header_on_404(client):
    """Even error responses should include X-Response-Time-Ms."""
    resp = await client.get("/nonexistent")
    assert resp.status_code == 404
    assert "X-Response-Time-Ms" in resp.headers


@pytest.mark.asyncio
async def test_response_time_header_on_api_route(client):
    """API routes also include X-Response-Time-Ms."""
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.get("/v1/stats")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert "X-Response-Time-Ms" in resp.headers
