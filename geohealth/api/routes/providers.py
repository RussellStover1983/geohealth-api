"""GET /v1/providers — serve NPI provider data as GeoJSON or JSON list."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from geoalchemy2.functions import (
    ST_AsGeoJSON,
    ST_Distance,
    ST_MakeEnvelope,
    ST_Point,
    ST_SetSRID,
)
from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from geohealth.api.auth import require_api_key
from geohealth.api.dependencies import get_db
from geohealth.api.schemas import ErrorResponse, ProviderModel, ProvidersResponse
from geohealth.db.models import NpiProvider
from geohealth.services.rate_limiter import rate_limiter

router = APIRouter(prefix="/v1", tags=["providers"])

MILES_TO_METERS = 1609.344


def _provider_properties(row: NpiProvider) -> dict:
    """Build a flat properties dict from an NpiProvider row."""
    return {
        "npi": row.npi,
        "entity_type": row.entity_type,
        "provider_name": row.provider_name,
        "credential": row.credential,
        "gender": row.gender,
        "primary_taxonomy": row.primary_taxonomy,
        "taxonomy_description": row.taxonomy_description,
        "provider_type": row.provider_type,
        "practice_address": row.practice_address,
        "practice_city": row.practice_city,
        "practice_state": row.practice_state,
        "practice_zip": row.practice_zip,
        "phone": row.phone,
        "is_fqhc": row.is_fqhc,
        "tract_fips": row.tract_fips,
    }


@router.get(
    "/providers/geojson",
    summary="NPI providers as GeoJSON",
    description=(
        "Return NPI providers as a GeoJSON FeatureCollection with Point "
        "geometries for map rendering. Filter by bounding box (required) "
        "and optionally by provider type.\n\n"
        "Provider types: `pcp`, `fqhc`, `urgent_care`, `rural_health_clinic`, "
        "`primary_care_clinic`, `community_health_center`, or `all` (default)."
    ),
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
    },
)
async def get_providers_geojson(
    response: Response,
    bbox: str = Query(
        ...,
        description="Bounding box as west,south,east,north (comma-separated)",
    ),
    provider_type: str = Query(
        "all",
        description="Filter by provider type: all, pcp, fqhc, urgent_care, etc.",
    ),
    limit: int = Query(500, gt=0, le=2000, description="Max providers (max 2000)"),
    session: AsyncSession = Depends(get_db),
    api_key: str = Depends(require_api_key),
):
    """Return providers in a bounding box as GeoJSON FeatureCollection."""
    # Rate limit
    allowed, rl_headers = rate_limiter.is_allowed(api_key)
    for hdr, val in rl_headers.items():
        response.headers[hdr] = val
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    # Parse bbox
    try:
        parts = [float(x.strip()) for x in bbox.split(",")]
        if len(parts) != 4:
            raise ValueError
        west, south, east, north = parts
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=422,
            detail="bbox must be 4 comma-separated floats: west,south,east,north",
        )

    geojson_col = ST_AsGeoJSON(NpiProvider.geom).label("geojson")
    envelope = ST_MakeEnvelope(west, south, east, north, 4326)

    stmt = (
        select(NpiProvider, geojson_col)
        .where(NpiProvider.geom.isnot(None))
        .where(NpiProvider.geom.ST_Intersects(envelope))
    )

    if provider_type != "all":
        stmt = stmt.where(NpiProvider.provider_type == provider_type)

    stmt = stmt.limit(limit)

    result = await session.execute(stmt)
    rows = result.all()

    features = []
    for provider, geojson_str in rows:
        geometry = json.loads(geojson_str)
        features.append({
            "type": "Feature",
            "geometry": geometry,
            "properties": _provider_properties(provider),
        })

    response.headers["Content-Type"] = "application/geo+json"
    return {
        "type": "FeatureCollection",
        "features": features,
    }


@router.get(
    "/providers",
    summary="Search NPI providers",
    description=(
        "Search for NPI providers by radius around a point or by census "
        "tract FIPS code. Returns a paginated JSON list with distance "
        "when querying by radius.\n\n"
        "Provider types: `pcp`, `fqhc`, `urgent_care`, `rural_health_clinic`, "
        "`primary_care_clinic`, `community_health_center`, or `all` (default)."
    ),
    response_model=ProvidersResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
    },
)
async def get_providers(
    response: Response,
    lat: float | None = Query(None, ge=-90, le=90, description="Center latitude"),
    lng: float | None = Query(None, ge=-180, le=180, description="Center longitude"),
    radius: float = Query(5.0, gt=0, le=50, description="Radius in miles (max 50)"),
    tract_fips: str | None = Query(None, description="11-digit census tract FIPS"),
    provider_type: str = Query("all", description="Filter by provider type"),
    limit: int = Query(50, gt=0, le=500, description="Max results (max 500)"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    session: AsyncSession = Depends(get_db),
    api_key: str = Depends(require_api_key),
):
    """Search for NPI providers by radius or tract."""
    # Rate limit
    allowed, rl_headers = rate_limiter.is_allowed(api_key)
    for hdr, val in rl_headers.items():
        response.headers[hdr] = val
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    if lat is None and lng is None and tract_fips is None:
        raise HTTPException(
            status_code=422,
            detail="Provide lat+lng or tract_fips to search providers",
        )

    has_radius_query = lat is not None and lng is not None

    if has_radius_query:
        point = ST_SetSRID(ST_Point(lng, lat), 4326)
        geog_point = cast(point, Geography)
        geog_geom = cast(NpiProvider.geom, Geography)
        distance_col = (
            ST_Distance(geog_geom, geog_point) / MILES_TO_METERS
        ).label("distance_miles")

        stmt = (
            select(NpiProvider, distance_col)
            .where(NpiProvider.geom.isnot(None))
            .where(
                ST_Distance(geog_geom, geog_point)
                <= radius * MILES_TO_METERS
            )
        )

        if provider_type != "all":
            stmt = stmt.where(NpiProvider.provider_type == provider_type)

        # Count total
        count_stmt = (
            select(func.count())
            .select_from(NpiProvider)
            .where(NpiProvider.geom.isnot(None))
            .where(
                ST_Distance(geog_geom, geog_point)
                <= radius * MILES_TO_METERS
            )
        )
        if provider_type != "all":
            count_stmt = count_stmt.where(
                NpiProvider.provider_type == provider_type
            )

        total = (await session.execute(count_stmt)).scalar() or 0

        stmt = stmt.order_by(distance_col).offset(offset).limit(limit)
        result = await session.execute(stmt)
        rows = result.all()

        providers = []
        for provider, dist in rows:
            providers.append(
                ProviderModel(
                    **_provider_properties(provider),
                    lat=provider.geom.ST_Y() if provider.geom else None,
                    lng=provider.geom.ST_X() if provider.geom else None,
                    distance_miles=round(dist, 2) if dist else None,
                )
            )

    else:
        # Tract FIPS query
        stmt = (
            select(NpiProvider)
            .where(NpiProvider.tract_fips == tract_fips)
        )
        if provider_type != "all":
            stmt = stmt.where(NpiProvider.provider_type == provider_type)

        count_stmt = (
            select(func.count())
            .select_from(NpiProvider)
            .where(NpiProvider.tract_fips == tract_fips)
        )
        if provider_type != "all":
            count_stmt = count_stmt.where(
                NpiProvider.provider_type == provider_type
            )

        total = (await session.execute(count_stmt)).scalar() or 0

        stmt = stmt.offset(offset).limit(limit)
        result = await session.execute(stmt)
        rows = result.scalars().all()

        providers = []
        for provider in rows:
            providers.append(
                ProviderModel(
                    **_provider_properties(provider),
                    lat=None,
                    lng=None,
                    distance_miles=None,
                )
            )

    return ProvidersResponse(
        count=len(providers),
        total=total,
        offset=offset,
        limit=limit,
        providers=providers,
    )
