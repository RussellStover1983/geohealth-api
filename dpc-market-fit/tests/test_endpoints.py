"""Tests for API endpoints — all external service calls mocked."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.census_acs import ACSData
from app.services.cdc_places import PLACESData
from app.services.cdc_svi import SVIData
from app.services.geocoder import GeocodedLocation


def _mock_geocode_result():
    return GeocodedLocation(
        lat=39.0997,
        lon=-94.5786,
        matched_address="123 Main St, Kansas City, MO",
        state_fips="29",
        county_fips="095",
        tract_fips="001100",
        geoid="29095001100",
    )


def _mock_acs_data():
    raw = {
        "total_population": 5000,
        "insurance_universe": 4500,
        "uninsured": 500,
        "employer_insurance": 2500,
        "medicaid": 400,
        "medicare": 300,
        "civilian_labor_force": 3000,
        "unemployed": 200,
        "median_household_income": 65000,
        "renters_total": 1500,
        "renters_30_34pct": 100,
        "renters_35_39pct": 80,
        "renters_40_49pct": 60,
        "renters_50pct_plus": 40,
        "employment_universe": 3500,
        "in_labor_force": 3200,
    }
    for key in [
        "male_18_19", "male_20", "male_21", "male_22_24",
        "male_25_29", "male_30_34", "male_35_39", "male_40_44",
        "male_45_49", "male_50_54", "male_55_59", "male_60_61", "male_62_64",
        "female_18_19", "female_20", "female_21", "female_22_24",
        "female_25_29", "female_30_34", "female_35_39", "female_40_44",
        "female_45_49", "female_50_54", "female_55_59", "female_60_61", "female_62_64",
    ]:
        raw[key] = 120
    return ACSData(raw)


def _mock_places_data():
    return PLACESData({
        "diabetes_pct": 12.0,
        "hypertension_pct": 30.0,
        "obesity_pct": 32.0,
        "copd_pct": 7.0,
        "depression_pct": 20.0,
        "asthma_pct": 10.0,
    })


def _mock_svi_data():
    return SVIData({
        "rpl_theme1": 0.6,
        "rpl_theme2": 0.5,
        "rpl_theme3": 0.4,
        "rpl_theme4": 0.3,
        "rpl_themes": 0.5,
    })


class TestHealthEndpoint:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


class TestMarketFitEndpoint:
    @patch("app.routers.market_fit.fetch_svi_data", new_callable=AsyncMock)
    @patch("app.routers.market_fit.fetch_places_data", new_callable=AsyncMock)
    @patch("app.routers.market_fit.fetch_acs_data", new_callable=AsyncMock)
    @patch("app.routers.market_fit.resolve_location", new_callable=AsyncMock)
    def test_market_fit_with_tract_fips(
        self, mock_geo, mock_acs, mock_places, mock_svi, client
    ):
        mock_geo.return_value = _mock_geocode_result()
        mock_acs.return_value = _mock_acs_data()
        mock_places.return_value = _mock_places_data()
        mock_svi.return_value = _mock_svi_data()

        resp = client.get("/api/v1/market-fit?tract_fips=29095001100")
        assert resp.status_code == 200
        data = resp.json()

        assert "composite_score" in data
        assert "dimensions" in data
        assert "location" in data
        assert "data_vintage" in data

        assert 0 <= data["composite_score"]["value"] <= 100
        assert data["composite_score"]["category"] in [
            "WEAK", "MODERATE", "STRONG", "EXCELLENT"
        ]

        assert "demand" in data["dimensions"]
        assert "supply_gap" in data["dimensions"]
        assert "affordability" in data["dimensions"]
        assert "employer" in data["dimensions"]
        assert "competition" in data["dimensions"]

        assert data["location"]["primary_tract_fips"] == "29095001100"

    @patch("app.routers.market_fit.fetch_svi_data", new_callable=AsyncMock)
    @patch("app.routers.market_fit.fetch_places_data", new_callable=AsyncMock)
    @patch("app.routers.market_fit.fetch_acs_data", new_callable=AsyncMock)
    @patch("app.routers.market_fit.resolve_location", new_callable=AsyncMock)
    def test_market_fit_with_address(
        self, mock_geo, mock_acs, mock_places, mock_svi, client
    ):
        mock_geo.return_value = _mock_geocode_result()
        mock_acs.return_value = _mock_acs_data()
        mock_places.return_value = _mock_places_data()
        mock_svi.return_value = _mock_svi_data()

        resp = client.get(
            "/api/v1/market-fit",
            params={"address": "123 Main St, Kansas City, MO"},
        )
        assert resp.status_code == 200

    def test_market_fit_no_location(self, client):
        resp = client.get("/api/v1/market-fit")
        assert resp.status_code == 400

    @patch("app.routers.market_fit.fetch_svi_data", new_callable=AsyncMock)
    @patch("app.routers.market_fit.fetch_places_data", new_callable=AsyncMock)
    @patch("app.routers.market_fit.fetch_acs_data", new_callable=AsyncMock)
    @patch("app.routers.market_fit.resolve_location", new_callable=AsyncMock)
    def test_market_fit_custom_weights(
        self, mock_geo, mock_acs, mock_places, mock_svi, client
    ):
        mock_geo.return_value = _mock_geocode_result()
        mock_acs.return_value = _mock_acs_data()
        mock_places.return_value = _mock_places_data()
        mock_svi.return_value = _mock_svi_data()

        resp = client.get(
            "/api/v1/market-fit",
            params={
                "tract_fips": "29095001100",
                "w_demand": "0.50",
                "w_supply_gap": "0.10",
                "w_affordability": "0.20",
                "w_employer": "0.10",
                "w_competition": "0.10",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["composite_score"]["weights_used"]["demand"] == 0.50

    @patch("app.routers.market_fit.fetch_svi_data", new_callable=AsyncMock)
    @patch("app.routers.market_fit.fetch_places_data", new_callable=AsyncMock)
    @patch("app.routers.market_fit.fetch_acs_data", new_callable=AsyncMock)
    @patch("app.routers.market_fit.resolve_location", new_callable=AsyncMock)
    def test_market_fit_null_data_graceful(
        self, mock_geo, mock_acs, mock_places, mock_svi, client
    ):
        """API should degrade gracefully when data sources return None."""
        mock_geo.return_value = _mock_geocode_result()
        mock_acs.return_value = None
        mock_places.return_value = None
        mock_svi.return_value = None

        resp = client.get("/api/v1/market-fit?tract_fips=29095001100")
        assert resp.status_code == 200
        data = resp.json()
        # Should still return a response with placeholder/zero scores
        assert data["dimensions"]["demand"]["score"] == 0.0
        assert data["dimensions"]["demand"]["data_completeness"] == 0.0


class TestDemandEndpoint:
    @patch("app.routers.demand.fetch_svi_data", new_callable=AsyncMock)
    @patch("app.routers.demand.fetch_places_data", new_callable=AsyncMock)
    @patch("app.routers.demand.fetch_acs_data", new_callable=AsyncMock)
    @patch("app.routers.demand.resolve_location", new_callable=AsyncMock)
    def test_demand_detail(
        self, mock_geo, mock_acs, mock_places, mock_svi, client
    ):
        mock_geo.return_value = _mock_geocode_result()
        mock_acs.return_value = _mock_acs_data()
        mock_places.return_value = _mock_places_data()
        mock_svi.return_value = _mock_svi_data()

        resp = client.get("/api/v1/market-fit/demand?tract_fips=29095001100")
        assert resp.status_code == 200
        data = resp.json()

        assert data["total_population"] == 5000
        assert data["uninsured_rate"] is not None
        assert data["chronic_disease_prevalence"]["diabetes_pct"] == 12.0
        assert data["svi_composite"] == 0.5
        assert data["demand_score"] is not None
        assert data["affordability_score"] is not None

    def test_demand_no_location(self, client):
        resp = client.get("/api/v1/market-fit/demand")
        assert resp.status_code == 400


class TestPhaseStubEndpoints:
    def test_supply_returns_501(self, client):
        resp = client.get("/api/v1/market-fit/supply?tract_fips=29095001100")
        assert resp.status_code == 200  # Returns JSON body, not 501 HTTP status
        data = resp.json()
        assert data["status_code"] == 501

    def test_employer_returns_501(self, client):
        resp = client.get("/api/v1/market-fit/employer?tract_fips=29095001100")
        data = resp.json()
        assert data["status_code"] == 501

    def test_competition_returns_501(self, client):
        resp = client.get("/api/v1/market-fit/competition?tract_fips=29095001100")
        data = resp.json()
        assert data["status_code"] == 501
