from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from geohealth.api.dependencies import get_db
from geohealth.db.models import TractProfile

router = APIRouter(prefix="/v1", tags=["stats"])


@router.get("/stats")
async def get_stats(session: AsyncSession = Depends(get_db)):
    """Return loading statistics: total states, total tracts, and per-state breakdown."""
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
