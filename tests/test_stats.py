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
    assert body["offset"] == 0
    assert body["limit"] == 50


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


@pytest.mark.asyncio
async def test_stats_pagination_offset_limit(client):
    """Pagination returns correct slice of states."""
    mock_rows = [
        MagicMock(state_fips="01", tract_count=100),
        MagicMock(state_fips="02", tract_count=200),
        MagicMock(state_fips="04", tract_count=300),
        MagicMock(state_fips="05", tract_count=400),
        MagicMock(state_fips="06", tract_count=500),
    ]
    mock_result = MagicMock()
    mock_result.all.return_value = mock_rows

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.get("/v1/stats", params={"offset": 1, "limit": 2})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    # total_states is always full count
    assert body["total_states"] == 5
    assert body["total_tracts"] == 1500
    assert body["offset"] == 1
    assert body["limit"] == 2
    # Only 2 states returned, starting from index 1
    assert len(body["states"]) == 2
    assert body["states"][0]["state_fips"] == "02"
    assert body["states"][1]["state_fips"] == "04"


@pytest.mark.asyncio
async def test_stats_pagination_beyond_end(client):
    """Offset beyond available states returns empty list."""
    mock_rows = [
        MagicMock(state_fips="06", tract_count=8057),
    ]
    mock_result = MagicMock()
    mock_result.all.return_value = mock_rows

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.get("/v1/stats", params={"offset": 100})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_states"] == 1
    assert body["states"] == []
