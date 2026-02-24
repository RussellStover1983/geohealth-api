"""GET /v1/nearby — find tracts within a radius of a point."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from geoalchemy2.functions import ST_Distance, ST_DWithin, ST_Point, ST_SetSRID
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2 import Geography

from geohealth.api.auth import require_api_key
from geohealth.api.dependencies import get_db
from geohealth.api.schemas import ErrorResponse, NearbyResponse
from geohealth.db.models import TractProfile
from geohealth.services.rate_limiter import rate_limiter

router = APIRouter(prefix="/v1", tags=["nearby"])

MILES_TO_METERS = 1609.344


@router.get(
    "/nearby",
    summary="Find nearby census tracts",
    description=(
        "Return census tracts within a given radius of a point, sorted by "
        "distance (nearest first). Uses PostGIS `ST_DWithin` for efficient "
        "spatial filtering.\n\n"
        "Results are paginated via `offset` and `limit`. The response "
        "includes `total` (all matching tracts) and `count` (tracts in "
        "the current page)."
    ),
    response_model=NearbyResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Missing API key"},
        403: {"model": ErrorResponse, "description": "Invalid API key"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    },
)
async def get_nearby(
    response: Response,
    lat: float = Query(..., ge=-90, le=90, description="Latitude of center point"),
    lng: float = Query(..., ge=-180, le=180, description="Longitude of center point"),
    radius: float = Query(5.0, gt=0, le=50, description="Radius in miles (max 50)"),
    limit: int = Query(25, gt=0, le=100, description="Max results (max 100)"),
    offset: int = Query(0, ge=0, description="Number of rows to skip"),
    session: AsyncSession = Depends(get_db),
    api_key: str = Depends(require_api_key),
):
    """Return census tracts within *radius* miles of (*lat*, *lng*), sorted by distance."""

    # --- rate limit ----------------------------------------------------------
    allowed, rl_headers = rate_limiter.is_allowed(api_key)
    for hdr, val in rl_headers.items():
        response.headers[hdr] = val
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded", headers=rl_headers)

    radius_meters = radius * MILES_TO_METERS

    point = ST_SetSRID(ST_Point(lng, lat), 4326)
    geog_point = cast(point, Geography)
    geog_geom = cast(TractProfile.geom, Geography)

    distance_col = ST_Distance(geog_geom, geog_point).label("distance_m")

    # Count total matching tracts (before pagination)
    count_stmt = (
        select(func.count())
        .select_from(TractProfile)
        .where(TractProfile.geom.isnot(None))
        .where(ST_DWithin(geog_geom, geog_point, radius_meters))
    )
    count_result = await session.execute(count_stmt)
    total = count_result.scalar_one()

    stmt = (
        select(TractProfile, distance_col)
        .where(TractProfile.geom.isnot(None))
        .where(ST_DWithin(geog_geom, geog_point, radius_meters))
        .order_by(distance_col)
        .offset(offset)
        .limit(limit)
    )

    result = await session.execute(stmt)
    rows = result.all()

    tracts = []
    for tract, distance_m in rows:
        tracts.append({
            "geoid": tract.geoid,
            "name": tract.name,
            "distance_miles": round(distance_m / MILES_TO_METERS, 2),
            "total_population": tract.total_population,
            "median_household_income": tract.median_household_income,
            "poverty_rate": tract.poverty_rate,
            "uninsured_rate": tract.uninsured_rate,
            "unemployment_rate": tract.unemployment_rate,
            "median_age": tract.median_age,
            "sdoh_index": tract.sdoh_index,
        })

    return {
        "center": {"lat": lat, "lng": lng},
        "radius_miles": radius,
        "count": len(tracts),
        "total": total,
        "offset": offset,
        "limit": limit,
        "tracts": tracts,
    }
