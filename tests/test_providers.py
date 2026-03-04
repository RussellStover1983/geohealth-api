"""Tests for GET /v1/providers and /v1/providers/geojson endpoints."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest


def _make_provider(
    npi="1234567890",
    name="Jane Smith",
    provider_type="pcp",
    is_fqhc=False,
    state="MO",
):
    """Build a mock NpiProvider."""
    p = MagicMock()
    p.npi = npi
    p.entity_type = "1"
    p.provider_name = name
    p.credential = "MD"
    p.gender = "F"
    p.primary_taxonomy = "207Q00000X"
    p.taxonomy_description = "Family Medicine"
    p.provider_type = provider_type
    p.practice_address = "123 Main St"
    p.practice_city = "Kansas City"
    p.practice_state = state
    p.practice_zip = "64108"
    p.phone = "8165551234"
    p.is_fqhc = is_fqhc
    p.tract_fips = "29095015200"
    p.geom = MagicMock()
    p.geom.ST_Y.return_value = 39.111
    p.geom.ST_X.return_value = -94.583
    return p


def _mock_geojson_session(providers):
    """Build a mock session for GeoJSON endpoint."""
    geojson_str = json.dumps({
        "type": "Point",
        "coordinates": [-94.583, 39.111],
    })
    rows = [(p, geojson_str) for p in providers]

    mock_result = MagicMock()
    mock_result.all.return_value = rows

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result
    return mock_session


def _mock_list_session(providers, total=None):
    """Build a mock session for list endpoint with count + results."""
    if total is None:
        total = len(providers)

    # The endpoint makes two execute calls: count and data
    count_result = MagicMock()
    count_result.scalar.return_value = total

    data_result = MagicMock()
    data_result.scalars.return_value = MagicMock(all=MagicMock(return_value=providers))
    # For radius queries that return tuples
    data_result.all.return_value = [(p, 1.5) for p in providers]

    mock_session = AsyncMock()
    mock_session.execute.side_effect = [count_result, data_result]
    return mock_session


# --- GeoJSON endpoint tests ---


@pytest.mark.asyncio
async def test_providers_geojson_requires_bbox(client):
    """Missing bbox → 422."""
    resp = await client.get("/v1/providers/geojson")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_providers_geojson_invalid_bbox(client):
    """Malformed bbox → 422."""
    mock_session = _mock_geojson_session([])
    from geohealth.api.dependencies import get_db
    from geohealth.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.get(
            "/v1/providers/geojson", params={"bbox": "bad,data"}
        )
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_providers_geojson_returns_feature_collection(client):
    """Valid bbox returns GeoJSON FeatureCollection."""
    providers = [
        _make_provider("1111111111", "Dr. A"),
        _make_provider("2222222222", "Dr. B"),
    ]
    mock_session = _mock_geojson_session(providers)

    from geohealth.api.dependencies import get_db
    from geohealth.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.get(
            "/v1/providers/geojson",
            params={"bbox": "-95.0,38.5,-94.0,39.5"},
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) == 2

    feature = body["features"][0]
    assert feature["type"] == "Feature"
    assert feature["geometry"]["type"] == "Point"
    assert feature["properties"]["npi"] == "1111111111"
    assert feature["properties"]["provider_name"] == "Dr. A"
    assert feature["properties"]["is_fqhc"] is False


@pytest.mark.asyncio
async def test_providers_geojson_fqhc_flag(client):
    """FQHC providers have is_fqhc=True in properties."""
    providers = [_make_provider("3333333333", "FQHC Clinic", "fqhc", True)]
    mock_session = _mock_geojson_session(providers)

    from geohealth.api.dependencies import get_db
    from geohealth.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.get(
            "/v1/providers/geojson",
            params={"bbox": "-95.0,38.5,-94.0,39.5"},
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    props = resp.json()["features"][0]["properties"]
    assert props["is_fqhc"] is True
    assert props["provider_type"] == "fqhc"


@pytest.mark.asyncio
async def test_providers_geojson_empty(client):
    """No providers in bbox → empty FeatureCollection."""
    mock_session = _mock_geojson_session([])

    from geohealth.api.dependencies import get_db
    from geohealth.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.get(
            "/v1/providers/geojson",
            params={"bbox": "-95.0,38.5,-94.0,39.5"},
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["features"] == []


# --- List endpoint tests ---


@pytest.mark.asyncio
async def test_providers_requires_filter(client):
    """Missing both lat/lng and tract_fips → 422."""
    resp = await client.get("/v1/providers")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_providers_by_tract_fips(client):
    """Filter by tract_fips returns providers list."""
    providers = [_make_provider(), _make_provider("9876543210", "Dr. B")]
    mock_session = _mock_list_session(providers)

    from geohealth.api.dependencies import get_db
    from geohealth.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.get(
            "/v1/providers",
            params={"tract_fips": "29095015200"},
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2
    assert body["total"] == 2
    assert len(body["providers"]) == 2
    assert body["providers"][0]["npi"] == "1234567890"


@pytest.mark.asyncio
async def test_providers_by_radius(client):
    """Radius search returns providers with distance."""
    providers = [_make_provider()]
    mock_session = _mock_list_session(providers)

    from geohealth.api.dependencies import get_db
    from geohealth.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.get(
            "/v1/providers",
            params={"lat": "39.1", "lng": "-94.5", "radius": "5"},
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["providers"][0]["distance_miles"] == 1.5


@pytest.mark.asyncio
async def test_providers_pagination(client):
    """Offset and limit are reflected in response."""
    mock_session = _mock_list_session([], total=0)

    from geohealth.api.dependencies import get_db
    from geohealth.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.get(
            "/v1/providers",
            params={"tract_fips": "29095015200", "offset": "10", "limit": "25"},
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["offset"] == 10
    assert body["limit"] == 25
