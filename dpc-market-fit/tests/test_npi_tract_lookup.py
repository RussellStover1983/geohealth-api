"""Tests for tract-level NPI lookup service."""

from __future__ import annotations

import csv
from pathlib import Path
from unittest.mock import patch

from app.services.npi_tract_lookup import (
    lookup_tract_npi,
    reset_index,
)


def _write_test_csv(path: Path) -> None:
    """Write a small test CSV for lookup tests."""
    fieldnames = [
        "tract_fips", "pcp_count", "fqhc_count", "urgent_care_count",
        "rural_health_clinic_count", "primary_care_clinic_count",
        "community_health_center_count", "total_providers",
    ]
    rows = [
        {
            "tract_fips": "29095001100",
            "pcp_count": "12.4",
            "fqhc_count": "1.0",
            "urgent_care_count": "2.3",
            "rural_health_clinic_count": "0.0",
            "primary_care_clinic_count": "0.5",
            "community_health_center_count": "0.0",
            "total_providers": "16.2",
        },
        {
            "tract_fips": "29095015200",
            "pcp_count": "5.7",
            "fqhc_count": "0.0",
            "urgent_care_count": "1.0",
            "rural_health_clinic_count": "1.5",
            "primary_care_clinic_count": "0.0",
            "community_health_center_count": "0.0",
            "total_providers": "8.2",
        },
    ]

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class TestNPITractLookup:
    def setup_method(self):
        reset_index()

    def test_lookup_returns_npi_data(self, tmp_path):
        csv_path = tmp_path / "npi_tract_counts.csv"
        _write_test_csv(csv_path)

        with patch(
            "app.services.npi_tract_lookup._NPI_TRACT_CSV_PATH", csv_path
        ):
            result = lookup_tract_npi("29095001100")

        assert result is not None
        assert result.pcp_count == 12
        assert result.fqhc_count == 1
        assert result.urgent_care_count == 2
        assert result.rural_health_clinic_count == 0
        assert result.is_tract_level is True
        assert result.total_population is None  # Caller sets this

    def test_lookup_missing_tract_returns_none(self, tmp_path):
        csv_path = tmp_path / "npi_tract_counts.csv"
        _write_test_csv(csv_path)

        with patch(
            "app.services.npi_tract_lookup._NPI_TRACT_CSV_PATH", csv_path
        ):
            result = lookup_tract_npi("99999999999")

        assert result is None

    def test_lookup_fractional_counts_round_correctly(self, tmp_path):
        csv_path = tmp_path / "npi_tract_counts.csv"
        _write_test_csv(csv_path)

        with patch(
            "app.services.npi_tract_lookup._NPI_TRACT_CSV_PATH", csv_path
        ):
            result = lookup_tract_npi("29095015200")

        assert result is not None
        assert result.pcp_count == 6  # 5.7 rounds to 6
        assert result.rural_health_clinic_count == 2  # 1.5 rounds to 2

    def test_lookup_missing_csv_returns_none(self, tmp_path):
        missing_path = tmp_path / "does_not_exist.csv"

        with patch(
            "app.services.npi_tract_lookup._NPI_TRACT_CSV_PATH", missing_path
        ):
            result = lookup_tract_npi("29095001100")

        assert result is None

    def test_lookup_pcp_density_with_population(self, tmp_path):
        csv_path = tmp_path / "npi_tract_counts.csv"
        _write_test_csv(csv_path)

        with patch(
            "app.services.npi_tract_lookup._NPI_TRACT_CSV_PATH", csv_path
        ):
            result = lookup_tract_npi("29095001100")

        assert result is not None
        result.total_population = 5000
        assert result.pcp_per_100k is not None
        assert result.pcp_per_100k == round(12 / 5000 * 100_000, 1)

    def test_lookup_facility_counts_mapped_to_codes(self, tmp_path):
        csv_path = tmp_path / "npi_tract_counts.csv"
        _write_test_csv(csv_path)

        with patch(
            "app.services.npi_tract_lookup._NPI_TRACT_CSV_PATH", csv_path
        ):
            result = lookup_tract_npi("29095001100")

        assert result is not None
        assert result.facility_counts["261QF0400X"] == 1
        assert result.facility_counts["261QU0200X"] == 2
        assert result.facility_counts["261QR1300X"] == 0
