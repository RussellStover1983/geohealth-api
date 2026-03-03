"""Tests for data source fallback mechanisms.

Verifies that when primary data sources fail (Socrata, Census API, HRSA API),
the services correctly fall back to secondary sources (GeoHealth API, CSV).
"""

from __future__ import annotations

import csv
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.cdc_svi import _fetch_svi_from_geohealth, fetch_svi_data
from app.services.census_acs import _fetch_acs_from_geohealth, fetch_acs_data
from app.services.cdc_places import (
    _fetch_places_from_geohealth,
    fetch_places_data,
)
from app.services.hrsa_hpsa import (
    _load_hpsa_csv,
    _lookup_hpsa_csv,
    fetch_hpsa_data,
)


# ---------------------------------------------------------------------------
# SVI Fallback Tests
# ---------------------------------------------------------------------------


class TestSVIGeoHealthFallback:
    """Test SVI fallback to GeoHealth API when Socrata fails."""

    @pytest.fixture(autouse=True)
    def _clear_caches(self):
        from app.utils.cache import svi_cache
        svi_cache.clear()

    @pytest.mark.asyncio
    async def test_geohealth_fallback_returns_svi_data(self):
        """GeoHealth API returns valid SVI themes."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "geoid": "29095001100",
            "svi_themes": {
                "rpl_theme1": 0.65,
                "rpl_theme2": 0.42,
                "rpl_theme3": 0.38,
                "rpl_theme4": 0.55,
                "rpl_themes": 0.51,
            },
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.cdc_svi.httpx.AsyncClient", return_value=mock_client):
            result = await _fetch_svi_from_geohealth("29095001100")

        assert result is not None
        assert result.socioeconomic == 0.65
        assert result.composite == 0.51

    @pytest.mark.asyncio
    async def test_geohealth_fallback_returns_none_on_404(self):
        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.cdc_svi.httpx.AsyncClient", return_value=mock_client):
            result = await _fetch_svi_from_geohealth("99999999999")

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_svi_falls_back_when_socrata_fails(self):
        """When Socrata raises an error, we should try GeoHealth API."""
        socrata_error = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=MagicMock(status_code=404)
        )

        geohealth_response = MagicMock()
        geohealth_response.status_code = 200
        geohealth_response.json.return_value = {
            "svi_themes": {
                "rpl_theme1": 0.7,
                "rpl_theme2": 0.5,
                "rpl_theme3": 0.4,
                "rpl_theme4": 0.3,
                "rpl_themes": 0.5,
            },
        }

        call_count = 0

        async def mock_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if "data.cdc.gov" in str(url):
                raise socrata_error
            return geohealth_response

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.cdc_svi.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_svi_data("29095001100")

        assert result is not None
        assert result.socioeconomic == 0.7

    @pytest.mark.asyncio
    async def test_fetch_svi_falls_back_when_socrata_returns_empty(self):
        """When Socrata returns empty array, we should try GeoHealth API."""
        socrata_response = MagicMock()
        socrata_response.status_code = 200
        socrata_response.raise_for_status = MagicMock()
        socrata_response.json.return_value = []

        geohealth_response = MagicMock()
        geohealth_response.status_code = 200
        geohealth_response.json.return_value = {
            "svi_themes": {
                "rpl_theme1": 0.8,
                "rpl_themes": 0.6,
            },
        }

        async def mock_get(url, **kwargs):
            if "data.cdc.gov" in str(url):
                return socrata_response
            return geohealth_response

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.cdc_svi.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_svi_data("29095001100")

        assert result is not None
        assert result.socioeconomic == 0.8


# ---------------------------------------------------------------------------
# HPSA CSV Lookup Tests
# ---------------------------------------------------------------------------


class TestHPSACSVLookup:
    """Test HPSA embedded CSV lookup."""

    @pytest.fixture(autouse=True)
    def _clear_caches_and_index(self):
        from app.utils.cache import hpsa_cache
        hpsa_cache.clear()
        # Reset the module-level index
        import app.services.hrsa_hpsa as hpsa_mod
        hpsa_mod._HPSA_INDEX = None

    def test_csv_file_exists(self):
        csv_path = Path(__file__).parent.parent / "app" / "data" / "hpsa_primary_care.csv"
        assert csv_path.exists(), f"HPSA CSV not found at {csv_path}"

    def test_csv_has_expected_columns(self):
        csv_path = Path(__file__).parent.parent / "app" / "data" / "hpsa_primary_care.csv"
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            row = next(reader)
        assert "common_county_fips" in row
        assert "hpsa_score" in row
        assert "hpsa_name" in row

    def test_load_hpsa_csv_populates_index(self):
        index = _load_hpsa_csv()
        assert len(index) > 0
        # Should have entries for Jackson County, MO (29095)
        assert "29095" in index

    def test_lookup_known_county(self):
        """Jackson County, MO (29095) should have HPSA designations."""
        result = _lookup_hpsa_csv("29095")
        assert result is not None
        assert result.is_hpsa is True
        assert result.hpsa_score is not None
        assert result.hpsa_score > 0
        assert result.discipline == "Primary Care"

    def test_lookup_unknown_county(self):
        """A county not in the CSV should return is_hpsa=False."""
        result = _lookup_hpsa_csv("99999")
        assert result is not None
        assert result.is_hpsa is False

    @pytest.mark.asyncio
    async def test_fetch_hpsa_uses_csv(self):
        """fetch_hpsa_data should return CSV data without hitting the API."""
        result = await fetch_hpsa_data(state_fips="29", county_fips="095")
        assert result is not None
        assert result.is_hpsa is True
        assert result.hpsa_score is not None
        assert len(result.designations) > 0


# ---------------------------------------------------------------------------
# ACS GeoHealth Fallback Tests
# ---------------------------------------------------------------------------


class TestACSGeoHealthFallback:
    """Test ACS fallback to GeoHealth API when Census API fails."""

    @pytest.fixture(autouse=True)
    def _clear_caches(self):
        from app.utils.cache import acs_cache
        acs_cache.clear()

    @pytest.mark.asyncio
    async def test_geohealth_acs_fallback_returns_data(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "geoid": "29095001100",
            "total_population": 4200,
            "median_household_income": 55000,
            "uninsured_rate": 12.5,
            "unemployment_rate": 5.8,
            "poverty_rate": 18.2,
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.census_acs.httpx.AsyncClient", return_value=mock_client):
            result = await _fetch_acs_from_geohealth("29095001100")

        assert result is not None
        assert result.total_population == 4200
        assert result.median_household_income == 55000

    @pytest.mark.asyncio
    async def test_geohealth_acs_fallback_returns_none_on_error(self):
        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.census_acs.httpx.AsyncClient", return_value=mock_client):
            result = await _fetch_acs_from_geohealth("99999999999")

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_acs_falls_back_when_census_fails(self):
        """When Census API fails, should try GeoHealth API."""
        census_error = httpx.HTTPStatusError(
            "No Content", request=MagicMock(), response=MagicMock(status_code=204)
        )

        geohealth_response = MagicMock()
        geohealth_response.status_code = 200
        geohealth_response.json.return_value = {
            "total_population": 3500,
            "median_household_income": 48000,
            "uninsured_rate": 15.0,
            "unemployment_rate": 7.2,
        }

        async def mock_get(url, **kwargs):
            if "api.census.gov" in str(url):
                raise census_error
            return geohealth_response

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.census_acs.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_acs_data("29095001100")

        assert result is not None
        assert result.total_population == 3500


# ---------------------------------------------------------------------------
# PLACES GeoHealth Fallback Tests
# ---------------------------------------------------------------------------


class TestPLACESGeoHealthFallback:
    """Test PLACES fallback to GeoHealth API when Socrata fails."""

    @pytest.fixture(autouse=True)
    def _clear_caches(self):
        from app.utils.cache import places_cache
        places_cache.clear()

    @pytest.mark.asyncio
    async def test_geohealth_places_fallback_returns_data(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "geoid": "29095001100",
            "places_measures": {
                "diabetes": 14.2,
                "obesity": 35.1,
                "bphigh": 32.0,
                "copd": 8.5,
                "depression": 22.3,
                "casthma": 9.8,
            },
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.services.cdc_places.httpx.AsyncClient", return_value=mock_client
        ):
            result = await _fetch_places_from_geohealth("29095001100")

        assert result is not None
        assert result.diabetes_pct == 14.2
        assert result.obesity_pct == 35.1
        assert result.chronic_disease_burden is not None

    @pytest.mark.asyncio
    async def test_fetch_places_falls_back_when_socrata_fails(self):
        """When Socrata PLACES fails, should try GeoHealth API."""
        socrata_error = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=MagicMock(status_code=500)
        )

        geohealth_response = MagicMock()
        geohealth_response.status_code = 200
        geohealth_response.json.return_value = {
            "places_measures": {
                "diabetes": 11.0,
                "obesity": 30.0,
            },
        }

        async def mock_get(url, **kwargs):
            if "data.cdc.gov" in str(url):
                raise socrata_error
            return geohealth_response

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.services.cdc_places.httpx.AsyncClient", return_value=mock_client
        ):
            result = await fetch_places_data("29095001100")

        assert result is not None
        assert result.diabetes_pct == 11.0


# ---------------------------------------------------------------------------
# Non-existent Tract Messaging Tests
# ---------------------------------------------------------------------------


class TestNonExistentTractMessaging:
    """Test that non-existent tracts get explanatory messages."""

    @patch("app.routers.market_fit.lookup_tract_npi", return_value=None)
    @patch("app.routers.market_fit.fetch_cbp_data", new_callable=AsyncMock)
    @patch("app.routers.market_fit.fetch_hpsa_data", new_callable=AsyncMock)
    @patch("app.routers.market_fit.fetch_npi_providers", new_callable=AsyncMock)
    @patch("app.routers.market_fit.fetch_svi_data", new_callable=AsyncMock)
    @patch("app.routers.market_fit.fetch_places_data", new_callable=AsyncMock)
    @patch("app.routers.market_fit.fetch_acs_data", new_callable=AsyncMock)
    @patch("app.routers.market_fit.resolve_location", new_callable=AsyncMock)
    def test_nonexistent_tract_gets_message(
        self, mock_geo, mock_acs, mock_places, mock_svi,
        mock_npi, mock_hpsa, mock_cbp, mock_tract_npi, client,
    ):
        from app.services.geocoder import GeocodedLocation

        mock_geo.return_value = GeocodedLocation(
            lat=0.0, lon=0.0,
            matched_address="Tract 29095001400",
            state_fips="29", county_fips="095",
            tract_fips="001400", geoid="29095001400",
        )
        # All data sources return None → non-existent tract
        mock_acs.return_value = None
        mock_places.return_value = None
        mock_svi.return_value = None
        mock_npi.return_value = None
        mock_hpsa.return_value = None
        mock_cbp.return_value = None

        resp = client.get("/api/v1/market-fit?tract_fips=29095001400")
        assert resp.status_code == 200
        data = resp.json()

        # Should contain explanatory message about non-existent tracts
        demand_summary = data["dimensions"]["demand"]["summary"]
        assert "may not exist" in demand_summary.lower() or "geography" in demand_summary.lower()
