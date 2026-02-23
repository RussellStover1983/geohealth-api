"""Tests for GET /v1/nearby endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from geohealth.services.rate_limiter import rate_limiter


def _mock_db_result(rows):
    """Build a mock async session that returns the given (tract, distance_m) rows."""
    mock_result = MagicMock()
    mock_result.all.return_value = rows
    return mock_result


def _make_nearby_tract(geoid="27053001100", name="Census Tract 11", distance_m=500.0):
    tract = MagicMock()
    tract.geoid = geoid
    tract.name = name
    tract.total_population = 4500
    tract.median_household_income = 52000
    tract.poverty_rate = 18.5
    tract.uninsured_rate = 12.3
    tract.unemployment_rate = 7.1
    tract.median_age = 34.2
    tract.sdoh_index = 0.72
    return tract, distance_m


@pytest.mark.asyncio
async def test_nearby_missing_params(client):
    """Missing lat/lng → 422."""
    resp = await client.get("/v1/nearby")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_nearby_missing_lng(client):
    """Missing lng → 422."""
    resp = await client.get("/v1/nearby", params={"lat": 44.97})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_nearby_radius_too_large(client):
    """Radius > 50 → 422."""
    resp = await client.get("/v1/nearby", params={"lat": 44.97, "lng": -93.26, "radius": 51})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_nearby_radius_zero(client):
    """Radius <= 0 → 422."""
    resp = await client.get("/v1/nearby", params={"lat": 44.97, "lng": -93.26, "radius": 0})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_nearby_returns_sorted_tracts(client):
    """Returns tracts sorted by distance."""
    rows = [
        _make_nearby_tract("27053001100", "Tract A", 500.0),
        _make_nearby_tract("27053001200", "Tract B", 2000.0),
        _make_nearby_tract("27053001300", "Tract C", 5000.0),
    ]

    mock_session = AsyncMock()
    mock_session.execute.return_value = _mock_db_result(rows)

    with patch("geohealth.api.routes.nearby.get_db", return_value=mock_session):
        from geohealth.api.dependencies import get_db
        from geohealth.api.main import app

        app.dependency_overrides[get_db] = lambda: mock_session
        try:
            resp = await client.get("/v1/nearby", params={"lat": 44.97, "lng": -93.26})
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 3
    assert body["center"] == {"lat": 44.97, "lng": -93.26}
    assert body["radius_miles"] == 5.0
    # Verify sorted by distance
    distances = [t["distance_miles"] for t in body["tracts"]]
    assert distances == sorted(distances)


@pytest.mark.asyncio
async def test_nearby_empty_result(client):
    """No tracts found → empty list, count 0."""
    mock_session = AsyncMock()
    mock_session.execute.return_value = _mock_db_result([])

    from geohealth.api.dependencies import get_db
    from geohealth.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.get("/v1/nearby", params={"lat": 44.97, "lng": -93.26})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 0
    assert body["tracts"] == []


@pytest.mark.asyncio
async def test_nearby_custom_limit(client):
    """Custom limit parameter is accepted."""
    rows = [_make_nearby_tract("27053001100", "Tract A", 500.0)]

    mock_session = AsyncMock()
    mock_session.execute.return_value = _mock_db_result(rows)

    from geohealth.api.dependencies import get_db
    from geohealth.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.get("/v1/nearby", params={"lat": 44.97, "lng": -93.26, "limit": 10})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["count"] == 1


@pytest.mark.asyncio
async def test_nearby_rate_limit(client):
    """Exceeding rate limit → 429."""
    rate_limiter._max_requests = 1
    try:
        mock_session = AsyncMock()
        mock_session.execute.return_value = _mock_db_result([])

        from geohealth.api.dependencies import get_db
        from geohealth.api.main import app

        app.dependency_overrides[get_db] = lambda: mock_session
        try:
            # First request consumes the limit
            await client.get("/v1/nearby", params={"lat": 44.97, "lng": -93.26})
            # Second should be rate-limited
            resp = await client.get("/v1/nearby", params={"lat": 44.97, "lng": -93.26})
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 429
    finally:
        rate_limiter._max_requests = 60
