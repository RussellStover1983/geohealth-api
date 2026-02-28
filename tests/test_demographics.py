"""Tests for GET /v1/demographics/compare — demographic rankings and averages."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from geohealth.api.dependencies import get_db
from geohealth.api.main import app

RANKED_METRICS = [
    "total_population",
    "median_household_income",
    "poverty_rate",
    "uninsured_rate",
    "unemployment_rate",
    "median_age",
    "sdoh_index",
]


def _make_mock_tract():
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
    return tract


def _make_batch_row(tract):
    """Build a mock row for the _batch_stats query with avg/below/total columns."""
    row = MagicMock()
    for metric in RANKED_METRICS:
        setattr(row, f"avg_{metric}", 50.0)
        tract_val = getattr(tract, metric, None)
        if tract_val is not None:
            setattr(row, f"below_{metric}", 40)
            setattr(row, f"total_{metric}", 100)
    return row


def _mock_session_for_demographics(tract):
    """Build a mock session: tract lookup → 3 batch stats queries."""
    session = AsyncMock()
    calls = [0]

    tract_result = MagicMock()
    tract_result.scalar_one_or_none.return_value = tract

    batch_row = _make_batch_row(tract)

    def _execute_side_effect(*args, **kwargs):
        calls[0] += 1
        if calls[0] == 1:
            return tract_result
        # Batch stats query — returns a single row
        result = MagicMock()
        result.one.return_value = batch_row
        return result

    session.execute = AsyncMock(side_effect=_execute_side_effect)
    return session


@pytest.mark.asyncio
async def test_demographics_compare_success(client):
    """Demographics compare returns rankings and averages."""
    tract = _make_mock_tract()
    mock_session = _mock_session_for_demographics(tract)

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.get(
            "/v1/demographics/compare", params={"geoid": "27053001100"}
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["geoid"] == "27053001100"
    assert body["name"] == "Census Tract 11"
    assert body["state_fips"] == "27"
    assert body["county_fips"] == "053"

    # Should have 7 ranked metrics
    assert len(body["rankings"]) == 7
    assert len(body["averages"]) == 7

    # Check structure of rankings
    first_ranking = body["rankings"][0]
    assert "metric" in first_ranking
    assert "value" in first_ranking
    assert "county_percentile" in first_ranking
    assert "state_percentile" in first_ranking
    assert "national_percentile" in first_ranking

    # Check structure of averages
    first_avg = body["averages"][0]
    assert "metric" in first_avg
    assert "tract_value" in first_avg
    assert "county_avg" in first_avg
    assert "state_avg" in first_avg
    assert "national_avg" in first_avg


@pytest.mark.asyncio
async def test_demographics_compare_not_found(client):
    """Returns 404 when tract does not exist."""
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result

    app.dependency_overrides[get_db] = lambda: session
    try:
        resp = await client.get(
            "/v1/demographics/compare", params={"geoid": "99999999999"}
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_demographics_compare_invalid_geoid(client):
    """Returns 422 for invalid GEOID."""
    resp = await client.get("/v1/demographics/compare", params={"geoid": "short"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_demographics_rate_limit(client):
    from geohealth.services.rate_limiter import rate_limiter

    rate_limiter._max_requests = 1
    try:
        tract = _make_mock_tract()
        mock_session = _mock_session_for_demographics(tract)
        app.dependency_overrides[get_db] = lambda: mock_session

        await client.get("/v1/demographics/compare", params={"geoid": "27053001100"})
        resp = await client.get(
            "/v1/demographics/compare", params={"geoid": "27053001100"}
        )
        assert resp.status_code == 429
    finally:
        rate_limiter._max_requests = 60
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_demographics_null_metric_handling(client):
    """Null metrics produce null rankings and averages without errors."""
    tract = _make_mock_tract()
    tract.sdoh_index = None
    mock_session = _mock_session_for_demographics(tract)

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.get(
            "/v1/demographics/compare", params={"geoid": "27053001100"}
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    sdoh_ranking = next(r for r in body["rankings"] if r["metric"] == "sdoh_index")
    assert sdoh_ranking["value"] is None
    assert sdoh_ranking["county_percentile"] is None
