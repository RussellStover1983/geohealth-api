from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel

from geohealth.config import settings
from geohealth.services.metrics import metrics

logger = logging.getLogger(__name__)


class GeocodedLocation(BaseModel):
    lat: float
    lng: float
    matched_address: str
    state_fips: str | None = None
    county_fips: str | None = None
    tract_fips: str | None = None


async def geocode(address: str) -> GeocodedLocation:
    """Geocode an address. Tries Census Bureau first, falls back to Nominatim."""
    try:
        result = await _geocode_census(address)
        metrics.inc_geocoder("census")
        return result
    except Exception:
        logger.warning("Census geocoder failed for %r, falling back to Nominatim", address)
    try:
        result = await _geocode_nominatim(address)
        metrics.inc_geocoder("nominatim")
        return result
    except Exception:
        metrics.inc_geocoder("failure")
        raise


async def _geocode_census(address: str) -> GeocodedLocation:
    params = {
        "address": address,
        "benchmark": "Public_AR_Current",
        "vintage": "Current_Current",
        "format": "json",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(settings.census_geocoder_url, params=params)
        resp.raise_for_status()

    data = resp.json()
    matches = data.get("result", {}).get("addressMatches", [])
    if not matches:
        raise ValueError(f"No matches from Census geocoder for: {address}")

    match = matches[0]
    coords = match["coordinates"]
    geographies = match.get("geographies", {})

    # Extract FIPS codes from the Census Tracts geography layer
    tract_info = geographies.get("Census Tracts", [{}])[0] if geographies.get("Census Tracts") else {}

    return GeocodedLocation(
        lat=coords["y"],
        lng=coords["x"],
        matched_address=match["matchedAddress"],
        state_fips=tract_info.get("STATE"),
        county_fips=tract_info.get("COUNTY"),
        tract_fips=tract_info.get("TRACT"),
    )


async def _geocode_nominatim(address: str) -> GeocodedLocation:
    params = {
        "q": address,
        "format": "json",
        "limit": 1,
    }
    headers = {"User-Agent": "geohealth-api/0.1 (health-research)"}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(settings.nominatim_url, params=params, headers=headers)
        resp.raise_for_status()

    results = resp.json()
    if not results:
        raise ValueError(f"No results from Nominatim for: {address}")

    hit = results[0]
    return GeocodedLocation(
        lat=float(hit["lat"]),
        lng=float(hit["lon"]),
        matched_address=hit.get("display_name", address),
    )
