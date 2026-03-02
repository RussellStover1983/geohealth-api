"""Main scoring endpoint — /api/v1/market-fit."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from app.models.enums import Dimension, ProviderTier
from app.models.response import (
    DataVintage,
    DimensionScore,
    ErrorResponse,
    MarketFitResponse,
    ResolvedLocation,
)
from app.services.census_acs import fetch_acs_data
from app.services.cdc_places import fetch_places_data
from app.services.cdc_svi import fetch_svi_data
from app.services.geocoder import resolve_location
from app.services.scoring import (
    compute_composite,
    score_affordability,
    score_competition,
    score_demand,
    score_employer,
    score_supply_gap,
)
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["market-fit"])


@router.get(
    "/market-fit",
    response_model=MarketFitResponse,
    summary="DPC Market Fit Score",
    description=(
        "Evaluate the DPC market viability for a location. Returns a composite "
        "score (0-100) with five dimensional sub-scores: demand, supply gap, "
        "affordability, employer opportunity, and competition."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Invalid input"},
        422: {"model": ErrorResponse, "description": "Validation error"},
    },
)
async def get_market_fit(
    address: str | None = Query(None, description="Street address to geocode"),
    lat: float | None = Query(None, description="Latitude", ge=-90, le=90),
    lon: float | None = Query(None, description="Longitude", ge=-180, le=180),
    zip_code: str | None = Query(None, description="5-digit ZIP code"),
    tract_fips: str | None = Query(None, description="11-digit census tract FIPS"),
    radius_miles: float = Query(5.0, description="Market area radius in miles", gt=0, le=50),
    provider_tier: ProviderTier = Query(
        ProviderTier.TIER1, description="NPI taxonomy tier for supply calculations"
    ),
    w_demand: float = Query(0.25, description="Demand dimension weight", ge=0, le=1),
    w_supply_gap: float = Query(0.25, description="Supply gap dimension weight", ge=0, le=1),
    w_affordability: float = Query(0.20, description="Affordability dimension weight", ge=0, le=1),
    w_employer: float = Query(0.20, description="Employer dimension weight", ge=0, le=1),
    w_competition: float = Query(0.10, description="Competition dimension weight", ge=0, le=1),
) -> MarketFitResponse:
    # Validate at least one location input
    if not any([address, lat is not None and lon is not None, zip_code, tract_fips]):
        raise HTTPException(
            status_code=400,
            detail="Provide at least one location input: address, lat/lon, zip_code, or tract_fips",
        )

    # Resolve location to tract FIPS
    location = await resolve_location(
        address=address, lat=lat, lon=lon,
        zip_code=zip_code, tract_fips=tract_fips,
    )

    if not location.geoid:
        raise HTTPException(
            status_code=400,
            detail=f"Could not resolve location to a census tract: {location.matched_address}",
        )

    # Build input description
    input_desc = address or zip_code or tract_fips or f"({lat}, {lon})"

    # Fetch data from all Phase 1 sources in parallel
    acs = await fetch_acs_data(location.geoid)
    places = await fetch_places_data(location.geoid)
    svi = await fetch_svi_data(location.geoid)

    # Score dimensions
    demand = score_demand(acs, places, svi)
    affordability = score_affordability(acs)
    supply_gap = score_supply_gap()
    employer = score_employer()
    competition = score_competition()

    dimension_scores: dict[str, DimensionScore] = {
        Dimension.DEMAND.value: demand,
        Dimension.SUPPLY_GAP.value: supply_gap,
        Dimension.AFFORDABILITY.value: affordability,
        Dimension.EMPLOYER.value: employer,
        Dimension.COMPETITION.value: competition,
    }

    # Compute composite with user-provided or default weights
    weights = {
        Dimension.DEMAND.value: w_demand,
        Dimension.SUPPLY_GAP.value: w_supply_gap,
        Dimension.AFFORDABILITY.value: w_affordability,
        Dimension.EMPLOYER.value: w_employer,
        Dimension.COMPETITION.value: w_competition,
    }
    composite = compute_composite(dimension_scores, weights)

    # Market population from ACS
    market_pop = acs.total_population if acs else None

    return MarketFitResponse(
        location=ResolvedLocation(
            input=input_desc,
            resolved_lat=location.lat,
            resolved_lon=location.lon,
            primary_tract_fips=location.geoid,
            tracts_in_radius=[location.geoid],
            radius_miles=radius_miles,
            market_population=market_pop,
        ),
        composite_score=composite,
        dimensions=dimension_scores,
        narrative=None,  # Phase 4 — Claude API narrative
        data_vintage=DataVintage(
            census_acs=f"{settings.acs_year} 5-Year",
            cdc_places="2024 Release",
            cdc_svi="2022",
        ),
    )
