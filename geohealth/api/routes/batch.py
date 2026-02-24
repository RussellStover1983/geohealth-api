"""POST /v1/batch — batch address lookups."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from geohealth.api.auth import require_api_key
from geohealth.api.dependencies import get_db
from geohealth.api.schemas import BatchResponse, ErrorResponse
from geohealth.config import settings
from geohealth.services.cache import context_cache, make_cache_key
from geohealth.services.geocoder import geocode
from geohealth.services.rate_limiter import rate_limiter
from geohealth.services.tract_lookup import lookup_tract
from geohealth.services.tract_serializer import fips_fallback_dict, tract_to_dict

router = APIRouter(prefix="/v1", tags=["batch"])


class BatchRequest(BaseModel):
    addresses: list[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of street addresses to geocode and look up",
    )


@router.post(
    "/batch",
    summary="Batch address lookup",
    description=(
        "Submit multiple street addresses in a single request and receive "
        "per-address census tract data. Each address is geocoded and looked "
        "up concurrently. The request counts as **one** rate-limit hit.\n\n"
        "The maximum number of addresses per request is controlled by the "
        "`BATCH_MAX_SIZE` setting (default 50)."
    ),
    response_model=BatchResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Too many addresses"},
        401: {"model": ErrorResponse, "description": "Missing API key"},
        403: {"model": ErrorResponse, "description": "Invalid API key"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    },
)
async def post_batch(
    body: BatchRequest,
    response: Response,
    session: AsyncSession = Depends(get_db),
    api_key: str = Depends(require_api_key),
):
    """Geocode and look up tract data for multiple addresses in one request."""

    # --- rate limit (counts as 1 request) ------------------------------------
    allowed, rl_headers = rate_limiter.is_allowed(api_key)
    for hdr, val in rl_headers.items():
        response.headers[hdr] = val
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded", headers=rl_headers)

    # --- validate against configurable max -----------------------------------
    if len(body.addresses) > settings.batch_max_size:
        raise HTTPException(
            status_code=400,
            detail=f"Too many addresses: {len(body.addresses)} exceeds max of {settings.batch_max_size}",
        )

    # --- process each address concurrently -----------------------------------
    async def _process(addr: str) -> dict:
        try:
            location = await geocode(addr)
            cache_key = make_cache_key(location.lat, location.lng)
            cached = context_cache.get(cache_key)
            if cached is not None:
                tract_data = cached
            else:
                tract = await lookup_tract(
                    location.lat,
                    location.lng,
                    session,
                    state_fips=location.state_fips,
                    county_fips=location.county_fips,
                    tract_fips=location.tract_fips,
                )
                tract_data = tract_to_dict(tract) if tract else fips_fallback_dict(location)
                if tract_data is not None:
                    context_cache.set(cache_key, tract_data)

            return {
                "address": addr,
                "status": "ok",
                "location": {
                    "lat": location.lat,
                    "lng": location.lng,
                    "matched_address": location.matched_address,
                },
                "tract": tract_data,
                "error": None,
            }
        except Exception as exc:
            return {
                "address": addr,
                "status": "error",
                "location": None,
                "tract": None,
                "error": str(exc),
            }

    results = await asyncio.gather(*[_process(addr) for addr in body.addresses])

    succeeded = sum(1 for r in results if r["status"] == "ok")
    failed = sum(1 for r in results if r["status"] == "error")

    return {
        "total": len(results),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
    }
