"""Tests for GET /v1/trends — historical trend data."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from geohealth.api.dependencies import get_db
from geohealth.api.main import app


def _make_mock_tract(with_trends=True):
    tract = MagicMock()
    tract.geoid = "27053001100"
    tract.name = "Census Tract 11"
    tract.state_fips = "27"
    tract.county_fips = "053"
    tract.tract_code = "001100"
    tract.total_population = 4500
    tract.median_household_income = 52000.0
    tract.poverty_rate = 18.5
    tract.uninsured_rate = 12.3
    tract.unemployment_rate = 7.1
    tract.median_age = 34.2
    tract.sdoh_index = 0.72
    tract.svi_themes = {}
    tract.places_measures = {}
    tract.epa_data = {}
    if with_trends:
        tract.trends = {
            "2018": {
                "total_population": 4200,
                "median_household_income": 48000.0,
                "poverty_rate": 20.1,
                "uninsured_rate": 14.0,
                "unemployment_rate": 8.5,
                "median_age": 33.0,
            },
            "2019": {
                "total_population": 4300,
                "median_household_income": 49500.0,
                "poverty_rate": 19.5,
                "uninsured_rate": 13.5,
                "unemployment_rate": 8.0,
                "median_age": 33.5,
            },
            "2020": {
                "total_population": 4350,
                "median_household_income": 50000.0,
                "poverty_rate": 19.0,
                "uninsured_rate": 13.0,
                "unemployment_rate": 9.0,
                "median_age": 33.8,
            },
        }
    else:
        tract.trends = None
    return tract


def _mock_session(tract):
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = tract
    session.execute.return_value = mock_result
    return session


@pytest.mark.asyncio
async def test_trends_with_historical_data(client):
    """Trends endpoint returns historical year data and computed changes."""
    tract = _make_mock_tract(with_trends=True)
    mock_session = _mock_session(tract)

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.get("/v1/trends", params={"geoid": "27053001100"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["geoid"] == "27053001100"
    assert body["name"] == "Census Tract 11"
    # Should have 4 years: 2018, 2019, 2020, 2022 (current)
    assert len(body["years"]) == 4
    assert body["years"][0]["year"] == 2018
    assert body["years"][-1]["year"] == 2022

    # Changes should be computed
    assert len(body["changes"]) == 6  # 6 metrics
    poverty_change = next(c for c in body["changes"] if c["metric"] == "poverty_rate")
    assert poverty_change["earliest_year"] == 2018
    assert poverty_change["latest_year"] == 2022
    assert poverty_change["earliest_value"] == pytest.approx(20.1)
    assert poverty_change["latest_value"] == pytest.approx(18.5)
    assert poverty_change["absolute_change"] is not None


@pytest.mark.asyncio
async def test_trends_without_historical_data(client):
    """Trends endpoint returns current snapshot when no trends data loaded."""
    tract = _make_mock_tract(with_trends=False)
    mock_session = _mock_session(tract)

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.get("/v1/trends", params={"geoid": "27053001100"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    # Only current year
    assert len(body["years"]) == 1
    assert body["years"][0]["year"] == 2022
    assert body["years"][0]["total_population"] == 4500
    # No meaningful changes with only one year
    for change in body["changes"]:
        assert change["absolute_change"] is None


@pytest.mark.asyncio
async def test_trends_tract_not_found(client):
    """Returns 404 when tract does not exist."""
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result

    app.dependency_overrides[get_db] = lambda: session
    try:
        resp = await client.get("/v1/trends", params={"geoid": "99999999999"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_trends_invalid_geoid(client):
    """Returns 422 for invalid GEOID length."""
    resp = await client.get("/v1/trends", params={"geoid": "123"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_trends_rate_limit(client):
    from geohealth.services.rate_limiter import rate_limiter

    rate_limiter._max_requests = 1
    try:
        tract = _make_mock_tract()
        mock_session = _mock_session(tract)
        app.dependency_overrides[get_db] = lambda: mock_session

        await client.get("/v1/trends", params={"geoid": "27053001100"})
        resp = await client.get("/v1/trends", params={"geoid": "27053001100"})
        assert resp.status_code == 429
    finally:
        rate_limiter._max_requests = 60
        app.dependency_overrides.clear()
