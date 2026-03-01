"""GET /v1/tracts/geojson — serve tract boundaries as GeoJSON for map rendering."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from geoalchemy2.functions import ST_AsGeoJSON, ST_DWithin, ST_Point, ST_SetSRID
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2 import Geography

from geohealth.api.auth import require_api_key
from geohealth.api.dependencies import get_db
from geohealth.api.schemas import ErrorResponse
from geohealth.db.models import TractProfile
from geohealth.services.rate_limiter import rate_limiter

router = APIRouter(prefix="/v1", tags=["geojson"])

MILES_TO_METERS = 1609.344


@router.get(
    "/tracts/geojson",
    summary="Tract boundaries as GeoJSON",
    description=(
        "Return census tract boundaries as a GeoJSON FeatureCollection for map "
        "rendering. Each Feature includes the tract polygon geometry and SDOH "
        "metrics as properties.\n\n"
        "Filter by `state_fips` or by spatial radius around a point (`lat`, `lng`, "
        "`radius`). At least one filter is required to avoid returning all tracts."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Missing API key"},
        403: {"model": ErrorResponse, "description": "Invalid API key"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    },
)
async def get_tracts_geojson(
    response: Response,
    state_fips: str | None = Query(None, description="2-digit state FIPS code"),
    lat: float | None = Query(None, ge=-90, le=90, description="Center latitude (for radius filter)"),
    lng: float | None = Query(None, ge=-180, le=180, description="Center longitude (for radius filter)"),
    radius: float = Query(10.0, gt=0, le=50, description="Radius in miles (max 50, used with lat/lng)"),
    limit: int = Query(500, gt=0, le=2000, description="Max tracts to return (max 2000)"),
    session: AsyncSession = Depends(get_db),
    api_key: str = Depends(require_api_key),
):
    """Return tract boundaries as GeoJSON FeatureCollection."""

    # --- rate limit ----------------------------------------------------------
    allowed, rl_headers = rate_limiter.is_allowed(api_key)
    for hdr, val in rl_headers.items():
        response.headers[hdr] = val
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded", headers=rl_headers)

    # Require at least one filter
    if not state_fips and (lat is None or lng is None):
        raise HTTPException(
            status_code=422,
            detail="Provide state_fips or lat+lng to filter tracts",
        )

    geojson_col = ST_AsGeoJSON(TractProfile.geom).label("geojson")

    stmt = (
        select(TractProfile, geojson_col)
        .where(TractProfile.geom.isnot(None))
    )

    # Apply filters
    if state_fips:
        stmt = stmt.where(TractProfile.state_fips == state_fips)

    if lat is not None and lng is not None:
        radius_meters = radius * MILES_TO_METERS
        point = ST_SetSRID(ST_Point(lng, lat), 4326)
        geog_point = cast(point, Geography)
        geog_geom = cast(TractProfile.geom, Geography)
        stmt = stmt.where(ST_DWithin(geog_geom, geog_point, radius_meters))

    stmt = stmt.limit(limit)

    result = await session.execute(stmt)
    rows = result.all()

    import json

    features = []
    for tract, geojson_str in rows:
        geometry = json.loads(geojson_str)

        # Build flat properties dict with all SDOH metrics
        properties: dict = {
            "geoid": tract.geoid,
            "state_fips": tract.state_fips,
            "county_fips": tract.county_fips,
            "tract_code": tract.tract_code,
            "name": tract.name,
            "total_population": tract.total_population,
            "median_household_income": tract.median_household_income,
            "poverty_rate": tract.poverty_rate,
            "uninsured_rate": tract.uninsured_rate,
            "unemployment_rate": tract.unemployment_rate,
            "median_age": tract.median_age,
            "sdoh_index": tract.sdoh_index,
        }

        # Flatten JSONB fields into dot-notation keys for map layer expressions
        if tract.svi_themes:
            for k, v in tract.svi_themes.items():
                properties[f"svi_themes.{k}"] = v

        if tract.places_measures:
            for k, v in tract.places_measures.items():
                properties[f"places_measures.{k}"] = v

        if tract.epa_data:
            for k, v in tract.epa_data.items():
                if k != "_source":
                    properties[f"epa_data.{k}"] = v

        features.append({
            "type": "Feature",
            "geometry": geometry,
            "properties": properties,
        })

    response.headers["Content-Type"] = "application/geo+json"

    return {
        "type": "FeatureCollection",
        "features": features,
    }
