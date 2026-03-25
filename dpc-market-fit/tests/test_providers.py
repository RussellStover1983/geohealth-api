"""Tests for individual provider lookup + API endpoint."""

from __future__ import annotations

import csv
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.provider_lookup import (
    lookup_providers,
    reset_index,
)


@pytest.fixture(autouse=True)
def _reset():
    """Reset provider index before each test."""
    reset_index()
    yield
    reset_index()


@pytest.fixture
def client():
    return TestClient(app)


def _write_provider_csv(path: Path, rows: list[dict]) -> None:
    """Write a provider CSV for testing."""
    fieldnames = [
        "npi", "name", "credential", "taxonomy_code", "provider_type",
        "address", "city", "state", "zip", "lat", "lon", "tract_fips",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _sample_provider(
    npi: str = "1234567890",
    name: str = "Jane Smith",
    credential: str = "MD",
    provider_type: str = "PCP",
    tract_fips: str = "29095001100",
) -> dict:
    return {
        "npi": npi,
        "name": name,
        "credential": credential,
        "taxonomy_code": "207Q00000X",
        "provider_type": provider_type,
        "address": "123 Main St",
        "city": "Kansas City",
        "state": "MO",
        "zip": "64106",
        "lat": "39.1000",
        "lon": "-94.5800",
        "tract_fips": tract_fips,
    }


class TestProviderLookupService:
    """Tests for the provider_lookup module."""

    def test_lookup_found(self, tmp_path: Path):
        csv_path = tmp_path / "providers_MO.csv"
        _write_provider_csv(csv_path, [_sample_provider()])

        with patch(
            "app.services.provider_lookup._DATA_DIR", tmp_path
        ):
            result = lookup_providers("29095001100")

        assert len(result) == 1
        assert result[0].npi == "1234567890"
        assert result[0].name == "Jane Smith"
        assert result[0].provider_type == "PCP"
        assert result[0].lat == pytest.approx(39.1)
        assert result[0].lon == pytest.approx(-94.58)

    def test_lookup_not_found(self, tmp_path: Path):
        csv_path = tmp_path / "providers_MO.csv"
        _write_provider_csv(csv_path, [_sample_provider()])

        with patch(
            "app.services.provider_lookup._DATA_DIR", tmp_path
        ):
            result = lookup_providers("29095999999")

        assert len(result) == 0

    def test_lookup_no_csv(self, tmp_path: Path):
        with patch(
            "app.services.provider_lookup._DATA_DIR", tmp_path
        ):
            result = lookup_providers("29095001100")

        assert len(result) == 0

    def test_lookup_filter_by_type(self, tmp_path: Path):
        csv_path = tmp_path / "providers_MO.csv"
        _write_provider_csv(csv_path, [
            _sample_provider(npi="111", provider_type="PCP"),
            _sample_provider(npi="222", provider_type="FQHC"),
            _sample_provider(npi="333", provider_type="PCP"),
        ])

        with patch(
            "app.services.provider_lookup._DATA_DIR", tmp_path
        ):
            all_providers = lookup_providers("29095001100")
            fqhc_only = lookup_providers("29095001100", provider_type="FQHC")
            pcp_only = lookup_providers("29095001100", provider_type="PCP")

        assert len(all_providers) == 3
        assert len(fqhc_only) == 1
        assert fqhc_only[0].npi == "222"
        assert len(pcp_only) == 2

    def test_lookup_multiple_tracts(self, tmp_path: Path):
        csv_path = tmp_path / "providers_MO.csv"
        _write_provider_csv(csv_path, [
            _sample_provider(npi="111", tract_fips="29095001100"),
            _sample_provider(npi="222", tract_fips="29095001200"),
        ])

        with patch(
            "app.services.provider_lookup._DATA_DIR", tmp_path
        ):
            result_1 = lookup_providers("29095001100")
            result_2 = lookup_providers("29095001200")

        assert len(result_1) == 1
        assert result_1[0].npi == "111"
        assert len(result_2) == 1
        assert result_2[0].npi == "222"

    def test_lookup_short_fips(self):
        result = lookup_providers("2")
        assert result == []

    def test_lookup_empty_fips(self):
        result = lookup_providers("")
        assert result == []


class TestProvidersEndpoint:
    """Tests for GET /api/v1/providers."""

    def test_providers_geojson(self, client, tmp_path: Path):
        csv_path = tmp_path / "providers_MO.csv"
        _write_provider_csv(csv_path, [
            _sample_provider(npi="111"),
            _sample_provider(npi="222", provider_type="FQHC"),
        ])

        with patch(
            "app.services.provider_lookup._DATA_DIR", tmp_path
        ):
            resp = client.get("/api/v1/providers?tract_fips=29095001100")

        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == 2

        feat = data["features"][0]
        assert feat["type"] == "Feature"
        assert feat["geometry"]["type"] == "Point"
        assert len(feat["geometry"]["coordinates"]) == 2
        assert feat["properties"]["npi"] == "111"
        assert "name" in feat["properties"]
        assert "provider_type" in feat["properties"]
        assert "address" in feat["properties"]

    def test_providers_type_filter(self, client, tmp_path: Path):
        csv_path = tmp_path / "providers_MO.csv"
        _write_provider_csv(csv_path, [
            _sample_provider(npi="111", provider_type="PCP"),
            _sample_provider(npi="222", provider_type="FQHC"),
        ])

        with patch(
            "app.services.provider_lookup._DATA_DIR", tmp_path
        ):
            resp = client.get(
                "/api/v1/providers?tract_fips=29095001100&type=FQHC"
            )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["features"]) == 1
        assert data["features"][0]["properties"]["provider_type"] == "FQHC"

    def test_providers_empty_result(self, client, tmp_path: Path):
        csv_path = tmp_path / "providers_MO.csv"
        _write_provider_csv(csv_path, [])

        with patch(
            "app.services.provider_lookup._DATA_DIR", tmp_path
        ):
            resp = client.get("/api/v1/providers?tract_fips=29095001100")

        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == 0

    def test_providers_missing_tract_fips(self, client):
        resp = client.get("/api/v1/providers")
        assert resp.status_code == 422

    def test_providers_invalid_tract_fips(self, client):
        resp = client.get("/api/v1/providers?tract_fips=123")
        assert resp.status_code == 422

    def test_providers_name_with_credential(self, client, tmp_path: Path):
        csv_path = tmp_path / "providers_MO.csv"
        _write_provider_csv(csv_path, [
            _sample_provider(name="John Doe", credential="DO"),
        ])

        with patch(
            "app.services.provider_lookup._DATA_DIR", tmp_path
        ):
            resp = client.get("/api/v1/providers?tract_fips=29095001100")

        assert resp.status_code == 200
        feat = resp.json()["features"][0]
        assert feat["properties"]["name"] == "John Doe, DO"

    def test_providers_coordinates_format(self, client, tmp_path: Path):
        csv_path = tmp_path / "providers_MO.csv"
        _write_provider_csv(csv_path, [_sample_provider()])

        with patch(
            "app.services.provider_lookup._DATA_DIR", tmp_path
        ):
            resp = client.get("/api/v1/providers?tract_fips=29095001100")

        coords = resp.json()["features"][0]["geometry"]["coordinates"]
        # GeoJSON: [lon, lat]
        assert coords[0] == pytest.approx(-94.58)
        assert coords[1] == pytest.approx(39.1)
