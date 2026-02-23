from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from geohealth.api.auth import require_api_key
from geohealth.api.dependencies import get_db
from geohealth.db.models import TractProfile
from geohealth.services.rate_limiter import rate_limiter

router = APIRouter(prefix="/v1", tags=["stats"])


@router.get("/stats")
async def get_stats(
    response: Response,
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

    states = [{"state_fips": r.state_fips, "tract_count": r.tract_count} for r in rows]

    return {
        "total_states": len(states),
        "total_tracts": sum(s["tract_count"] for s in states),
        "states": states,
    }
