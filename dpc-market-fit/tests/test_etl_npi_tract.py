"""Tests for NPPES bulk data ETL pipeline."""

from __future__ import annotations

import csv
import io

from etl.load_npi_tract import (
    _extract_taxonomy_codes,
    _get_practice_zip,
    _is_active,
    _load_taxonomy_sets,
    load_hud_crosswalk,
    process_nppes_stream,
    write_output_csv,
)


class TestTaxonomyLoading:
    def test_load_taxonomy_sets(self):
        pcp_codes, facility_map = _load_taxonomy_sets()

        # Should have tier1 + tier2 PCP codes
        assert len(pcp_codes) > 10
        assert "207Q00000X" in pcp_codes  # Family Medicine
        assert "363LF0000X" in pcp_codes  # Family NP
        assert "363A00000X" in pcp_codes  # PA (tier2)

        # Should not include tier3 / excluded codes
        assert "207RH0003X" not in pcp_codes  # Hospitalist

        # Facility codes mapped to columns
        assert "261QF0400X" in facility_map  # FQHC
        assert facility_map["261QF0400X"] == "fqhc_count"
        assert "261QU0200X" in facility_map  # Urgent care
        assert facility_map["261QU0200X"] == "urgent_care_count"
        assert "261QR1300X" in facility_map  # Rural health
        assert facility_map["261QR1300X"] == "rural_health_clinic_count"


class TestNPPESRowParsing:
    def test_extract_taxonomy_codes(self):
        row = {
            "Healthcare Provider Taxonomy Code_1": "207Q00000X",
            "Healthcare Provider Taxonomy Code_2": "207R00000X",
            "Healthcare Provider Taxonomy Code_3": "",
        }
        codes = _extract_taxonomy_codes(row)
        assert codes == ["207Q00000X", "207R00000X"]

    def test_extract_taxonomy_codes_empty(self):
        row = {}
        codes = _extract_taxonomy_codes(row)
        assert codes == []

    def test_get_practice_zip(self):
        row = {
            "Provider Business Practice Location Address Postal Code": "641061234"
        }
        assert _get_practice_zip(row) == "64106"

    def test_get_practice_zip_short(self):
        row = {
            "Provider Business Practice Location Address Postal Code": "641"
        }
        assert _get_practice_zip(row) is None

    def test_get_practice_zip_missing(self):
        row = {}
        assert _get_practice_zip(row) is None

    def test_is_active_empty_deactivation(self):
        row = {"NPI Deactivation Reason Code": ""}
        assert _is_active(row) is True

    def test_is_active_with_deactivation(self):
        row = {"NPI Deactivation Reason Code": "DT"}
        assert _is_active(row) is False

    def test_is_active_missing_field(self):
        row = {}
        assert _is_active(row) is True


class TestHUDCrosswalk:
    def test_load_csv_crosswalk(self, tmp_path):
        csv_path = tmp_path / "crosswalk.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["ZIP", "TRACT", "TOT_RATIO"])
            writer.writeheader()
            writer.writerow({"ZIP": "64106", "TRACT": "29095001100", "TOT_RATIO": "0.6"})
            writer.writerow({"ZIP": "64106", "TRACT": "29095001200", "TOT_RATIO": "0.4"})
            writer.writerow({"ZIP": "66101", "TRACT": "20209000100", "TOT_RATIO": "1.0"})

        crosswalk = load_hud_crosswalk(str(csv_path))

        assert len(crosswalk) == 2
        assert len(crosswalk["64106"]) == 2
        assert crosswalk["64106"][0] == ("29095001100", 0.6)
        assert crosswalk["64106"][1] == ("29095001200", 0.4)
        assert crosswalk["66101"][0] == ("20209000100", 1.0)

    def test_crosswalk_skips_zero_ratio(self, tmp_path):
        csv_path = tmp_path / "crosswalk.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["ZIP", "TRACT", "TOT_RATIO"])
            writer.writeheader()
            writer.writerow({"ZIP": "64106", "TRACT": "29095001100", "TOT_RATIO": "0.0"})
            writer.writerow({"ZIP": "64106", "TRACT": "29095001200", "TOT_RATIO": "0.8"})

        crosswalk = load_hud_crosswalk(str(csv_path))
        assert len(crosswalk["64106"]) == 1


class TestProcessNPPESStream:
    def _make_nppes_row(
        self,
        npi: str = "1234567890",
        entity_type: str = "1",
        taxonomy: str = "207Q00000X",
        zip_code: str = "64106",
        state: str = "MO",
        active: bool = True,
    ) -> dict:
        row = {
            "NPI": npi,
            "Entity Type Code": entity_type,
            "Healthcare Provider Taxonomy Code_1": taxonomy,
            "Provider Business Practice Location Address Postal Code": zip_code,
            "Provider Business Practice Location Address State Name": state,
            "NPI Deactivation Reason Code": "" if active else "DT",
        }
        # Fill remaining taxonomy columns as empty
        for i in range(2, 16):
            row[f"Healthcare Provider Taxonomy Code_{i}"] = ""
        return row

    def _make_crosswalk(self) -> dict[str, list[tuple[str, float]]]:
        return {
            "64106": [("29095001100", 0.6), ("29095001200", 0.4)],
            "66101": [("20209000100", 1.0)],
        }

    def _make_reader(self, rows: list[dict]) -> csv.DictReader:
        """Create a DictReader from a list of row dicts."""
        if not rows:
            return csv.DictReader(io.StringIO(""))

        fieldnames = list(rows[0].keys())
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        output.seek(0)
        return csv.DictReader(output)

    def test_pcp_allocated_fractionally(self):
        pcp_codes, facility_map = _load_taxonomy_sets()
        crosswalk = self._make_crosswalk()

        rows = [
            self._make_nppes_row(npi="1111111111", taxonomy="207Q00000X", zip_code="64106"),
        ]
        reader = self._make_reader(rows)

        result, _ = process_nppes_stream(reader, crosswalk, pcp_codes, facility_map)

        assert "29095001100" in result
        assert result["29095001100"]["pcp_count"] == 0.6
        assert "29095001200" in result
        assert result["29095001200"]["pcp_count"] == 0.4

    def test_facility_allocated_to_tracts(self):
        pcp_codes, facility_map = _load_taxonomy_sets()
        crosswalk = self._make_crosswalk()

        rows = [
            self._make_nppes_row(
                npi="2222222222",
                entity_type="2",
                taxonomy="261QF0400X",  # FQHC
                zip_code="66101",
            ),
        ]
        reader = self._make_reader(rows)

        result, _ = process_nppes_stream(reader, crosswalk, pcp_codes, facility_map)

        assert "20209000100" in result
        assert result["20209000100"]["fqhc_count"] == 1.0

    def test_inactive_npi_skipped(self):
        pcp_codes, facility_map = _load_taxonomy_sets()
        crosswalk = self._make_crosswalk()

        rows = [
            self._make_nppes_row(
                npi="3333333333", taxonomy="207Q00000X",
                zip_code="64106", active=False,
            ),
        ]
        reader = self._make_reader(rows)

        result, _ = process_nppes_stream(reader, crosswalk, pcp_codes, facility_map)
        assert len(result) == 0

    def test_non_pcp_taxonomy_skipped(self):
        pcp_codes, facility_map = _load_taxonomy_sets()
        crosswalk = self._make_crosswalk()

        rows = [
            self._make_nppes_row(
                npi="4444444444",
                taxonomy="207RH0003X",  # Hospitalist — excluded
                zip_code="64106",
            ),
        ]
        reader = self._make_reader(rows)

        result, _ = process_nppes_stream(reader, crosswalk, pcp_codes, facility_map)
        assert len(result) == 0

    def test_state_filter(self):
        pcp_codes, facility_map = _load_taxonomy_sets()
        crosswalk = self._make_crosswalk()

        rows = [
            self._make_nppes_row(npi="5555555555", zip_code="64106", state="MO"),
            self._make_nppes_row(npi="6666666666", zip_code="66101", state="KS"),
        ]
        reader = self._make_reader(rows)

        result, _ = process_nppes_stream(
            reader, crosswalk, pcp_codes, facility_map,
            state_filter={"MO"},
        )

        # Only MO provider should be included
        assert "29095001100" in result
        assert "20209000100" not in result

    def test_multiple_providers_aggregate(self):
        pcp_codes, facility_map = _load_taxonomy_sets()
        crosswalk = self._make_crosswalk()

        rows = [
            self._make_nppes_row(npi="7777777771", zip_code="64106"),
            self._make_nppes_row(npi="7777777772", zip_code="64106"),
            self._make_nppes_row(npi="7777777773", zip_code="64106"),
        ]
        reader = self._make_reader(rows)

        result, _ = process_nppes_stream(reader, crosswalk, pcp_codes, facility_map)

        # 3 PCPs × 0.6 ratio = 1.8 for tract 29095001100
        assert abs(result["29095001100"]["pcp_count"] - 1.8) < 0.01
        # 3 PCPs × 0.4 ratio = 1.2 for tract 29095001200
        assert abs(result["29095001200"]["pcp_count"] - 1.2) < 0.01


class TestWriteOutputCSV:
    def test_write_and_read_csv(self, tmp_path):
        output_path = tmp_path / "output.csv"
        tract_counts = {
            "29095001100": {
                "pcp_count": 12.4,
                "fqhc_count": 1.0,
                "urgent_care_count": 2.3,
                "rural_health_clinic_count": 0.0,
                "primary_care_clinic_count": 0.5,
                "community_health_center_count": 0.0,
            },
        }

        write_output_csv(tract_counts, output_path)

        assert output_path.exists()
        with open(output_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 1
        row = rows[0]
        assert row["tract_fips"] == "29095001100"
        assert float(row["pcp_count"]) == 12.4
        assert float(row["fqhc_count"]) == 1.0
        assert float(row["total_providers"]) == 16.2
