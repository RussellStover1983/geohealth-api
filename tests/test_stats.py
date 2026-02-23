from unittest.mock import AsyncMock, MagicMock

import pytest

from geohealth.api.dependencies import get_db
from geohealth.api.main import app


@pytest.mark.asyncio
async def test_stats_empty_db(client):
    """Empty database should return zeros."""
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
    body = resp.json()
    assert body["total_states"] == 0
    assert body["total_tracts"] == 0
    assert body["states"] == []


@pytest.mark.asyncio
async def test_stats_with_data(client):
    """Stats endpoint returns correct shape with multiple states."""
    mock_rows = [
        MagicMock(state_fips="06", tract_count=8057),
        MagicMock(state_fips="27", tract_count=1505),
    ]
    mock_result = MagicMock()
    mock_result.all.return_value = mock_rows

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.get("/v1/stats")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_states"] == 2
    assert body["total_tracts"] == 8057 + 1505
    assert len(body["states"]) == 2
    assert body["states"][0]["state_fips"] == "06"
    assert body["states"][1]["tract_count"] == 1505
