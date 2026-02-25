"""FastMCP server wrapping the GeoHealth API as tools for Claude agents."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.fastmcp import FastMCP

from geohealth.sdk.client import AsyncGeoHealthClient


_client: AsyncGeoHealthClient | None = None


@asynccontextmanager
async def _lifespan(server: FastMCP):
    """Create and tear down the shared API client."""
    global _client  # noqa: PLW0603
    base_url = os.environ.get(
        "GEOHEALTH_BASE_URL",
        "https://geohealth-api-production.up.railway.app",
    )
    api_key = os.environ.get("GEOHEALTH_API_KEY", "")
    _client = AsyncGeoHealthClient(
        base_url=base_url,
        api_key=api_key or None,
        timeout=30.0,
    )
    yield
    await _client.close()
    _client = None


mcp = FastMCP(
    name="GeoHealth",
    instructions=(
        "GeoHealth provides census-tract-level geographic health data for any "
        "US address or coordinates. It returns demographics (ACS), social "
        "vulnerability (CDC SVI), health outcomes (CDC PLACES), and a composite "
        "SDOH index. Use lookup_health_context as the primary tool. Use "
        "get_data_dictionary to understand what fields are available and their "
        "clinical significance before interpreting results."
    ),
    lifespan=_lifespan,
)


def _get_client() -> AsyncGeoHealthClient:
    assert _client is not None, "MCP server not started — client unavailable"
    return _client


@mcp.tool()
async def lookup_health_context(
    address: str | None = None,
    lat: float | None = None,
    lng: float | None = None,
    narrative: bool = False,
) -> dict[str, Any]:
    """Look up census-tract health context for a US location.

    Given a street address OR lat/lng coordinates, returns census tract
    demographics (population, income, poverty, insurance, unemployment, age),
    CDC Social Vulnerability Index theme percentiles, CDC PLACES health
    outcome prevalence measures, and a composite SDOH index.

    Use this when you need to understand the social determinants of health
    for a patient's neighborhood. The sdoh_index (0-1, higher = more
    vulnerable) is the best single triage metric. Poverty rate above 20%
    and SVI percentile above 0.75 both indicate high-vulnerability areas.

    Args:
        address: US street address (e.g., "123 Main St, Minneapolis, MN 55401").
                 Required if lat/lng are not provided.
        lat: Latitude (-90 to 90). Required if address is not provided.
        lng: Longitude (-180 to 180). Required if address is not provided.
        narrative: If true, includes an AI-generated clinical summary of the
                   tract's health context.

    Returns:
        Dict with location (geocoded coordinates), tract (all health data
        fields), and optionally a narrative string.
    """
    client = _get_client()
    result = await client.context(
        address=address, lat=lat, lng=lng, narrative=narrative,
    )
    return result.model_dump()


@mcp.tool()
async def batch_health_lookup(addresses: list[str]) -> dict[str, Any]:
    """Look up health context for multiple US addresses at once.

    Accepts up to 50 addresses and returns per-address results. Each result
    includes the same tract data as lookup_health_context. Failed lookups
    include an error message rather than tract data.

    Use this when you have a list of patient addresses and need SDOH context
    for each one efficiently.

    Args:
        addresses: List of US street addresses (max 50).

    Returns:
        Dict with total, succeeded, failed counts and a results array with
        per-address status, location, tract data, and any error messages.
    """
    client = _get_client()
    result = await client.batch(addresses)
    return result.model_dump()


@mcp.tool()
async def find_nearby_tracts(
    lat: float,
    lng: float,
    radius: float = 5.0,
    limit: int = 25,
) -> dict[str, Any]:
    """Find census tracts near a location, sorted by distance.

    Returns tracts within the specified radius with key demographic and
    health metrics for each. Use this to understand the health landscape
    around a facility, clinic, or patient concentration.

    Args:
        lat: Latitude of the center point.
        lng: Longitude of the center point.
        radius: Search radius in miles (default 5, max 50).
        limit: Maximum number of tracts to return (default 25, max 100).

    Returns:
        Dict with center point, radius, total matching tracts, and an array
        of nearby tracts with distance_miles, demographics, and sdoh_index.
    """
    client = _get_client()
    result = await client.nearby(lat=lat, lng=lng, radius=radius, limit=limit)
    return result.model_dump()


@mcp.tool()
async def compare_tracts(
    geoid1: str,
    geoid2: str | None = None,
    compare_to: str | None = None,
) -> dict[str, Any]:
    """Compare two census tracts or a tract against state/national averages.

    Provide two GEOIDs to compare tracts directly, or one GEOID with
    compare_to="state" or compare_to="national" to compare against averages.
    Returns side-by-side values and computed differences.

    Use this to contextualize a tract — is its poverty rate higher or lower
    than the state average? How does one neighborhood compare to another?

    Args:
        geoid1: 11-digit GEOID of the first census tract.
        geoid2: 11-digit GEOID of the second tract (for direct comparison).
        compare_to: "state" or "national" (for average comparison).

    Returns:
        Dict with side A values, side B values, and differences (A minus B)
        for population, income, poverty, uninsured, unemployment, age, and
        sdoh_index.
    """
    client = _get_client()
    result = await client.compare(
        geoid1=geoid1, geoid2=geoid2, compare_to=compare_to,
    )
    return result.model_dump()


@mcp.tool()
async def get_data_dictionary(category: str | None = None) -> dict[str, Any]:
    """Get field definitions with clinical interpretation guidance.

    Returns structured metadata about every data field the API provides,
    including the data source, clinical relevance, typical ranges, and
    interpretation thresholds.

    Call this FIRST when you need to understand what health data is available
    and what the values mean clinically before interpreting results from
    other tools.

    Args:
        category: Optional filter — "demographics", "vulnerability",
                  "health_outcomes", or "composite". Omit for all fields.

    Returns:
        Dict with total_fields count and categories array, each containing
        field definitions with name, type, source, description,
        clinical_relevance, unit, typical_range, and example_value.
    """
    client = _get_client()
    result = await client.dictionary(category=category)
    return result.model_dump()


@mcp.tool()
async def get_tract_statistics() -> dict[str, Any]:
    """Get data coverage statistics — which states have loaded tract data.

    Returns the total number of states and census tracts loaded, plus a
    per-state breakdown. Use this to verify data availability before
    querying for a specific state or region.

    Returns:
        Dict with total_states, total_tracts, and a states array with
        state_fips and tract_count for each loaded state.
    """
    client = _get_client()
    result = await client.stats()
    return result.model_dump()
