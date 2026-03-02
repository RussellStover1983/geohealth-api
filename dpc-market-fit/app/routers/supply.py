"""Supply detail endpoint — /api/v1/market-fit/supply (Phase 2 stub)."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.models.response import ErrorResponse

router = APIRouter(prefix="/api/v1", tags=["supply"])


@router.get(
    "/market-fit/supply",
    summary="Provider supply analysis (Phase 2)",
    description="Detailed provider supply analysis. Requires NPI and HRSA data integration.",
    responses={
        501: {"model": ErrorResponse, "description": "Not yet implemented"},
    },
)
async def get_supply_detail(
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
        "detail": "Supply analysis endpoint requires NPI + HRSA data (Phase 2). "
                  "Use /market-fit for current supply gap placeholder scoring.",
    }
