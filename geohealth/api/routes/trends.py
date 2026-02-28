"""GET /v1/trends — historical trend data for a census tract."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from geohealth.api.auth import require_api_key
from geohealth.api.dependencies import get_db
from geohealth.api.schemas import ErrorResponse, TrendsResponse
from geohealth.config import settings
from geohealth.db.models import TractProfile
from geohealth.services.rate_limiter import rate_limiter

router = APIRouter(prefix="/v1", tags=["trends"])

TREND_METRICS = [
    "total_population",
    "median_household_income",
    "poverty_rate",
    "uninsured_rate",
    "unemployment_rate",
    "median_age",
]


def _compute_changes(years_data: list[dict]) -> list[dict]:
    """Compute absolute and percent change between earliest and latest data points."""
    changes = []
    for metric in TREND_METRICS:
        earliest_year = None
        earliest_val = None
        latest_year = None
        latest_val = None

        for yd in years_data:
            val = yd.get(metric)
            if val is not None:
                yr = yd["year"]
                if earliest_year is None or yr < earliest_year:
                    earliest_year = yr
                    earliest_val = val
                if latest_year is None or yr > latest_year:
                    latest_year = yr
                    latest_val = val

        absolute_change = None
        percent_change = None
        if earliest_val is not None and latest_val is not None and earliest_year != latest_year:
            absolute_change = round(latest_val - earliest_val, 4)
            if earliest_val != 0:
                percent_change = round(
                    ((latest_val - earliest_val) / abs(earliest_val)) * 100, 2
                )

        changes.append({
            "metric": metric,
            "earliest_year": earliest_year,
            "latest_year": latest_year,
            "earliest_value": earliest_val,
            "latest_value": latest_val,
            "absolute_change": absolute_change,
            "percent_change": percent_change,
        })
    return changes


@router.get(
    "/trends",
    summary="Get historical trends for a tract",
    description=(
        "Returns historical ACS demographic data for a census tract across "
        "multiple years, with computed change metrics.\n\n"
        "Trend data must be loaded via the ETL pipeline. If no trend data "
        "exists, the response will contain only the current-year snapshot."
    ),
    response_model=TrendsResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Missing API key"},
        403: {"model": ErrorResponse, "description": "Invalid API key"},
        404: {"model": ErrorResponse, "description": "Tract not found"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    },
)
async def get_trends(
    response: Response,
    geoid: str = Query(..., min_length=11, max_length=11, description="11-digit tract GEOID"),
    session: AsyncSession = Depends(get_db),
    api_key: str = Depends(require_api_key),
):
    """Return historical trend data for a census tract."""

    # --- rate limit ----------------------------------------------------------
    allowed, rl_headers = rate_limiter.is_allowed(api_key)
    for hdr, val in rl_headers.items():
        response.headers[hdr] = val
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    # --- fetch tract ---------------------------------------------------------
    result = await session.execute(
        select(TractProfile).where(TractProfile.geoid == geoid)
    )
    tract = result.scalar_one_or_none()
    if tract is None:
        raise HTTPException(status_code=404, detail=f"Tract {geoid} not found.")

    # --- build year snapshots ------------------------------------------------
    years_data = []

    # Include historical trend data if available
    if tract.trends and isinstance(tract.trends, dict):
        for year_str, data in sorted(tract.trends.items()):
            try:
                year_int = int(year_str)
            except (ValueError, TypeError):
                continue
            entry = {"year": year_int}
            for metric in TREND_METRICS:
                entry[metric] = data.get(metric)
            years_data.append(entry)

    # Always include current data as the latest snapshot
    current = {"year": settings.acs_current_year}
    for metric in TREND_METRICS:
        current[metric] = getattr(tract, metric, None)
    # Only add if not already present from trends
    current_years = {yd["year"] for yd in years_data}
    if settings.acs_current_year not in current_years:
        years_data.append(current)

    years_data.sort(key=lambda x: x["year"])

    # --- compute changes -----------------------------------------------------
    changes = _compute_changes(years_data)

    return {
        "geoid": tract.geoid,
        "name": tract.name,
        "years": years_data,
        "changes": changes,
    }
