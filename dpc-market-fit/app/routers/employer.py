"""Employer opportunity endpoint — /api/v1/market-fit/employer."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from app.models.response import (
    DataVintage,
    EmployerDetailResponse,
    ErrorResponse,
    ResolvedLocation,
)
from app.services.census_acs import fetch_acs_data
from app.services.census_cbp import fetch_cbp_data
from app.services.geocoder import resolve_location
from app.services.scoring import score_employer
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["employer"])


@router.get(
    "/market-fit/employer",
    response_model=EmployerDetailResponse,
    summary="Employer landscape analysis",
    description=(
        "Employer opportunity analysis including establishment counts, "
        "employee size distribution, and wage data from County Business Patterns."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Invalid input"},
    },
)
async def get_employer_detail(
    address: str | None = Query(None, description="Street address"),
    lat: float | None = Query(None, description="Latitude", ge=-90, le=90),
    lon: float | None = Query(None, description="Longitude", ge=-180, le=180),
    zip_code: str | None = Query(None, description="5-digit ZIP code"),
    tract_fips: str | None = Query(None, description="11-digit tract FIPS"),
    radius_miles: float = Query(5.0, description="Market area radius", gt=0, le=50),
) -> EmployerDetailResponse:
    if not any([address, lat is not None and lon is not None, zip_code, tract_fips]):
        raise HTTPException(
            status_code=400,
            detail="Provide at least one location input: address, lat/lon, zip_code, or tract_fips",
        )

    location = await resolve_location(
        address=address, lat=lat, lon=lon,
        zip_code=zip_code, tract_fips=tract_fips,
    )

    if not location.geoid:
        raise HTTPException(
            status_code=400,
            detail=f"Could not resolve to a census tract: {location.matched_address}",
        )

    input_desc = address or zip_code or tract_fips or f"({lat}, {lon})"

    acs = await fetch_acs_data(location.geoid)
    population = acs.total_population if acs else None

    cbp = None
    if location.state_fips and location.county_fips:
        cbp = await fetch_cbp_data(
            state_fips=location.state_fips,
            county_fips=location.county_fips,
        )

    emp_score = score_employer(cbp, acs)

    return EmployerDetailResponse(
        location=ResolvedLocation(
            input=input_desc,
            resolved_lat=location.lat,
            resolved_lon=location.lon,
            primary_tract_fips=location.geoid,
            tracts_in_radius=[location.geoid],
            radius_miles=radius_miles,
            market_population=population,
        ),
        total_establishments=cbp.total_establishments if cbp else 0,
        target_establishments=cbp.target_establishments if cbp else 0,
        target_establishment_pct=cbp.target_establishment_pct if cbp else None,
        total_employees=cbp.total_employees if cbp else 0,
        avg_annual_wage=cbp.avg_annual_wage if cbp else None,
        industry_breakdown=cbp.industry_breakdown if cbp else {},
        employer_score=emp_score,
        data_vintage=DataVintage(
            census_acs=f"{settings.acs_year} 5-Year" if acs else None,
            cbp="2021" if cbp else None,
        ),
    )
