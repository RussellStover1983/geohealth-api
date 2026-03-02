"""Tests for GET /v1/tracts/geojson endpoint."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest



def _make_tract(geoid="27053001100", name="Census Tract 11"):
    """Build a mock TractProfile with geometry."""
    tract = MagicMock()
    tract.geoid = geoid
    tract.state_fips = geoid[:2]
    tract.county_fips = geoid[2:5]
    tract.tract_code = geoid[5:]
    tract.name = name
    tract.total_population = 4500
    tract.median_household_income = 52000
    tract.poverty_rate = 18.5
    tract.uninsured_rate = 12.3
    tract.unemployment_rate = 7.1
    tract.median_age = 34.2
    tract.sdoh_index = 0.72
    tract.svi_themes = {"rpl_theme1": 0.65, "rpl_themes": 0.58}
    tract.places_measures = {"diabetes": 12.1, "obesity": 33.2}
    tract.epa_data = {"pm25": 8.1, "_source": "estimated"}
    return tract


def _mock_geojson_session(tracts):
    """Build a mock session that returns tracts with GeoJSON geometry strings."""
    geojson_str = json.dumps({
        "type": "MultiPolygon",
        "coordinates": [[[[-93.26, 44.97], [-93.25, 44.97], [-93.25, 44.98], [-93.26, 44.98], [-93.26, 44.97]]]],
    })

    rows = [(t, geojson_str) for t in tracts]

    mock_result = MagicMock()
    mock_result.all.return_value = rows

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result
    return mock_session


@pytest.mark.asyncio
async def test_geojson_requires_filter(client):
    """Missing both state_fips and lat/lng → 422."""
    resp = await client.get("/v1/tracts/geojson")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_geojson_by_state_fips(client):
    """Filter by state_fips returns GeoJSON FeatureCollection."""
    tracts = [_make_tract("27053001100", "Tract A"), _make_tract("27053001200", "Tract B")]
    mock_session = _mock_geojson_session(tracts)

    from geohealth.api.dependencies import get_db
    from geohealth.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.get("/v1/tracts/geojson", params={"state_fips": "27"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) == 2

    feature = body["features"][0]
    assert feature["type"] == "Feature"
    assert feature["geometry"]["type"] == "MultiPolygon"
    assert feature["properties"]["geoid"] == "27053001100"
    assert feature["properties"]["poverty_rate"] == 18.5
    assert feature["properties"]["sdoh_index"] == 0.72


@pytest.mark.asyncio
async def test_geojson_flattens_jsonb_fields(client):
    """JSONB fields (svi_themes, places_measures, epa_data) are flattened with dot notation."""
    tracts = [_make_tract()]
    mock_session = _mock_geojson_session(tracts)

    from geohealth.api.dependencies import get_db
    from geohealth.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.get("/v1/tracts/geojson", params={"state_fips": "27"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    props = resp.json()["features"][0]["properties"]
    assert props["svi_themes.rpl_theme1"] == 0.65
    assert props["svi_themes.rpl_themes"] == 0.58
    assert props["places_measures.diabetes"] == 12.1
    assert props["epa_data.pm25"] == 8.1
    # _source should be excluded from epa flattening
    assert "epa_data._source" not in props


@pytest.mark.asyncio
async def test_geojson_by_lat_lng(client):
    """Filter by lat/lng radius returns tracts."""
    tracts = [_make_tract()]
    mock_session = _mock_geojson_session(tracts)

    from geohealth.api.dependencies import get_db
    from geohealth.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.get(
            "/v1/tracts/geojson",
            params={"lat": "44.97", "lng": "-93.26", "radius": "5"},
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) == 1


@pytest.mark.asyncio
async def test_geojson_empty_result(client):
    """No matching tracts → empty FeatureCollection."""
    mock_session = _mock_geojson_session([])

    from geohealth.api.dependencies import get_db
    from geohealth.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.get("/v1/tracts/geojson", params={"state_fips": "99"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "FeatureCollection"
    assert body["features"] == []
