"""Tests for the geocoder service — all external calls mocked."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.geocoder import (
    GeocodedLocation,
    haversine_distance,
    resolve_location,
)


class TestResolveLocation:
    @pytest.mark.asyncio
    async def test_tract_fips_bypass(self):
        """Providing a tract_fips should bypass geocoding entirely."""
        result = await resolve_location(tract_fips="29095001100")
        assert result.geoid == "29095001100"
        assert result.state_fips == "29"
        assert result.county_fips == "095"
        assert result.tract_fips == "001100"

    @pytest.mark.asyncio
    async def test_no_input_raises(self):
        with pytest.raises(ValueError, match="At least one location"):
            await resolve_location()

    @pytest.mark.asyncio
    async def test_address_geocoding(self):
        mock_result = GeocodedLocation(
            lat=39.0997,
            lon=-94.5786,
            matched_address="123 Main St, Kansas City, MO",
            state_fips="29",
            county_fips="095",
            tract_fips="001100",
            geoid="29095001100",
        )
        with patch("app.services.geocoder.geocode_address", new_callable=AsyncMock) as mock:
            mock.return_value = mock_result
            result = await resolve_location(address="123 Main St, Kansas City, MO")
            assert result.geoid == "29095001100"
            mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_lat_lon_geocoding(self):
        mock_result = GeocodedLocation(
            lat=39.0997,
            lon=-94.5786,
            matched_address="(39.0997, -94.5786)",
            state_fips="29",
            county_fips="095",
            tract_fips="001100",
            geoid="29095001100",
        )
        with patch("app.services.geocoder.geocode_lat_lon", new_callable=AsyncMock) as mock:
            mock.return_value = mock_result
            result = await resolve_location(lat=39.0997, lon=-94.5786)
            assert result.lat == 39.0997
            mock.assert_called_once()


class TestHaversineDistance:
    def test_same_point(self):
        assert haversine_distance(39.1, -94.5, 39.1, -94.5) == 0.0

    def test_known_distance(self):
        # KC to St. Louis is roughly 250 miles
        dist = haversine_distance(39.0997, -94.5786, 38.6270, -90.1994)
        assert 230 < dist < 270

    def test_short_distance(self):
        # ~1 degree latitude is about 69 miles
        dist = haversine_distance(39.0, -94.5, 40.0, -94.5)
        assert 68 < dist < 70
