"""Supply detail endpoint — /api/v1/market-fit/supply."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from app.models.enums import ProviderTier
from app.models.response import (
    DataVintage,
    ErrorResponse,
    ResolvedLocation,
    SupplyDetailResponse,
)
from app.services.census_acs import fetch_acs_data
from app.services.geocoder import resolve_location
from app.services.hrsa_hpsa import fetch_hpsa_data
from app.services.npi_registry import fetch_npi_providers
from app.services.scoring import score_supply_gap
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["supply"])

# Reuse from market_fit router
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


@router.get(
    "/market-fit/supply",
    response_model=SupplyDetailResponse,
    summary="Provider supply analysis",
    description=(
        "Detailed provider supply analysis including PCP counts, HPSA "
        "designations, and competing facility presence."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Invalid input"},
    },
)
async def get_supply_detail(
    address: str | None = Query(None, description="Street address"),
    lat: float | None = Query(None, description="Latitude", ge=-90, le=90),
    lon: float | None = Query(None, description="Longitude", ge=-180, le=180),
    zip_code: str | None = Query(None, description="5-digit ZIP code"),
    tract_fips: str | None = Query(None, description="11-digit tract FIPS"),
    radius_miles: float = Query(5.0, description="Market area radius", gt=0, le=50),
    provider_tier: ProviderTier = Query(
        ProviderTier.TIER1, description="NPI taxonomy tier"
    ),
) -> SupplyDetailResponse:
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

    # Fetch population data
    acs = await fetch_acs_data(location.geoid)
    population = acs.total_population if acs else None

    # Fetch NPI + HPSA data
    state_code = _STATE_FIPS_MAP.get(location.state_fips or "")
    npi = None
    hpsa = None

    if state_code and location.state_fips and location.county_fips:
        effective_postal = zip_code or location.postal_code
        effective_city = location.city if not effective_postal else None
        npi = await fetch_npi_providers(
            state=state_code,
            city=effective_city,
            postal_code=effective_postal,
            tier=provider_tier.value,
        )
        if npi and population:
            npi.total_population = population

        hpsa = await fetch_hpsa_data(
            state_fips=location.state_fips,
            county_fips=location.county_fips,
        )

    supply_score = score_supply_gap(npi, hpsa, population)

    return SupplyDetailResponse(
        location=ResolvedLocation(
            input=input_desc,
            resolved_lat=location.lat,
            resolved_lon=location.lon,
            primary_tract_fips=location.geoid,
            tracts_in_radius=[location.geoid],
            radius_miles=radius_miles,
            market_population=population,
        ),
        pcp_count=npi.pcp_count if npi else 0,
        pcp_per_100k=npi.pcp_per_100k if npi else None,
        is_hpsa=hpsa.is_hpsa if hpsa else False,
        hpsa_score=hpsa.hpsa_score if hpsa else None,
        hpsa_type=hpsa.hpsa_type if hpsa else None,
        fqhc_count=npi.fqhc_count if npi else 0,
        urgent_care_count=npi.urgent_care_count if npi else 0,
        rural_health_clinic_count=npi.rural_health_clinic_count if npi else 0,
        supply_gap_score=supply_score,
        data_vintage=DataVintage(
            census_acs=f"{settings.acs_year} 5-Year" if acs else None,
            npi="2026 Monthly" if npi else None,
        ),
    )
