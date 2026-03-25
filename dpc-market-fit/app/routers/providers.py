"""Individual provider lookup endpoint — returns GeoJSON FeatureCollection."""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.services.provider_lookup import lookup_providers

router = APIRouter(prefix="/api/v1", tags=["providers"])


@router.get(
    "/providers",
    summary="Individual providers for a census tract",
    description=(
        "Returns a GeoJSON FeatureCollection of individual primary care "
        "providers and facilities assigned to a census tract. Each feature "
        "is a Point with provider name, type, taxonomy, and address."
    ),
    responses={
        200: {"description": "GeoJSON FeatureCollection of provider points"},
        400: {"description": "Missing tract_fips parameter"},
    },
)
async def get_providers(
    tract_fips: str = Query(
        ..., description="11-digit census tract FIPS code", min_length=11, max_length=11
    ),
    type: str | None = Query(
        None,
        description="Filter by provider type: PCP, FQHC, URGENT_CARE, RURAL_HEALTH, "
        "PRIMARY_CARE_CLINIC, COMMUNITY_HEALTH_CENTER",
    ),
) -> JSONResponse:
    """Return individual providers as GeoJSON FeatureCollection."""
    providers = lookup_providers(tract_fips, provider_type=type)

    features = []
    for p in providers:
        full_address = ", ".join(
            part for part in [p.address, p.city, f"{p.state} {p.zip_code}"] if part
        )
        display_name = p.name
        if p.credential:
            display_name = f"{p.name}, {p.credential}"

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [p.lon, p.lat],
            },
            "properties": {
                "npi": p.npi,
                "name": display_name,
                "provider_type": p.provider_type,
                "taxonomy_code": p.taxonomy_code,
                "address": full_address,
            },
        })

    return JSONResponse(
        content={
            "type": "FeatureCollection",
            "features": features,
        },
        headers={"Cache-Control": "public, max-age=300"},
    )
