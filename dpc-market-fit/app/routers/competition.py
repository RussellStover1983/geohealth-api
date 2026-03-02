"""Competition/saturation endpoint — /api/v1/market-fit/competition (Phase 3 stub)."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.models.response import ErrorResponse

router = APIRouter(prefix="/api/v1", tags=["competition"])


@router.get(
    "/market-fit/competition",
    summary="Competition landscape (Phase 3)",
    description="Competition and saturation analysis. Requires DPC practice registry.",
    responses={
        501: {"model": ErrorResponse, "description": "Not yet implemented"},
    },
)
async def get_competition_detail(
    address: str | None = Query(None),
    lat: float | None = Query(None),
    lon: float | None = Query(None),
    zip_code: str | None = Query(None),
    tract_fips: str | None = Query(None),
    radius_miles: float = Query(5.0, gt=0, le=50),
) -> dict:
    return {
        "error": True,
        "status_code": 501,
        "detail": "Competition analysis endpoint requires DPC registry data (Phase 3). "
                  "Use /market-fit for current competition placeholder scoring.",
    }
