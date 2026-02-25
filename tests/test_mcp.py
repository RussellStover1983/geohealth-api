"""Tests for the GeoHealth MCP server tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

mcp_sdk = pytest.importorskip("mcp", reason="mcp package not installed")

from geohealth.api.schemas import (  # noqa: E402
    BatchResponse,
    BatchResultItem,
    BatchResultLocation,
    CompareResponse,
    CompareSide,
    CompareValues,
    CompareDifferences,
    ContextResponse,
    DictionaryCategory,
    DictionaryResponse,
    FieldDefinition,
    LocationModel,
    NearbyCenter,
    NearbyResponse,
    NearbyTract,
    StatsResponse,
    StateCount,
    TractDataModel,
)
from geohealth.mcp.server import (  # noqa: E402
    lookup_health_context,
    batch_health_lookup,
    find_nearby_tracts,
    compare_tracts,
    get_data_dictionary,
    get_tract_statistics,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PATCH_CLIENT = "geohealth.mcp.server._client"


# ---------------------------------------------------------------------------
# lookup_health_context
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lookup_by_address():
    """lookup_health_context delegates to client.context and returns dict."""
    mc = AsyncMock()
    mc.context.return_value = ContextResponse(
        location=LocationModel(lat=44.97, lng=-93.26, matched_address="123 Main St"),
        tract=TractDataModel(
            geoid="27053026200", state_fips="27",
            county_fips="053", tract_code="026200",
        ),
    )
    with patch(_PATCH_CLIENT, mc):
        result = await lookup_health_context(address="123 Main St")
    mc.context.assert_called_once_with(
        address="123 Main St", lat=None, lng=None, narrative=False,
    )
    assert result["location"]["lat"] == 44.97
    assert result["tract"]["geoid"] == "27053026200"


@pytest.mark.asyncio
async def test_lookup_by_coords_with_narrative():
    """lookup_health_context passes lat/lng and narrative flag."""
    mc = AsyncMock()
    mc.context.return_value = ContextResponse(
        location=LocationModel(lat=44.97, lng=-93.26, matched_address="Matched"),
        tract=TractDataModel(
            geoid="27053026200", state_fips="27",
            county_fips="053", tract_code="026200",
        ),
        narrative="AI summary here.",
    )
    with patch(_PATCH_CLIENT, mc):
        result = await lookup_health_context(lat=44.97, lng=-93.26, narrative=True)
    mc.context.assert_called_once_with(
        address=None, lat=44.97, lng=-93.26, narrative=True,
    )
    assert result["narrative"] == "AI summary here."


# ---------------------------------------------------------------------------
# batch_health_lookup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_batch_lookup():
    """batch_health_lookup delegates to client.batch."""
    mc = AsyncMock()
    mc.batch.return_value = BatchResponse(
        total=1, succeeded=1, failed=0,
        results=[BatchResultItem(
            address="123 Main St", status="ok",
            location=BatchResultLocation(
                lat=44.97, lng=-93.26, matched_address="123 Main St",
            ),
            tract=TractDataModel(
                geoid="27053026200", state_fips="27",
                county_fips="053", tract_code="026200",
            ),
        )],
    )
    with patch(_PATCH_CLIENT, mc):
        result = await batch_health_lookup(addresses=["123 Main St"])
    mc.batch.assert_called_once_with(["123 Main St"])
    assert result["total"] == 1
    assert result["results"][0]["tract"]["geoid"] == "27053026200"


# ---------------------------------------------------------------------------
# find_nearby_tracts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_find_nearby():
    """find_nearby_tracts delegates to client.nearby."""
    mc = AsyncMock()
    mc.nearby.return_value = NearbyResponse(
        center=NearbyCenter(lat=44.97, lng=-93.26),
        radius_miles=5.0, count=1, total=1, offset=0, limit=25,
        tracts=[NearbyTract(
            geoid="27053026200", distance_miles=1.2,
            total_population=4500, sdoh_index=0.4,
        )],
    )
    with patch(_PATCH_CLIENT, mc):
        result = await find_nearby_tracts(lat=44.97, lng=-93.26, radius=5.0)
    mc.nearby.assert_called_once_with(lat=44.97, lng=-93.26, radius=5.0, limit=25)
    assert result["tracts"][0]["distance_miles"] == 1.2


# ---------------------------------------------------------------------------
# compare_tracts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compare():
    """compare_tracts delegates to client.compare."""
    mc = AsyncMock()
    mc.compare.return_value = CompareResponse(
        a=CompareSide(
            type="tract", geoid="27053026200", label="Tract 262",
            values=CompareValues(poverty_rate=11.0, sdoh_index=0.4),
        ),
        b=CompareSide(
            type="state_average", label="State 27 average",
            values=CompareValues(poverty_rate=13.0, sdoh_index=0.5),
        ),
        differences=CompareDifferences(poverty_rate=-2.0, sdoh_index=-0.1),
    )
    with patch(_PATCH_CLIENT, mc):
        result = await compare_tracts(geoid1="27053026200", compare_to="state")
    mc.compare.assert_called_once_with(
        geoid1="27053026200", geoid2=None, compare_to="state",
    )
    assert result["differences"]["poverty_rate"] == -2.0


# ---------------------------------------------------------------------------
# get_data_dictionary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_dictionary():
    """get_data_dictionary delegates to client.dictionary."""
    mc = AsyncMock()
    mc.dictionary.return_value = DictionaryResponse(
        total_fields=1,
        categories=[DictionaryCategory(
            category="demographics",
            description="ACS demographics",
            source="ACS",
            fields=[FieldDefinition(
                name="poverty_rate", type="float", source="ACS",
                category="demographics",
                description="Poverty rate",
                clinical_relevance="Important for clinical risk.",
            )],
        )],
    )
    with patch(_PATCH_CLIENT, mc):
        result = await get_data_dictionary(category="demographics")
    mc.dictionary.assert_called_once_with(category="demographics")
    assert result["total_fields"] == 1
    assert result["categories"][0]["fields"][0]["name"] == "poverty_rate"


# ---------------------------------------------------------------------------
# get_tract_statistics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_statistics():
    """get_tract_statistics delegates to client.stats."""
    mc = AsyncMock()
    mc.stats.return_value = StatsResponse(
        total_states=1, total_tracts=1505, offset=0, limit=50,
        states=[StateCount(state_fips="27", tract_count=1505)],
    )
    with patch(_PATCH_CLIENT, mc):
        result = await get_tract_statistics()
    mc.stats.assert_called_once()
    assert result["total_tracts"] == 1505
