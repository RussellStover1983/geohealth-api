"""GET /v1/compare — compare two tracts or a tract against state/national averages."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from geohealth.api.auth import require_api_key
from geohealth.api.dependencies import get_db
from geohealth.db.models import TractProfile
from geohealth.services.rate_limiter import rate_limiter

router = APIRouter(prefix="/v1", tags=["compare"])

COMPARED_FIELDS = [
    "total_population",
    "median_household_income",
    "poverty_rate",
    "uninsured_rate",
    "unemployment_rate",
    "median_age",
    "sdoh_index",
]


def _extract_values(tract: TractProfile) -> dict:
    return {f: getattr(tract, f) for f in COMPARED_FIELDS}


def _compute_differences(a_vals: dict, b_vals: dict) -> dict:
    diffs = {}
    for f in COMPARED_FIELDS:
        av, bv = a_vals.get(f), b_vals.get(f)
        if av is not None and bv is not None:
            diffs[f] = round(av - bv, 4)
        else:
            diffs[f] = None
    return diffs


@router.get("/compare")
async def get_compare(
    response: Response,
    geoid1: str = Query(..., min_length=11, max_length=11, description="First tract GEOID (11 chars)"),
    geoid2: str | None = Query(None, min_length=11, max_length=11, description="Second tract GEOID (11 chars)"),
    compare_to: str | None = Query(None, description="Compare to 'state' or 'national' average"),
    session: AsyncSession = Depends(get_db),
    api_key: str = Depends(require_api_key),
):
    """Compare two census tracts, or a tract against state/national averages."""

    # --- rate limit ----------------------------------------------------------
    allowed, rl_headers = rate_limiter.is_allowed(api_key)
    for hdr, val in rl_headers.items():
        response.headers[hdr] = val
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded", headers=rl_headers)

    # --- validate params: exactly one of geoid2 / compare_to -----------------
    if geoid2 and compare_to:
        raise HTTPException(
            status_code=400,
            detail="Provide either 'geoid2' or 'compare_to', not both.",
        )
    if not geoid2 and not compare_to:
        raise HTTPException(
            status_code=400,
            detail="Provide either 'geoid2' or 'compare_to'.",
        )
    if compare_to and compare_to not in ("state", "national"):
        raise HTTPException(
            status_code=400,
            detail="'compare_to' must be 'state' or 'national'.",
        )

    # --- fetch tract A -------------------------------------------------------
    result = await session.execute(
        select(TractProfile).where(TractProfile.geoid == geoid1)
    )
    tract_a = result.scalar_one_or_none()
    if tract_a is None:
        raise HTTPException(status_code=404, detail=f"Tract {geoid1} not found.")

    a_values = _extract_values(tract_a)

    # --- build side B --------------------------------------------------------
    if geoid2:
        result = await session.execute(
            select(TractProfile).where(TractProfile.geoid == geoid2)
        )
        tract_b = result.scalar_one_or_none()
        if tract_b is None:
            raise HTTPException(status_code=404, detail=f"Tract {geoid2} not found.")

        b_values = _extract_values(tract_b)
        b_side = {
            "type": "tract",
            "geoid": tract_b.geoid,
            "label": tract_b.name or f"Tract {tract_b.geoid}",
            "values": b_values,
        }
    else:
        # state or national average
        avg_cols = [func.avg(getattr(TractProfile, f)).label(f) for f in COMPARED_FIELDS]
        stmt = select(*avg_cols)

        if compare_to == "state":
            stmt = stmt.where(TractProfile.state_fips == tract_a.state_fips)
            b_type = "state_average"
            b_label = f"State {tract_a.state_fips} average"
        else:
            b_type = "national_average"
            b_label = "National average"

        result = await session.execute(stmt)
        row = result.one()
        b_values = {}
        for f in COMPARED_FIELDS:
            val = getattr(row, f)
            b_values[f] = round(float(val), 4) if val is not None else None

        b_side = {
            "type": b_type,
            "label": b_label,
            "values": b_values,
        }

    return {
        "a": {
            "type": "tract",
            "geoid": tract_a.geoid,
            "label": tract_a.name or f"Tract {tract_a.geoid}",
            "values": a_values,
        },
        "b": b_side,
        "differences": _compute_differences(a_values, b_side["values"]),
    }
