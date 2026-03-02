"""Demand detail endpoint — /api/v1/market-fit/demand."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from app.models.response import (
    ChronicDiseasePrevalence,
    DataVintage,
    DemandDetailResponse,
    ErrorResponse,
    ResolvedLocation,
)
from app.services.census_acs import fetch_acs_data
from app.services.cdc_places import fetch_places_data
from app.services.cdc_svi import fetch_svi_data
from app.services.geocoder import resolve_location
from app.services.scoring import score_affordability, score_demand
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["demand"])


@router.get(
    "/market-fit/demand",
    response_model=DemandDetailResponse,
    summary="Demand indicators",
    description=(
        "Detailed demand-side indicators for the market area including "
        "demographics, insurance coverage, chronic disease prevalence, "
        "and social vulnerability."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Invalid input"},
    },
)
async def get_demand_detail(
    address: str | None = Query(None, description="Street address"),
    lat: float | None = Query(None, description="Latitude", ge=-90, le=90),
    lon: float | None = Query(None, description="Longitude", ge=-180, le=180),
    zip_code: str | None = Query(None, description="5-digit ZIP code"),
    tract_fips: str | None = Query(None, description="11-digit tract FIPS"),
    radius_miles: float = Query(5.0, description="Market area radius", gt=0, le=50),
) -> DemandDetailResponse:
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
    places = await fetch_places_data(location.geoid)
    svi = await fetch_svi_data(location.geoid)

    chronic = None
    if places:
        chronic = ChronicDiseasePrevalence(
            diabetes_pct=places.diabetes_pct,
            hypertension_pct=places.hypertension_pct,
            obesity_pct=places.obesity_pct,
            copd_pct=places.copd_pct,
            depression_pct=places.depression_pct,
            asthma_pct=places.asthma_pct,
        )

    demand = score_demand(acs, places, svi)
    affordability = score_affordability(acs)

    return DemandDetailResponse(
        location=ResolvedLocation(
            input=input_desc,
            resolved_lat=location.lat,
            resolved_lon=location.lon,
            primary_tract_fips=location.geoid,
            tracts_in_radius=[location.geoid],
            radius_miles=radius_miles,
            market_population=acs.total_population if acs else None,
        ),
        total_population=acs.total_population if acs else None,
        working_age_population=acs.working_age_population if acs else None,
        uninsured_rate=acs.uninsured_rate if acs else None,
        uninsured_count=acs.uninsured_count if acs else None,
        employer_insured_rate=acs.employer_insured_rate if acs else None,
        medicaid_rate=acs.medicaid_rate if acs else None,
        medicare_rate=acs.medicare_rate if acs else None,
        median_household_income=acs.median_household_income if acs else None,
        chronic_disease_prevalence=chronic,
        svi_composite=svi.composite if svi else None,
        demand_score=demand,
        affordability_score=affordability,
        data_vintage=DataVintage(
            census_acs=f"{settings.acs_year} 5-Year",
            cdc_places="2024 Release",
            cdc_svi="2022",
        ),
    )
