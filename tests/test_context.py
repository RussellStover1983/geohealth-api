from unittest.mock import AsyncMock, patch

import pytest

from geohealth.services.geocoder import GeocodedLocation


MOCK_LOCATION = GeocodedLocation(
    lat=44.9778,
    lng=-93.2650,
    matched_address="1234 MAIN ST, MINNEAPOLIS, MN, 55401",
    state_fips="27",
    county_fips="053",
    tract_fips="001100",
)


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_context_requires_params(client):
    resp = await client.get("/v1/context")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_context_with_address(client):
    with (
        patch("geohealth.api.routes.context.geocode", new_callable=AsyncMock) as mock_geo,
        patch("geohealth.api.routes.context.lookup_tract", new_callable=AsyncMock) as mock_tract,
    ):
        mock_geo.return_value = MOCK_LOCATION
        mock_tract.return_value = None  # no tract in DB

        resp = await client.get("/v1/context", params={"address": "1234 Main St, Minneapolis, MN"})

    assert resp.status_code == 200
    body = resp.json()

    assert body["location"]["lat"] == pytest.approx(44.9778)
    assert body["location"]["lng"] == pytest.approx(-93.2650)
    # FIPS still returned from geocoder even without DB row
    assert body["tract"]["geoid"] == "27053001100"
    assert "narrative" in body


@pytest.mark.asyncio
async def test_context_with_lat_lng(client):
    with patch("geohealth.api.routes.context.lookup_tract", new_callable=AsyncMock) as mock_tract:
        mock_tract.return_value = None

        resp = await client.get("/v1/context", params={"lat": 44.9778, "lng": -93.265})

    assert resp.status_code == 200
    body = resp.json()
    assert body["location"]["lat"] == pytest.approx(44.9778)
