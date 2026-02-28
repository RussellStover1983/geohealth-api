from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from geohealth.api.dependencies import get_db
from geohealth.api.main import app
from geohealth.services.cache import context_cache
from geohealth.services.geocoder import GeocodedLocation


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear the context cache before each test to prevent cross-test leakage."""
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
    """Return a mock tract ORM object with realistic data."""
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
async def test_health(client):
    mock_result = MagicMock()
    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.get("/health")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"


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


@pytest.mark.asyncio
async def test_default_narrative_is_null(client):
    """Without ?narrative=true, narrative should be null."""
    with (
        patch("geohealth.api.routes.context.geocode", new_callable=AsyncMock) as mock_geo,
        patch("geohealth.api.routes.context.lookup_tract", new_callable=AsyncMock) as mock_tract,
    ):
        mock_geo.return_value = MOCK_LOCATION
        mock_tract.return_value = _make_mock_tract()

        resp = await client.get("/v1/context", params={"address": "1234 Main St"})

    assert resp.status_code == 200
    assert resp.json()["narrative"] is None


@pytest.mark.asyncio
async def test_narrative_true_calls_narrator(client):
    """?narrative=true should call generate_narrative and return the result."""
    with (
        patch("geohealth.api.routes.context.geocode", new_callable=AsyncMock) as mock_geo,
        patch("geohealth.api.routes.context.lookup_tract", new_callable=AsyncMock) as mock_tract,
        patch(
            "geohealth.api.routes.context.generate_narrative", new_callable=AsyncMock
        ) as mock_narr,
    ):
        mock_geo.return_value = MOCK_LOCATION
        mock_tract.return_value = _make_mock_tract()
        mock_narr.return_value = "This is a generated narrative."

        resp = await client.get(
            "/v1/context", params={"address": "1234 Main St", "narrative": "true"}
        )

    assert resp.status_code == 200
    assert resp.json()["narrative"] == "This is a generated narrative."
    mock_narr.assert_called_once()


@pytest.mark.asyncio
async def test_narrative_failure_returns_null(client):
    """If the narrator fails, response should still be 200 with narrative: null."""
    with (
        patch("geohealth.api.routes.context.geocode", new_callable=AsyncMock) as mock_geo,
        patch("geohealth.api.routes.context.lookup_tract", new_callable=AsyncMock) as mock_tract,
        patch(
            "geohealth.api.routes.context.generate_narrative", new_callable=AsyncMock
        ) as mock_narr,
    ):
        mock_geo.return_value = MOCK_LOCATION
        mock_tract.return_value = _make_mock_tract()
        mock_narr.return_value = None  # narrator failure

        resp = await client.get(
            "/v1/context", params={"address": "1234 Main St", "narrative": "true"}
        )

    assert resp.status_code == 200
    assert resp.json()["narrative"] is None


@pytest.mark.asyncio
async def test_second_request_uses_cache(client):
    """Second identical request should use cache — lookup_tract called only once."""
    with (
        patch("geohealth.api.routes.context.geocode", new_callable=AsyncMock) as mock_geo,
        patch("geohealth.api.routes.context.lookup_tract", new_callable=AsyncMock) as mock_tract,
    ):
        mock_geo.return_value = MOCK_LOCATION
        mock_tract.return_value = _make_mock_tract()

        resp1 = await client.get(
            "/v1/context", params={"address": "1234 Main St", "narrative": "false"}
        )
        resp2 = await client.get(
            "/v1/context", params={"address": "1234 Main St", "narrative": "false"}
        )

    assert resp1.status_code == 200
    assert resp2.status_code == 200
    # lookup_tract should only be called once — second request hits cache
    mock_tract.assert_called_once()
    # Both responses should have the same tract data
    assert resp1.json()["tract"]["geoid"] == resp2.json()["tract"]["geoid"]
