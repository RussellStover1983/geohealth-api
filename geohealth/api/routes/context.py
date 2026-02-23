from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from geohealth.api.auth import require_api_key
from geohealth.api.dependencies import get_db
from geohealth.services.cache import context_cache, make_cache_key
from geohealth.services.geocoder import GeocodedLocation, geocode
from geohealth.services.narrator import generate_narrative
from geohealth.services.rate_limiter import rate_limiter
from geohealth.services.tract_lookup import lookup_tract
from geohealth.services.tract_serializer import fips_fallback_dict, tract_to_dict

router = APIRouter(prefix="/v1", tags=["context"])


@router.get("/context")
async def get_context(
    response: Response,
    address: str | None = Query(None, description="Street address to geocode"),
    lat: float | None = Query(None, description="Latitude (if no address)"),
    lng: float | None = Query(None, description="Longitude (if no address)"),
    narrative: bool = Query(False, description="Generate LLM narrative summary"),
    format: str = Query("json", description="Response format"),
    context: str = Query("full", description="Context sections to include"),
    session: AsyncSession = Depends(get_db),
    api_key: str = Depends(require_api_key),
):
    """Return geographic health context for a location."""

    # --- rate limit ----------------------------------------------------------
    allowed, rl_headers = rate_limiter.is_allowed(api_key)
    for hdr, val in rl_headers.items():
        response.headers[hdr] = val
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded", headers=rl_headers)

    # --- resolve location ---------------------------------------------------
    if address:
        location = await geocode(address)
    elif lat is not None and lng is not None:
        location = GeocodedLocation(
            lat=lat, lng=lng, matched_address=f"{lat},{lng}"
        )
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide either 'address' or both 'lat' and 'lng'.",
        )

    # --- cache check ---------------------------------------------------------
    cache_key = make_cache_key(location.lat, location.lng)
    cached = context_cache.get(cache_key)
    if cached is not None:
        tract_data = cached
    else:
        # --- tract lookup ----------------------------------------------------
        tract = await lookup_tract(
            location.lat,
            location.lng,
            session,
            state_fips=location.state_fips,
            county_fips=location.county_fips,
            tract_fips=location.tract_fips,
        )

        tract_data = None
        if tract:
            tract_data = tract_to_dict(tract)
        else:
            tract_data = fips_fallback_dict(location)

        if tract_data is not None:
            context_cache.set(cache_key, tract_data)

    # --- narrative generation (opt-in) ----------------------------------------
    narrative_text = None
    if narrative and tract_data:
        narrative_text = await generate_narrative(tract_data)

    return {
        "location": {
            "lat": location.lat,
            "lng": location.lng,
            "matched_address": location.matched_address,
        },
        "tract": tract_data,
        "narrative": narrative_text,
        "data": tract_data,
    }
