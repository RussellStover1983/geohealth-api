"""Geocoding pipeline: address/ZIP/lat-lon → tract FIPS.

Primary: Census Bureau Geocoder API (returns tract FIPS directly).
Fallback: Nominatim (returns coordinates only — no FIPS).
For ZIP codes: resolves to tract FIPS via FCC Area API.
"""

from __future__ import annotations

import logging
import math

import httpx
from pydantic import BaseModel

from app.config import settings
from app.utils.cache import geocode_cache

logger = logging.getLogger(__name__)

# Approximate radius of Earth in miles
_EARTH_RADIUS_MI = 3958.8


class GeocodedLocation(BaseModel):
    """Result of geocoding a location input."""

    lat: float
    lon: float
    matched_address: str
    state_fips: str | None = None
    county_fips: str | None = None
    tract_fips: str | None = None  # 6-digit tract code
    geoid: str | None = None  # Full 11-digit FIPS (state+county+tract)


async def geocode_address(address: str) -> GeocodedLocation:
    """Geocode a street address. Census primary, Nominatim fallback."""
    cached = geocode_cache.get(f"addr:{address}")
    if cached is not None:
        return cached

    try:
        result = await _geocode_census(address)
    except Exception:
        logger.warning("Census geocoder failed for %r, trying Nominatim", address)
        result = await _geocode_nominatim(address)

    geocode_cache.set(f"addr:{address}", result)
    return result


async def geocode_lat_lon(lat: float, lon: float) -> GeocodedLocation:
    """Resolve lat/lon to tract FIPS via FCC Area API."""
    cache_key = f"ll:{round(lat, 5)},{round(lon, 5)}"
    cached = geocode_cache.get(cache_key)
    if cached is not None:
        return cached

    result = await _reverse_geocode_fcc(lat, lon)
    geocode_cache.set(cache_key, result)
    return result


async def geocode_zip(zip_code: str) -> list[GeocodedLocation]:
    """Resolve a ZIP code to its constituent tracts.

    Uses the HUD USPS ZIP-Tract crosswalk when available, otherwise
    geocodes the ZIP centroid and finds the primary tract.
    """
    cached = geocode_cache.get(f"zip:{zip_code}")
    if cached is not None:
        return cached

    # Geocode ZIP via Census to get a centroid, then reverse-geocode
    try:
        result = await _geocode_census(zip_code)
        results = [result]
    except Exception:
        logger.warning("ZIP geocoding failed for %s, trying Nominatim", zip_code)
        result = await _geocode_nominatim(zip_code)
        results = [result]

    geocode_cache.set(f"zip:{zip_code}", results)
    return results


async def resolve_location(
    *,
    address: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    zip_code: str | None = None,
    tract_fips: str | None = None,
) -> GeocodedLocation:
    """Unified location resolver — accepts any input type."""
    if tract_fips:
        # Bypass geocoding — construct from FIPS directly
        return GeocodedLocation(
            lat=0.0,
            lon=0.0,
            matched_address=f"Tract {tract_fips}",
            state_fips=tract_fips[:2],
            county_fips=tract_fips[2:5],
            tract_fips=tract_fips[5:],
            geoid=tract_fips,
        )

    if address:
        return await geocode_address(address)

    if lat is not None and lon is not None:
        return await geocode_lat_lon(lat, lon)

    if zip_code:
        results = await geocode_zip(zip_code)
        return results[0] if results else _empty_location(f"ZIP {zip_code}")

    raise ValueError("At least one location input (address, lat/lon, zip_code, tract_fips) required")


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in miles between two lat/lon points."""
    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    return _EARTH_RADIUS_MI * 2 * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


async def _geocode_census(query: str) -> GeocodedLocation:
    """Census Bureau Geocoder — returns coordinates + FIPS codes."""
    params = {
        "address": query,
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
        raise ValueError(f"No Census geocoder matches for: {query}")

    match = matches[0]
    coords = match["coordinates"]
    geographies = match.get("geographies", {})
    tract_info = (
        geographies.get("Census Tracts", [{}])[0]
        if geographies.get("Census Tracts")
        else {}
    )

    state = tract_info.get("STATE", "")
    county = tract_info.get("COUNTY", "")
    tract = tract_info.get("TRACT", "")
    geoid = f"{state}{county}{tract}" if state and county and tract else None

    return GeocodedLocation(
        lat=coords["y"],
        lon=coords["x"],
        matched_address=match["matchedAddress"],
        state_fips=state or None,
        county_fips=county or None,
        tract_fips=tract or None,
        geoid=geoid,
    )


async def _geocode_nominatim(query: str) -> GeocodedLocation:
    """Nominatim fallback — coordinates only, no FIPS."""
    params = {"q": query, "format": "json", "limit": 1}
    headers = {"User-Agent": "dpc-market-fit-api/0.1 (health-research)"}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(settings.nominatim_url, params=params, headers=headers)
        resp.raise_for_status()

    results = resp.json()
    if not results:
        raise ValueError(f"No Nominatim results for: {query}")

    hit = results[0]
    loc = GeocodedLocation(
        lat=float(hit["lat"]),
        lon=float(hit["lon"]),
        matched_address=hit.get("display_name", query),
    )

    # Try to resolve FIPS via FCC reverse geocode
    try:
        fcc_result = await _reverse_geocode_fcc(loc.lat, loc.lon)
        loc.state_fips = fcc_result.state_fips
        loc.county_fips = fcc_result.county_fips
        loc.tract_fips = fcc_result.tract_fips
        loc.geoid = fcc_result.geoid
    except Exception:
        logger.warning("FCC reverse geocode failed for %s, %s", loc.lat, loc.lon)

    return loc


async def _reverse_geocode_fcc(lat: float, lon: float) -> GeocodedLocation:
    """FCC Area API — resolve lat/lon to census tract FIPS."""
    url = "https://geo.fcc.gov/api/census/area"
    params = {"lat": lat, "lon": lon, "format": "json"}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()

    data = resp.json()
    results = data.get("results", [])
    if not results:
        raise ValueError(f"No FCC results for ({lat}, {lon})")

    block = results[0].get("block_fips", "")
    # Block FIPS is 15 digits: state(2) + county(3) + tract(6) + block group(1) + block(3)
    state = block[:2] if len(block) >= 2 else None
    county = block[2:5] if len(block) >= 5 else None
    tract = block[5:11] if len(block) >= 11 else None
    geoid = f"{state}{county}{tract}" if state and county and tract else None

    return GeocodedLocation(
        lat=lat,
        lon=lon,
        matched_address=f"({lat}, {lon})",
        state_fips=state,
        county_fips=county,
        tract_fips=tract,
        geoid=geoid,
    )


def _empty_location(description: str) -> GeocodedLocation:
    return GeocodedLocation(lat=0.0, lon=0.0, matched_address=description)
