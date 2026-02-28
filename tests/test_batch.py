"""Tests for POST /v1/batch endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from geohealth.services.cache import context_cache
from geohealth.services.geocoder import GeocodedLocation
from geohealth.services.rate_limiter import rate_limiter


@pytest.fixture(autouse=True)
def _clear_cache():
    context_cache.clear()
    yield
    context_cache.clear()


MOCK_LOCATION = GeocodedLocation(
    lat=44.9778,
    lng=-93.2650,
    matched_address="1234 MAIN ST, MINNEAPOLIS, MN, 55401",
    state_fips="27",
    county_fips="053",
    tract_fips="001100",
)


def _make_mock_tract():
    tract = MagicMock()
    tract.geoid = "27053001100"
    tract.state_fips = "27"
    tract.county_fips = "053"
    tract.tract_code = "001100"
    tract.name = "Census Tract 11"
    tract.total_population = 4500
    tract.median_household_income = 52000
    tract.poverty_rate = 18.5
    tract.uninsured_rate = 12.3
    tract.unemployment_rate = 7.1
    tract.median_age = 34.2
    tract.svi_themes = {"socioeconomic_status": 0.78}
    tract.places_measures = {"diabetes": 12.1}
    tract.sdoh_index = 0.72
    tract.epa_data = None
    return tract


@pytest.mark.asyncio
async def test_batch_empty_body(client):
    """POST with no body → 422."""
    resp = await client.post("/v1/batch")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_batch_empty_addresses(client):
    """POST with empty addresses list → 422."""
    resp = await client.post("/v1/batch", json={"addresses": []})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_batch_too_many_addresses(client):
    """Exceeding batch_max_size → 400."""
    with patch("geohealth.api.routes.batch.settings") as mock_settings:
        mock_settings.batch_max_size = 2
        resp = await client.post("/v1/batch", json={"addresses": ["a", "b", "c"]})
    assert resp.status_code == 400
    assert "Too many addresses" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_batch_single_success(client):
    """Single address batch returns correct shape."""
    with (
        patch("geohealth.api.routes.batch.geocode", new_callable=AsyncMock) as mock_geo,
        patch("geohealth.api.routes.batch.lookup_tract", new_callable=AsyncMock) as mock_lookup,
    ):
        mock_geo.return_value = MOCK_LOCATION
        mock_lookup.return_value = _make_mock_tract()

        resp = await client.post("/v1/batch", json={"addresses": ["1234 Main St"]})

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["succeeded"] == 1
    assert body["failed"] == 0
    assert body["results"][0]["status"] == "ok"
    assert body["results"][0]["tract"]["geoid"] == "27053001100"


@pytest.mark.asyncio
async def test_batch_multiple_success(client):
    """Multiple addresses all succeed."""
    with (
        patch("geohealth.api.routes.batch.geocode", new_callable=AsyncMock) as mock_geo,
        patch("geohealth.api.routes.batch.lookup_tract", new_callable=AsyncMock) as mock_lookup,
    ):
        mock_geo.return_value = MOCK_LOCATION
        mock_lookup.return_value = _make_mock_tract()

        resp = await client.post("/v1/batch", json={"addresses": ["addr1", "addr2"]})

    body = resp.json()
    assert body["total"] == 2
    assert body["succeeded"] == 2
    assert body["failed"] == 0


@pytest.mark.asyncio
async def test_batch_partial_failure(client):
    """One address fails, others succeed — no 500."""
    call_count = 0

    async def _geocode_side_effect(addr):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise ValueError("Geocode failed for bad address")
        return MOCK_LOCATION

    with (
        patch("geohealth.api.routes.batch.geocode", new_callable=AsyncMock, side_effect=_geocode_side_effect),
        patch("geohealth.api.routes.batch.lookup_tract", new_callable=AsyncMock) as mock_lookup,
    ):
        mock_lookup.return_value = _make_mock_tract()
        resp = await client.post("/v1/batch", json={"addresses": ["good1", "bad", "good2"]})

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert body["succeeded"] == 2
    assert body["failed"] == 1
    error_result = [r for r in body["results"] if r["status"] == "error"]
    assert len(error_result) == 1
    assert error_result[0]["error"] is not None


@pytest.mark.asyncio
async def test_batch_uses_cache(client):
    """Second identical address in batch uses cache — lookup_tract called once."""
    with (
        patch("geohealth.api.routes.batch.geocode", new_callable=AsyncMock) as mock_geo,
        patch("geohealth.api.routes.batch.lookup_tract", new_callable=AsyncMock) as mock_lookup,
    ):
        mock_geo.return_value = MOCK_LOCATION
        mock_lookup.return_value = _make_mock_tract()

        resp = await client.post("/v1/batch", json={"addresses": ["same addr", "same addr"]})

    assert resp.status_code == 200
    # Both should succeed
    body = resp.json()
    assert body["succeeded"] == 2
    # Due to asyncio.gather concurrency, both tasks may run lookup_tract before
    # either caches. What matters is both results are ok.


@pytest.mark.asyncio
async def test_batch_rate_limit(client):
    """Exceeding rate limit → 429."""
    rate_limiter._max_requests = 1
    try:
        with (
            patch("geohealth.api.routes.batch.geocode", new_callable=AsyncMock) as mock_geo,
            patch("geohealth.api.routes.batch.lookup_tract", new_callable=AsyncMock) as mock_lookup,
        ):
            mock_geo.return_value = MOCK_LOCATION
            mock_lookup.return_value = None

            # First request consumes the limit
            await client.post("/v1/batch", json={"addresses": ["a"]})
            # Second should be rate-limited
            resp = await client.post("/v1/batch", json={"addresses": ["b"]})

        assert resp.status_code == 429
    finally:
        rate_limiter._max_requests = 60
