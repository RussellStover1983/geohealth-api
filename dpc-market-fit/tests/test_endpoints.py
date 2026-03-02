"""Tests for API endpoints — all external service calls mocked."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.census_acs import ACSData
from app.services.census_cbp import CBPData
from app.services.cdc_places import PLACESData
from app.services.cdc_svi import SVIData
from app.services.geocoder import GeocodedLocation
from app.services.hrsa_hpsa import HPSAData
from app.services.npi_registry import NPIData


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


def _mock_npi_data():
    return NPIData(
        pcp_count=25,
        pcp_details=[],
        facility_counts={
            "261QF0400X": 2,
            "261QU0200X": 3,
            "261QR1300X": 0,
        },
        total_population=5000,
    )


def _mock_hpsa_data():
    return HPSAData(
        is_hpsa=True,
        hpsa_score=15.0,
        hpsa_type="Geographic HPSA",
        designation_type="Designated",
        discipline="Primary Care",
        designations=[],
    )


def _mock_cbp_data():
    return CBPData(
        total_establishments=500,
        target_establishments=120,
        total_employees=8000,
        annual_payroll=400_000_000,  # $400M total → $50k avg wage
        industry_breakdown={
            "Professional, Scientific & Technical Services": 80,
            "Health Care & Social Assistance": 60,
        },
    )


# Shared mock patch paths for market_fit router
_MF_PREFIX = "app.routers.market_fit"
_MF_PATCHES = [
    f"{_MF_PREFIX}.resolve_location",
    f"{_MF_PREFIX}.fetch_acs_data",
    f"{_MF_PREFIX}.fetch_places_data",
    f"{_MF_PREFIX}.fetch_svi_data",
    f"{_MF_PREFIX}.fetch_npi_providers",
    f"{_MF_PREFIX}.fetch_hpsa_data",
    f"{_MF_PREFIX}.fetch_cbp_data",
]


class TestHealthEndpoint:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


class TestMarketFitEndpoint:
    @patch(f"{_MF_PREFIX}.fetch_cbp_data", new_callable=AsyncMock)
    @patch(f"{_MF_PREFIX}.fetch_hpsa_data", new_callable=AsyncMock)
    @patch(f"{_MF_PREFIX}.fetch_npi_providers", new_callable=AsyncMock)
    @patch(f"{_MF_PREFIX}.fetch_svi_data", new_callable=AsyncMock)
    @patch(f"{_MF_PREFIX}.fetch_places_data", new_callable=AsyncMock)
    @patch(f"{_MF_PREFIX}.fetch_acs_data", new_callable=AsyncMock)
    @patch(f"{_MF_PREFIX}.resolve_location", new_callable=AsyncMock)
    def test_market_fit_with_tract_fips(
        self, mock_geo, mock_acs, mock_places, mock_svi,
        mock_npi, mock_hpsa, mock_cbp, client
    ):
        mock_geo.return_value = _mock_geocode_result()
        mock_acs.return_value = _mock_acs_data()
        mock_places.return_value = _mock_places_data()
        mock_svi.return_value = _mock_svi_data()
        mock_npi.return_value = _mock_npi_data()
        mock_hpsa.return_value = _mock_hpsa_data()
        mock_cbp.return_value = _mock_cbp_data()

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

        # Phase 2: supply_gap, employer, competition should have real scores
        for dim in ["supply_gap", "employer", "competition"]:
            assert data["dimensions"][dim]["data_completeness"] > 0

    @patch(f"{_MF_PREFIX}.fetch_cbp_data", new_callable=AsyncMock)
    @patch(f"{_MF_PREFIX}.fetch_hpsa_data", new_callable=AsyncMock)
    @patch(f"{_MF_PREFIX}.fetch_npi_providers", new_callable=AsyncMock)
    @patch(f"{_MF_PREFIX}.fetch_svi_data", new_callable=AsyncMock)
    @patch(f"{_MF_PREFIX}.fetch_places_data", new_callable=AsyncMock)
    @patch(f"{_MF_PREFIX}.fetch_acs_data", new_callable=AsyncMock)
    @patch(f"{_MF_PREFIX}.resolve_location", new_callable=AsyncMock)
    def test_market_fit_with_address(
        self, mock_geo, mock_acs, mock_places, mock_svi,
        mock_npi, mock_hpsa, mock_cbp, client
    ):
        mock_geo.return_value = _mock_geocode_result()
        mock_acs.return_value = _mock_acs_data()
        mock_places.return_value = _mock_places_data()
        mock_svi.return_value = _mock_svi_data()
        mock_npi.return_value = _mock_npi_data()
        mock_hpsa.return_value = _mock_hpsa_data()
        mock_cbp.return_value = _mock_cbp_data()

        resp = client.get(
            "/api/v1/market-fit",
            params={"address": "123 Main St, Kansas City, MO"},
        )
        assert resp.status_code == 200

    def test_market_fit_no_location(self, client):
        resp = client.get("/api/v1/market-fit")
        assert resp.status_code == 400

    @patch(f"{_MF_PREFIX}.fetch_cbp_data", new_callable=AsyncMock)
    @patch(f"{_MF_PREFIX}.fetch_hpsa_data", new_callable=AsyncMock)
    @patch(f"{_MF_PREFIX}.fetch_npi_providers", new_callable=AsyncMock)
    @patch(f"{_MF_PREFIX}.fetch_svi_data", new_callable=AsyncMock)
    @patch(f"{_MF_PREFIX}.fetch_places_data", new_callable=AsyncMock)
    @patch(f"{_MF_PREFIX}.fetch_acs_data", new_callable=AsyncMock)
    @patch(f"{_MF_PREFIX}.resolve_location", new_callable=AsyncMock)
    def test_market_fit_custom_weights(
        self, mock_geo, mock_acs, mock_places, mock_svi,
        mock_npi, mock_hpsa, mock_cbp, client
    ):
        mock_geo.return_value = _mock_geocode_result()
        mock_acs.return_value = _mock_acs_data()
        mock_places.return_value = _mock_places_data()
        mock_svi.return_value = _mock_svi_data()
        mock_npi.return_value = _mock_npi_data()
        mock_hpsa.return_value = _mock_hpsa_data()
        mock_cbp.return_value = _mock_cbp_data()

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

    @patch(f"{_MF_PREFIX}.fetch_cbp_data", new_callable=AsyncMock)
    @patch(f"{_MF_PREFIX}.fetch_hpsa_data", new_callable=AsyncMock)
    @patch(f"{_MF_PREFIX}.fetch_npi_providers", new_callable=AsyncMock)
    @patch(f"{_MF_PREFIX}.fetch_svi_data", new_callable=AsyncMock)
    @patch(f"{_MF_PREFIX}.fetch_places_data", new_callable=AsyncMock)
    @patch(f"{_MF_PREFIX}.fetch_acs_data", new_callable=AsyncMock)
    @patch(f"{_MF_PREFIX}.resolve_location", new_callable=AsyncMock)
    def test_market_fit_null_data_graceful(
        self, mock_geo, mock_acs, mock_places, mock_svi,
        mock_npi, mock_hpsa, mock_cbp, client
    ):
        """API should degrade gracefully when data sources return None."""
        mock_geo.return_value = _mock_geocode_result()
        mock_acs.return_value = None
        mock_places.return_value = None
        mock_svi.return_value = None
        mock_npi.return_value = None
        mock_hpsa.return_value = None
        mock_cbp.return_value = None

        resp = client.get("/api/v1/market-fit?tract_fips=29095001100")
        assert resp.status_code == 200
        data = resp.json()
        # Should still return a response with placeholder/zero scores
        assert data["dimensions"]["demand"]["score"] == 0.0
        assert data["dimensions"]["demand"]["data_completeness"] == 0.0

    @patch(f"{_MF_PREFIX}.fetch_cbp_data", new_callable=AsyncMock)
    @patch(f"{_MF_PREFIX}.fetch_hpsa_data", new_callable=AsyncMock)
    @patch(f"{_MF_PREFIX}.fetch_npi_providers", new_callable=AsyncMock)
    @patch(f"{_MF_PREFIX}.fetch_svi_data", new_callable=AsyncMock)
    @patch(f"{_MF_PREFIX}.fetch_places_data", new_callable=AsyncMock)
    @patch(f"{_MF_PREFIX}.fetch_acs_data", new_callable=AsyncMock)
    @patch(f"{_MF_PREFIX}.resolve_location", new_callable=AsyncMock)
    def test_market_fit_all_dimensions_scored(
        self, mock_geo, mock_acs, mock_places, mock_svi,
        mock_npi, mock_hpsa, mock_cbp, client
    ):
        """All five dimensions should have real scores with full data."""
        mock_geo.return_value = _mock_geocode_result()
        mock_acs.return_value = _mock_acs_data()
        mock_places.return_value = _mock_places_data()
        mock_svi.return_value = _mock_svi_data()
        mock_npi.return_value = _mock_npi_data()
        mock_hpsa.return_value = _mock_hpsa_data()
        mock_cbp.return_value = _mock_cbp_data()

        resp = client.get("/api/v1/market-fit?tract_fips=29095001100")
        assert resp.status_code == 200
        data = resp.json()

        for dim_name, dim_data in data["dimensions"].items():
            assert 0 <= dim_data["score"] <= 100, f"{dim_name} score out of range"
            assert dim_data["category"] in [
                "WEAK", "MODERATE", "STRONG", "EXCELLENT"
            ]
            assert dim_data["data_completeness"] > 0, (
                f"{dim_name} has no data completeness"
            )

        # Data vintage should include Phase 2 sources
        assert data["data_vintage"]["npi"] is not None
        assert data["data_vintage"]["cbp"] is not None


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


class TestSupplyEndpoint:
    @patch("app.routers.supply.fetch_npi_providers", new_callable=AsyncMock)
    @patch("app.routers.supply.fetch_hpsa_data", new_callable=AsyncMock)
    @patch("app.routers.supply.fetch_acs_data", new_callable=AsyncMock)
    @patch("app.routers.supply.resolve_location", new_callable=AsyncMock)
    def test_supply_detail(
        self, mock_geo, mock_acs, mock_hpsa, mock_npi, client
    ):
        mock_geo.return_value = _mock_geocode_result()
        mock_acs.return_value = _mock_acs_data()
        mock_npi.return_value = _mock_npi_data()
        mock_hpsa.return_value = _mock_hpsa_data()

        resp = client.get("/api/v1/market-fit/supply?tract_fips=29095001100")
        assert resp.status_code == 200
        data = resp.json()

        assert data["pcp_count"] == 25
        assert data["pcp_per_100k"] is not None
        assert data["is_hpsa"] is True
        assert data["hpsa_score"] == 15.0
        assert data["fqhc_count"] == 2
        assert data["urgent_care_count"] == 3
        assert data["supply_gap_score"] is not None
        assert data["supply_gap_score"]["data_completeness"] > 0

    @patch("app.routers.supply.fetch_npi_providers", new_callable=AsyncMock)
    @patch("app.routers.supply.fetch_hpsa_data", new_callable=AsyncMock)
    @patch("app.routers.supply.fetch_acs_data", new_callable=AsyncMock)
    @patch("app.routers.supply.resolve_location", new_callable=AsyncMock)
    def test_supply_no_data_graceful(
        self, mock_geo, mock_acs, mock_hpsa, mock_npi, client
    ):
        mock_geo.return_value = _mock_geocode_result()
        mock_acs.return_value = None
        mock_npi.return_value = None
        mock_hpsa.return_value = None

        resp = client.get("/api/v1/market-fit/supply?tract_fips=29095001100")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pcp_count"] == 0
        assert data["supply_gap_score"]["data_completeness"] == 0.0

    def test_supply_no_location(self, client):
        resp = client.get("/api/v1/market-fit/supply")
        assert resp.status_code == 400


class TestEmployerEndpoint:
    @patch("app.routers.employer.fetch_cbp_data", new_callable=AsyncMock)
    @patch("app.routers.employer.fetch_acs_data", new_callable=AsyncMock)
    @patch("app.routers.employer.resolve_location", new_callable=AsyncMock)
    def test_employer_detail(
        self, mock_geo, mock_acs, mock_cbp, client
    ):
        mock_geo.return_value = _mock_geocode_result()
        mock_acs.return_value = _mock_acs_data()
        mock_cbp.return_value = _mock_cbp_data()

        resp = client.get("/api/v1/market-fit/employer?tract_fips=29095001100")
        assert resp.status_code == 200
        data = resp.json()

        assert data["total_establishments"] == 500
        assert data["target_establishments"] == 120
        assert data["target_establishment_pct"] is not None
        assert data["total_employees"] == 8000
        assert data["avg_annual_wage"] is not None
        assert data["employer_score"] is not None
        assert data["employer_score"]["data_completeness"] > 0

    @patch("app.routers.employer.fetch_cbp_data", new_callable=AsyncMock)
    @patch("app.routers.employer.fetch_acs_data", new_callable=AsyncMock)
    @patch("app.routers.employer.resolve_location", new_callable=AsyncMock)
    def test_employer_no_data_graceful(
        self, mock_geo, mock_acs, mock_cbp, client
    ):
        mock_geo.return_value = _mock_geocode_result()
        mock_acs.return_value = None
        mock_cbp.return_value = None

        resp = client.get("/api/v1/market-fit/employer?tract_fips=29095001100")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_establishments"] == 0
        assert data["employer_score"]["data_completeness"] == 0.0

    def test_employer_no_location(self, client):
        resp = client.get("/api/v1/market-fit/employer")
        assert resp.status_code == 400


class TestCompetitionEndpoint:
    @patch("app.routers.competition.fetch_npi_providers", new_callable=AsyncMock)
    @patch("app.routers.competition.fetch_acs_data", new_callable=AsyncMock)
    @patch("app.routers.competition.resolve_location", new_callable=AsyncMock)
    def test_competition_detail(
        self, mock_geo, mock_acs, mock_npi, client
    ):
        mock_geo.return_value = _mock_geocode_result()
        mock_acs.return_value = _mock_acs_data()
        mock_npi.return_value = _mock_npi_data()

        resp = client.get("/api/v1/market-fit/competition?tract_fips=29095001100")
        assert resp.status_code == 200
        data = resp.json()

        assert data["fqhc_count"] == 2
        assert data["urgent_care_count"] == 3
        assert data["pcp_density_per_100k"] is not None
        assert data["competition_score"] is not None
        assert data["competition_score"]["data_completeness"] > 0

    @patch("app.routers.competition.fetch_npi_providers", new_callable=AsyncMock)
    @patch("app.routers.competition.fetch_acs_data", new_callable=AsyncMock)
    @patch("app.routers.competition.resolve_location", new_callable=AsyncMock)
    def test_competition_no_data_graceful(
        self, mock_geo, mock_acs, mock_npi, client
    ):
        mock_geo.return_value = _mock_geocode_result()
        mock_acs.return_value = None
        mock_npi.return_value = None

        resp = client.get("/api/v1/market-fit/competition?tract_fips=29095001100")
        assert resp.status_code == 200
        data = resp.json()
        assert data["fqhc_count"] == 0
        assert data["competition_score"]["data_completeness"] == 0.0

    def test_competition_no_location(self, client):
        resp = client.get("/api/v1/market-fit/competition")
        assert resp.status_code == 400
