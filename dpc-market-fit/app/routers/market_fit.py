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
from app.services.census_acs import fetch_acs_data, fetch_county_population
from app.services.census_cbp import fetch_cbp_data
from app.services.cdc_places import fetch_places_data
from app.services.cdc_svi import fetch_svi_data
from app.services.geocoder import resolve_location
from app.services.hrsa_hpsa import fetch_hpsa_data
from app.services.npi_registry import fetch_npi_providers
from app.services.npi_tract_lookup import lookup_tract_npi
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

    # Fetch data from all sources
    acs = await fetch_acs_data(location.geoid)
    places = await fetch_places_data(location.geoid)
    svi = await fetch_svi_data(location.geoid)

    # Phase 2 data sources
    state_code = _state_fips_to_abbrev(location.state_fips) if location.state_fips else None
    npi = None
    hpsa = None
    cbp = None

    if state_code and location.state_fips and location.county_fips:
        hpsa = await fetch_hpsa_data(
            state_fips=location.state_fips,
            county_fips=location.county_fips,
        )
        cbp = await fetch_cbp_data(
            state_fips=location.state_fips,
            county_fips=location.county_fips,
        )

        # Try tract-level CSV data first (from NPPES bulk ETL)
        npi = lookup_tract_npi(location.geoid)

        if npi:
            # Tract-level data — use ACS tract population for density
            if acs and acs.total_population:
                npi.total_population = acs.total_population
        else:
            # Fall back to NPI Registry API (city-level approximation)
            if zip_code:
                effective_postal = zip_code
                effective_city = None
            elif location.city:
                effective_postal = None
                effective_city = location.city
            else:
                effective_postal = location.postal_code
                effective_city = None
            npi = await fetch_npi_providers(
                state=state_code,
                city=effective_city,
                postal_code=effective_postal,
                tier=provider_tier.value,
            )

            # Use county population for NPI density when search scope is city-level
            if npi and effective_city:
                county_pop = await fetch_county_population(
                    location.state_fips, location.county_fips
                )
                if not county_pop and cbp and cbp.total_employees:
                    # Estimate county pop from CBP employees (~45% of pop is employed)
                    county_pop = int(cbp.total_employees / 0.45)
                if county_pop:
                    npi.total_population = county_pop
            elif npi and acs and acs.total_population:
                npi.total_population = acs.total_population

    # Population for scoring — county when NPI is city-scoped, else tract
    npi_pop = npi.total_population if npi else None
    market_pop = acs.total_population if acs else None

    # Detect non-existent tract (all primary sources returned None)
    _all_sources_empty = acs is None and places is None and svi is None
    _nonexistent_note = ""
    if _all_sources_empty:
        _nonexistent_note = (
            " Census tract may not exist in current geography"
            " (e.g., redistricted after 2020 Census)."
        )

    # Score dimensions
    demand = score_demand(acs, places, svi)
    affordability = score_affordability(acs)
    supply_gap = score_supply_gap(npi, hpsa, npi_pop)
    employer = score_employer(cbp, acs)
    competition = score_competition(npi, npi_pop)

    # Append non-existent tract note to dimension summaries
    if _nonexistent_note:
        demand.summary += _nonexistent_note
        affordability.summary += _nonexistent_note
        supply_gap.summary += _nonexistent_note

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
            npi="2026 Monthly" if npi else None,
            cbp="2021" if cbp else None,
        ),
    )


# State FIPS → abbreviation mapping (50 states + DC)
_STATE_FIPS_MAP = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA",
    "08": "CO", "09": "CT", "10": "DE", "11": "DC", "12": "FL",
    "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN",
    "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME",
    "24": "MD", "25": "MA", "26": "MI", "27": "MN", "28": "MS",
    "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH",
    "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND",
    "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI",
    "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT",
    "50": "VT", "51": "VA", "53": "WA", "54": "WV", "55": "WI",
    "56": "WY",
}


def _state_fips_to_abbrev(fips: str) -> str | None:
    return _STATE_FIPS_MAP.get(fips)
