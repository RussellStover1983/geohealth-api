from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from geohealth.api.auth import require_api_key
from geohealth.api.dependencies import get_db
from geohealth.api.schemas import ErrorResponse, StatsResponse
from geohealth.db.models import TractProfile
from geohealth.services.rate_limiter import rate_limiter

router = APIRouter(prefix="/v1", tags=["stats"])


@router.get(
    "/stats",
    summary="Data loading statistics",
    description=(
        "Return a paginated summary of loaded census tract data: total "
        "states, total tracts, and a per-state breakdown ordered by "
        "state FIPS code."
    ),
    response_model=StatsResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Missing API key"},
        403: {"model": ErrorResponse, "description": "Invalid API key"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    },
)
async def get_stats(
    response: Response,
    offset: int = Query(0, ge=0, description="Number of state rows to skip"),
    limit: int = Query(50, gt=0, le=200, description="Max state rows to return"),
    session: AsyncSession = Depends(get_db),
    api_key: str = Depends(require_api_key),
):
    """Return loading statistics: total states, total tracts, and per-state breakdown."""
    # --- rate limit ----------------------------------------------------------
    allowed, rl_headers = rate_limiter.is_allowed(api_key)
    for hdr, val in rl_headers.items():
        response.headers[hdr] = val
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded", headers=rl_headers)

    # Per-state counts
    stmt = (
        select(
            TractProfile.state_fips,
            func.count(TractProfile.geoid).label("tract_count"),
        )
        .group_by(TractProfile.state_fips)
        .order_by(TractProfile.state_fips)
    )
    result = await session.execute(stmt)
    rows = result.all()

    all_states = [{"state_fips": r.state_fips, "tract_count": r.tract_count} for r in rows]

    # Pagination (applied in Python — dataset is bounded at ~56 states/territories)
    paginated = all_states[offset : offset + limit]

    return {
        "total_states": len(all_states),
        "total_tracts": sum(s["tract_count"] for s in all_states),
        "offset": offset,
        "limit": limit,
        "states": paginated,
    }
