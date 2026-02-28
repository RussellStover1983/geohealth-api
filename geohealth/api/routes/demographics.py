"""GET /v1/demographics/compare — tract vs county/state/national with percentile rankings."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from geohealth.api.auth import require_api_key
from geohealth.api.dependencies import get_db
from geohealth.api.schemas import DemographicCompareResponse, ErrorResponse
from geohealth.db.models import TractProfile
from geohealth.services.rate_limiter import rate_limiter

router = APIRouter(prefix="/v1", tags=["demographics"])

RANKED_METRICS = [
    "total_population",
    "median_household_income",
    "poverty_rate",
    "uninsured_rate",
    "unemployment_rate",
    "median_age",
    "sdoh_index",
]


async def _batch_stats(
    session: AsyncSession,
    tract_values: dict[str, float | None],
    filters: dict,
) -> tuple[dict[str, float | None], dict[str, float | None]]:
    """Compute averages and percentiles for all metrics in a single query.

    Returns (averages_dict, percentiles_dict) keyed by metric name.
    """
    cols = []
    for metric in RANKED_METRICS:
        col = getattr(TractProfile, metric)
        cols.append(func.avg(col).label(f"avg_{metric}"))
        # Percentile: count of non-null values below tract value / total non-null
        tract_val = tract_values.get(metric)
        if tract_val is not None:
            cols.append(
                func.count(case((col < tract_val, 1))).label(f"below_{metric}")
            )
            cols.append(
                func.count(case((col.isnot(None), 1))).label(f"total_{metric}")
            )

    stmt = select(*cols).select_from(TractProfile)
    for field, value in filters.items():
        stmt = stmt.where(getattr(TractProfile, field) == value)

    result = await session.execute(stmt)
    row = result.one()

    avgs: dict[str, float | None] = {}
    pcts: dict[str, float | None] = {}
    for metric in RANKED_METRICS:
        raw_avg = getattr(row, f"avg_{metric}", None)
        avgs[metric] = round(float(raw_avg), 4) if raw_avg is not None else None

        tract_val = tract_values.get(metric)
        if tract_val is not None:
            total = getattr(row, f"total_{metric}", 0) or 0
            below = getattr(row, f"below_{metric}", 0) or 0
            pcts[metric] = round((below / total) * 100, 1) if total > 0 else None
        else:
            pcts[metric] = None

    return avgs, pcts


@router.get(
    "/demographics/compare",
    summary="Demographic comparison with rankings",
    description=(
        "Compare a census tract's demographics against county, state, and "
        "national averages. Includes percentile rankings showing where the "
        "tract falls relative to peers at each geographic level.\n\n"
        "Percentiles are computed over all tracts with non-null data for "
        "each metric. A percentile of 80 means the tract ranks higher than "
        "80% of tracts in that scope."
    ),
    response_model=DemographicCompareResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Missing API key"},
        403: {"model": ErrorResponse, "description": "Invalid API key"},
        404: {"model": ErrorResponse, "description": "Tract not found"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    },
)
async def get_demographic_compare(
    response: Response,
    geoid: str = Query(..., min_length=11, max_length=11, description="11-digit tract GEOID"),
    session: AsyncSession = Depends(get_db),
    api_key: str = Depends(require_api_key),
):
    """Compare a tract's demographics against county, state, and national averages."""

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

    # Collect tract values once
    tract_values: dict[str, float | None] = {}
    for metric in RANKED_METRICS:
        raw = getattr(tract, metric, None)
        tract_values[metric] = float(raw) if raw is not None else None

    # 3 batch queries instead of ~43 individual ones
    county_avgs, county_pcts = await _batch_stats(
        session, tract_values,
        {"state_fips": tract.state_fips, "county_fips": tract.county_fips},
    )
    state_avgs, state_pcts = await _batch_stats(
        session, tract_values,
        {"state_fips": tract.state_fips},
    )
    national_avgs, national_pcts = await _batch_stats(
        session, tract_values, {},
    )

    rankings = []
    averages = []
    for metric in RANKED_METRICS:
        tv = tract_values[metric]
        averages.append({
            "metric": metric,
            "tract_value": tv,
            "county_avg": county_avgs[metric],
            "state_avg": state_avgs[metric],
            "national_avg": national_avgs[metric],
        })
        rankings.append({
            "metric": metric,
            "value": tv,
            "county_percentile": county_pcts[metric],
            "state_percentile": state_pcts[metric],
            "national_percentile": national_pcts[metric],
        })

    return {
        "geoid": tract.geoid,
        "name": tract.name,
        "state_fips": tract.state_fips,
        "county_fips": tract.county_fips,
        "rankings": rankings,
        "averages": averages,
    }
