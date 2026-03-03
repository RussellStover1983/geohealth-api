"""Tests for the geocoder service — all external calls mocked."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.geocoder import (
    GeocodedLocation,
    _enrich_tract_location,
    haversine_distance,
    resolve_location,
)


class TestResolveLocation:
    @pytest.mark.asyncio
    async def test_tract_fips_bypass(self):
        """When enrichment fails, tract_fips should fall back to stub."""
        with patch(
            "app.services.geocoder._enrich_tract_location",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await resolve_location(tract_fips="29095001100")
        assert result.geoid == "29095001100"
        assert result.state_fips == "29"
        assert result.county_fips == "095"
        assert result.tract_fips == "001100"

    @pytest.mark.asyncio
    async def test_tract_fips_enrichment(self):
        """When enrichment succeeds, tract_fips should return enriched location."""
        enriched = GeocodedLocation(
            lat=39.1, lon=-94.5,
            matched_address="Tract 29095001100",
            state_fips="29", county_fips="095",
            tract_fips="001100", geoid="29095001100",
            city="Kansas City", postal_code="64106",
        )
        with patch(
            "app.services.geocoder._enrich_tract_location",
            new_callable=AsyncMock,
            return_value=enriched,
        ):
            result = await resolve_location(tract_fips="29095001100")
        assert result.city == "Kansas City"
        assert result.postal_code == "64106"
        assert result.lat == 39.1

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


class TestEnrichTractLocation:
    """Tests for _enrich_tract_location() with mocked TIGERweb + Census APIs."""

    @pytest.mark.asyncio
    async def test_successful_enrichment(self):
        """TIGERweb returns centroid, Census returns city/ZIP."""
        tiger_response = MagicMock()
        tiger_response.status_code = 200
        tiger_response.raise_for_status = MagicMock()
        tiger_response.json.return_value = {
            "features": [
                {"attributes": {"CENTLAT": "+39.099",  "CENTLON": "-94.578"}}
            ]
        }

        census_geo_response = MagicMock()
        census_geo_response.status_code = 200
        census_geo_response.raise_for_status = MagicMock()
        census_geo_response.json.return_value = {
            "result": {
                "geographies": {
                    "Incorporated Places": [{"NAME": "Kansas City"}],
                    "County Subdivisions": [{"NAME": "Kansas City township"}],
                }
            }
        }

        zcta_response = MagicMock()
        zcta_response.status_code = 200
        zcta_response.raise_for_status = MagicMock()
        zcta_response.json.return_value = {
            "features": [
                {"attributes": {"ZCTA5": "64106"}}
            ]
        }

        async def mock_get(url, **kwargs):
            url_str = str(url).lower()
            if "mapserver/6" in url_str:
                return tiger_response
            if "mapserver/84" in url_str:
                return zcta_response
            return census_geo_response

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.geocoder.httpx.AsyncClient", return_value=mock_client):
            result = await _enrich_tract_location("29095001100")

        assert result is not None
        assert result.lat == 39.099
        assert result.lon == -94.578
        assert result.city == "Kansas City"
        assert result.postal_code == "64106"
        assert result.geoid == "29095001100"
        assert result.state_fips == "29"

    @pytest.mark.asyncio
    async def test_tigerweb_returns_no_features(self):
        """TIGERweb returns empty features → returns None."""
        tiger_response = MagicMock()
        tiger_response.status_code = 200
        tiger_response.raise_for_status = MagicMock()
        tiger_response.json.return_value = {"features": []}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=tiger_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.geocoder.httpx.AsyncClient", return_value=mock_client):
            result = await _enrich_tract_location("99999999999")

        assert result is None

    @pytest.mark.asyncio
    async def test_tigerweb_failure_returns_none(self):
        """TIGERweb HTTP error → returns None (no crash)."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("TIGERweb down"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.geocoder.httpx.AsyncClient", return_value=mock_client):
            result = await _enrich_tract_location("29095001100")

        assert result is None

    @pytest.mark.asyncio
    async def test_enrichment_without_city_or_zip(self):
        """TIGERweb works but Census geocoder has no city/ZIP data."""
        tiger_response = MagicMock()
        tiger_response.status_code = 200
        tiger_response.raise_for_status = MagicMock()
        tiger_response.json.return_value = {
            "features": [
                {"attributes": {"CENTLAT": "+38.500", "CENTLON": "-92.100"}}
            ]
        }

        empty_geo_response = MagicMock()
        empty_geo_response.status_code = 200
        empty_geo_response.raise_for_status = MagicMock()
        empty_geo_response.json.return_value = {
            "result": {"geographies": {}}
        }

        async def mock_get(url, **kwargs):
            if "tigerweb" in str(url).lower():
                return tiger_response
            return empty_geo_response

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.geocoder.httpx.AsyncClient", return_value=mock_client):
            result = await _enrich_tract_location("29095001100")

        # Still returns a location with coords even without city/ZIP
        assert result is not None
        assert result.lat == 38.5
        assert result.lon == -92.1
        assert result.city is None
        assert result.postal_code is None


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
